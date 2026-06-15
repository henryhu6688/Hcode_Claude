"""Event 判别联合——按 type 字段路由（S0 仅有 CoreStartedEvent）"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class CoreStartedEvent(BaseModel):
    """daemon 启动完毕事件——通知日志/客户端 daemon 已就绪"""

    type: Literal["core.started"]
    host: str
    port: int
    version: str


# Event 判别联合，全系统统一按 type 字段路由
Event = Annotated[
    CoreStartedEvent,
    Field(discriminator="type"),
]
