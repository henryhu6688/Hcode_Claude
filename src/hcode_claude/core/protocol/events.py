"""Event 判别联合——按 type 字段路由"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class CoreStartedEvent(BaseModel):
    """daemon 启动完毕事件——通知日志/客户端 daemon 已就绪"""
    type: Literal["core.started"]
    host: str
    port: int
    version: str


# S1 新增事件

class RunStartedEvent(BaseModel):
    """run 开始事件——AgentRunner 启动新的 agent.run 时发布"""
    type: Literal["run.started"]
    run_id: str
    goal: str


class RunFinishedEvent(BaseModel):
    """run 结束事件——Agent 循环终止时发布"""
    type: Literal["run.finished"]
    run_id: str
    status: Literal["completed", "max_steps", "error"]
    steps: int


class StepStartedEvent(BaseModel):
    """每步开始事件——AgentLoop 每轮循环开始时发布"""
    type: Literal["step.started"]
    step_number: int


class StepFinishedEvent(BaseModel):
    """每步结束事件——工具调用全部完成后发布"""
    type: Literal["step.finished"]
    step_number: int
    tool_call_count: int


class ToolCallStartedEvent(BaseModel):
    """工具调用开始事件——开始 invoke 工具时发布"""
    type: Literal["tool.started"]
    tool_name: str
    params: dict[str, Any]


class ToolCallFinishedEvent(BaseModel):
    """工具调用成功事件——工具返回结果后发布"""
    type: Literal["tool.finished"]
    tool_name: str
    output: str


class ToolCallFailedEvent(BaseModel):
    """工具调用失败事件——工具抛异常时发布"""
    type: Literal["tool.failed"]
    tool_name: str
    error: str


class LlmTokenEvent(BaseModel):
    """流式 token 事件——LLM 输出每个 token 时发布"""
    type: Literal["llm.token"]
    text: str


class LlmUsageEvent(BaseModel):
    """LLM 用量事件——每次 LLM 调用完成后发布"""
    type: Literal["llm.usage"]
    input_tokens: int
    output_tokens: int


class LlmModelSelectedEvent(BaseModel):
    """LLM 模型选择事件——记录实际使用的模型 ID"""
    type: Literal["llm.model_selected"]
    model_id: str


# Event 判别联合，全系统统一按 type 字段路由
Event = Annotated[
    CoreStartedEvent
    | RunStartedEvent
    | RunFinishedEvent
    | StepStartedEvent
    | StepFinishedEvent
    | ToolCallStartedEvent
    | ToolCallFinishedEvent
    | ToolCallFailedEvent
    | LlmTokenEvent
    | LlmUsageEvent
    | LlmModelSelectedEvent,
    Field(discriminator="type"),
]
