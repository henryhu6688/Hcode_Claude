"""Command 判别联合——按 type 字段路由"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PingCommand(BaseModel):
    """core.ping 命令——请求 daemon 回应 pong"""
    type: Literal["ping"]


class PongResult(BaseModel):
    """core.ping 的成功响应体"""
    type: Literal["pong"]
    nonce: str
    server_version: str


class RunCommand(BaseModel):
    """agent.run 命令——请求 daemon 执行 Agent"""
    type: Literal["agent.run"]
    goal: str
    max_steps: int = 20


class RunResult(BaseModel):
    """agent.run 的成功响应体"""
    type: Literal["run.result"]
    run_id: str
    status: Literal["completed", "max_steps", "error"]
    steps: int
    output: str


# Command 判别联合，全系统统一按 type 字段路由
Command = Annotated[
    PingCommand | RunCommand,
    Field(discriminator="type"),
]
