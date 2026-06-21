"""AgentLoop 测试——用 FakeProvider 模拟 LLM 行为"""

import pytest

from hcode_claude.core.context import ExecutionContext
from hcode_claude.core.events.bus import EventBus
from hcode_claude.core.llm.provider import BaseProvider
from hcode_claude.core.llm.types import ChatResult, ToolUseBlock
from hcode_claude.core.loop import AgentLoop
from hcode_claude.core.tools.registry import ToolRegistry


class FakeProvider(BaseProvider):
    """模拟 LLM：按预设序列依次返回 ChatResult"""

    def __init__(self, responses: list[ChatResult]) -> None:
        self.responses = responses
        self.called = 0

    async def chat(
        self, messages: list[dict], tools: list[dict] | None, system: str
    ) -> ChatResult:
        if self.called >= len(self.responses):
            return ChatResult(text="done", tool_uses=[], usage={"input_tokens": 0, "output_tokens": 0})
        result = self.responses[self.called]
        self.called += 1
        return result


class FakeTool:
    """模拟工具：直接返回传入参数"""
    name = "fake_tool"
    description = "a fake tool"

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def invoke(self, params: dict) -> str:
        return f"executed with {params}"


# 功能：验证纯文本回复（无工具调用）时 AgentLoop 正常终止
# 设计：FakeProvider 返回空 tool_uses，loop 应返回 completed status
@pytest.mark.asyncio
async def test_loop_stops_on_text_only_response():
    ctx = ExecutionContext()
    provider = FakeProvider([
        ChatResult(text="任务完成", tool_uses=[], usage={"input_tokens": 10, "output_tokens": 5}),
    ])
    registry = ToolRegistry()
    bus = EventBus()
    loop = AgentLoop(ctx, provider, registry, bus)

    result = await loop.run("测试目标", max_steps=5)
    assert result.status == "completed"
    assert result.steps == 1
    assert result.output == "任务完成"


# 功能：验证达到 max_steps 时强制终止
# 设计：FakeProvider 一直返回工具调用，直到步数耗尽
@pytest.mark.asyncio
async def test_loop_max_steps_triggers():
    ctx = ExecutionContext()
    tu = ToolUseBlock(id="t1", name="fake_tool", input={})
    provider = FakeProvider([
        ChatResult(text="", tool_uses=[tu], usage={"input_tokens": 1, "output_tokens": 1}),
        ChatResult(text="", tool_uses=[tu], usage={"input_tokens": 1, "output_tokens": 1}),
        ChatResult(text="", tool_uses=[tu], usage={"input_tokens": 1, "output_tokens": 1}),
    ])
    registry = ToolRegistry()
    registry.register(FakeTool())
    bus = EventBus()
    loop = AgentLoop(ctx, provider, registry, bus)

    result = await loop.run("目标", max_steps=2)
    assert result.status == "max_steps"
    assert result.steps == 2


# 功能：验证工具调用正常执行并返回结果
# 设计：FakeProvider 返回一个工具调用，loop 应执行工具并将结果追加到 context
@pytest.mark.asyncio
async def test_loop_invokes_tool_and_continues():
    ctx = ExecutionContext()
    tu1 = ToolUseBlock(id="tu1", name="fake_tool", input={"x": 1})
    provider = FakeProvider([
        ChatResult(text="lets check", tool_uses=[tu1], usage={"input_tokens": 10, "output_tokens": 5}),
        ChatResult(text="done after tool", tool_uses=[], usage={"input_tokens": 10, "output_tokens": 5}),
    ])
    registry = ToolRegistry()
    registry.register(FakeTool())
    bus = EventBus()
    loop = AgentLoop(ctx, provider, registry, bus)

    result = await loop.run("目标", max_steps=5)
    assert result.status == "completed"
    assert result.steps == 2
    assert "done after tool" in result.output


# 功能：验证工具调用失败不会中断循环
# 设计：工具抛异常 → 结果以 error 形式写回 context，循环继续
@pytest.mark.asyncio
async def test_loop_handles_tool_error_gracefully():
    class CrashingTool:
        name = "crash"
        description = "crashes"

        @property
        def input_schema(self) -> dict:
            return {"type": "object", "properties": {}}

        async def invoke(self, params: dict) -> str:
            raise RuntimeError("boom")

    ctx = ExecutionContext()
    tu1 = ToolUseBlock(id="t1", name="crash", input={})
    provider = FakeProvider([
        ChatResult(text="", tool_uses=[tu1], usage={"input_tokens": 1, "output_tokens": 1}),
        ChatResult(text="ok after crash", tool_uses=[], usage={"input_tokens": 1, "output_tokens": 1}),
    ])
    registry = ToolRegistry()
    registry.register(CrashingTool())
    bus = EventBus()
    loop = AgentLoop(ctx, provider, registry, bus)

    result = await loop.run("目标", max_steps=5)
    assert result.status == "completed"
    assert result.steps == 2
