"""LLM Provider 抽象 + Anthropic 实现——封装 API 流式调用、prompt caching 与重试"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from anthropic import AsyncAnthropic

from hcode_claude.core.llm.types import ChatResult, ToolUseBlock


class BaseProvider(ABC):
    """LLM Provider 抽象——AgentLoop 只依赖此接口，不直接接触 SDK"""

    # 发送消息到 LLM，返回文本 + 工具调用列表 + 用量
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        system: str,
    ) -> ChatResult: ...


class AnthropicProvider(BaseProvider):
    """Anthropic 实现——流式调用 + prompt caching + 网络重试"""

    # 初始化 SDK 客户端和模型 ID
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    # 流式调用 Anthropic API，带重试和 prompt caching
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        system: str,
    ) -> ChatResult:
        system_blocks = self._with_cache_control(system)
        cached_tools = self._add_tool_cache_control(tools) if tools else None

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return await self._do_chat(messages, cached_tools, system_blocks)
            except Exception as e:
                last_error = e
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError(f"Anthropic API failed after 3 retries: {last_error}")

    # 执行单次 API 调用：构造请求 → 流式接收 → 收集 text + tool_uses
    async def _do_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        system_blocks: list[dict[str, Any]],
    ) -> ChatResult:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
            "system": system_blocks,
        }
        if tools:
            kwargs["tools"] = tools

        text_parts: list[str] = []
        tool_uses: dict[int, dict[str, str]] = {}  # index → {id, name, input_str}
        input_tokens = 0
        output_tokens = 0

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "message_start":
                    if event.message and event.message.usage:
                        input_tokens = event.message.usage.input_tokens
                elif event.type == "message_delta":
                    if event.usage:
                        output_tokens = event.usage.output_tokens
                elif event.type == "content_block_start":
                    block = event.content_block
                    if block and block.type == "tool_use":
                        tool_uses[event.index] = {
                            "id": block.id or "",
                            "name": block.name or "",
                            "input_str": "",
                        }
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta and delta.type == "text_delta":
                        text_parts.append(delta.text or "")
                    elif delta and delta.type == "input_json_delta":
                        if event.index in tool_uses:
                            tool_uses[event.index]["input_str"] += delta.partial_json or ""

        # 解析 tool_uses 中的 JSON input（按 stream index 排序保持 LLM 意图顺序）
        import json
        proper_order = []
        for idx in sorted(tool_uses.keys()):
            tu = tool_uses[idx]
            try:
                parsed_input = json.loads(tu["input_str"]) if tu["input_str"] else {}
            except json.JSONDecodeError:
                parsed_input = {}
            proper_order.append(ToolUseBlock(
                id=tu["id"],
                name=tu["name"],
                input=parsed_input,
            ))

        return ChatResult(
            text="".join(text_parts),
            tool_uses=proper_order,
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
        )

    # 给 system prompt 最后 2 段加 cache_control
    @staticmethod
    def _with_cache_control(system: str) -> list[dict[str, Any]]:
        paragraphs = [p for p in system.split("\n\n") if p.strip()]
        if len(paragraphs) <= 2:
            return [
                {"type": "text", "text": p, "cache_control": {"type": "ephemeral"}}
                for p in paragraphs
            ]
        result: list[dict[str, Any]] = [
            {"type": "text", "text": p} for p in paragraphs[:-2]
        ]
        for p in paragraphs[-2:]:
            result.append({
                "type": "text",
                "text": p,
                "cache_control": {"type": "ephemeral"},
            })
        return result

    # 给 tools 列表最后一条加 cache_control
    @staticmethod
    def _add_tool_cache_control(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not tools:
            return tools
        result = list(tools)
        result[-1] = {**result[-1], "cache_control": {"type": "ephemeral"}}
        return result
