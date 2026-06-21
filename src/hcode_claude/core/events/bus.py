"""进程内事件总线——发布/订阅，AgentLoop 发布事件，Writer/Printer 订阅消费"""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

# 事件 handler 签名：接收 BaseModel 子类实例，返回 None
EventHandler = Callable[[Any], Awaitable[None]]


class EventBus:
    """进程内 pub/sub，按 BaseModel 子类型路由事件到已订阅 handler"""

    # 初始化空的订阅表
    def __init__(self) -> None:
        self._subscribers: dict[type, list[EventHandler]] = {}

    # 订阅指定事件类型，返回取消订阅的回调
    def subscribe(self, event_type: type, handler: EventHandler) -> Callable[[], None]:
        self._subscribers.setdefault(event_type, []).append(handler)

        def unsubscribe() -> None:
            handlers = self._subscribers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    # 发布事件：逐类型匹配，通知所有订阅者（异常隔离）
    async def publish(self, event: BaseModel) -> None:
        for event_type, handlers in self._subscribers.items():
            if isinstance(event, event_type):
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception:
                        pass  # 一个 handler 崩了不影响其他
