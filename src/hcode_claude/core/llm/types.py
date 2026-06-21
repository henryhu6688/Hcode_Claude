"""LLM 模块类型定义——ToolUseBlock、ChatResult、LoopResult"""

from typing import Any, Literal

from pydantic import BaseModel


class ToolUseBlock(BaseModel):
    """LLM 返回的单个工具调用块"""
    id: str
    name: str
    input: dict[str, Any]


class ChatResult(BaseModel):
    """单次 LLM 调用的完整结果"""
    text: str
    tool_uses: list[ToolUseBlock]
    usage: dict[str, int]


class LoopResult(BaseModel):
    """Agent 循环的最终结果"""
    status: Literal["completed", "max_steps"]
    steps: int
    output: str
