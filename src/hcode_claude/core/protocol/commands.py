"""Command 判别联合——按 type 字段路由（S0 仅有 Ping/Pong）"""

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


# Command 判别联合，全系统统一按 type 字段路由
Command = Annotated[
    PingCommand,
    Field(discriminator="type"),
]
