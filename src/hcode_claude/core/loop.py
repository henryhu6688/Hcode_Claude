"""Agent 核心循环——plan→observe→act→observe 循环，管理 LLM 调用与工具执行"""

from hcode_claude.core.context import ExecutionContext
from hcode_claude.core.events.bus import EventBus
from hcode_claude.core.llm.provider import BaseProvider
from hcode_claude.core.llm.types import LoopResult
from hcode_claude.core.protocol.events import (
    LlmUsageEvent,
    StepFinishedEvent,
    StepStartedEvent,
    ToolCallFailedEvent,
    ToolCallFinishedEvent,
    ToolCallStartedEvent,
)
from hcode_claude.core.tools.registry import ToolRegistry

# Agent 基础 system prompt
BASE_SYSTEM_PROMPT = """你是一个 AI 编程助手。用户会给你任务，你可以使用工具来完成。
每次只调用必要的工具，不要调用多余的。如果任务已经完成，直接回复文本即可。"""


class AgentLoop:
    """持有 Context、Provider、Registry、EventBus，执行 plan→observe→act→observe 循环"""

    # 注入依赖：上下文、LLM provider、工具注册表、事件总线
    def __init__(
        self,
        ctx: ExecutionContext,
        provider: BaseProvider,
        registry: ToolRegistry,
        bus: EventBus,
    ) -> None:
        self._ctx = ctx
        self._provider = provider
        self._registry = registry
        self._bus = bus

    # 运行 Agent 循环直到终止
    async def run(self, goal: str, max_steps: int = 20) -> LoopResult:
        # 构建 system prompt + 初始 user 消息
        system = await self._ctx.build_system_prompt(BASE_SYSTEM_PROMPT)
        self._ctx.add_user_message(goal)

        for step in range(1, max_steps + 1):
            # 每步开始事件
            step_started = StepStartedEvent(type="step.started", step_number=step)
            await self._bus.publish(step_started)

            # plan: 调 LLM
            response = await self._provider.chat(
                messages=self._ctx.messages,
                tools=self._registry.as_anthropic_tools(),
                system=system,
            )

            # 用量事件
            usage_event = LlmUsageEvent(
                type="llm.usage",
                input_tokens=response.usage.get("input_tokens", 0),
                output_tokens=response.usage.get("output_tokens", 0),
            )
            await self._bus.publish(usage_event)

            # observe: 记录 assistant 消息（必须在 act 之前，Anthropic API 格式要求）
            raw_tool_uses = [
                {"id": tu.id, "name": tu.name, "input": tu.input}
                for tu in response.tool_uses
            ]
            self._ctx.add_assistant_message(response.text, raw_tool_uses)

            if not response.tool_uses:
                # 无工具调用 → 任务完成
                step_finished = StepFinishedEvent(
                    type="step.finished", step_number=step, tool_call_count=0
                )
                await self._bus.publish(step_finished)
                return LoopResult(status="completed", steps=step, output=response.text)

            # act: 执行所有工具调用
            tool_results = []
            for tu in response.tool_uses:
                started = ToolCallStartedEvent(
                    type="tool.started", tool_name=tu.name, params=tu.input
                )
                await self._bus.publish(started)

                try:
                    tool = self._registry.get(tu.name)
                    output = await tool.invoke(tu.input)
                    finished = ToolCallFinishedEvent(
                        type="tool.finished", tool_name=tu.name, output=output[:500]
                    )
                    await self._bus.publish(finished)
                    tool_results.append({
                        "tool_use_id": tu.id,
                        "content": output,
                        "is_error": False,
                    })
                except Exception as e:
                    failed = ToolCallFailedEvent(
                        type="tool.failed", tool_name=tu.name, error=str(e)
                    )
                    await self._bus.publish(failed)
                    tool_results.append({
                        "tool_use_id": tu.id,
                        "content": str(e),
                        "is_error": True,
                    })

            # observe: 所有工具结果打包到一条 user 消息
            self._ctx.add_tool_results(tool_results)
            step_finished = StepFinishedEvent(
                type="step.finished", step_number=step, tool_call_count=len(tool_results)
            )
            await self._bus.publish(step_finished)

        # max_steps 用尽
        return LoopResult(status="max_steps", steps=max_steps, output="")
