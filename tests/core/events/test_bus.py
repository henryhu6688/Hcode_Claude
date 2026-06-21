"""EventBus 进程内 pub/sub 测试"""

import pytest
from pydantic import BaseModel

from hcode_claude.core.events.bus import EventBus


class FakeEvent(BaseModel):
    type: str = "fake"
    payload: str


class AnotherEvent(BaseModel):
    type: str = "another"
    value: int


# 功能：验证 publish 后订阅者能收到事件对象
# 设计：用内联 async handler 收集事件，断言收到的就是发布的那个对象
@pytest.mark.asyncio
async def test_publish_reaches_subscriber():
    bus = EventBus()
    received: list[FakeEvent] = []

    async def handler(event: FakeEvent) -> None:
        received.append(event)

    bus.subscribe(FakeEvent, handler)
    event = FakeEvent(payload="hello")
    await bus.publish(event)
    assert len(received) == 1
    assert received[0].payload == "hello"


# 功能：验证多个订阅者都能收到同一事件
# 设计：两个不同 handler 订阅同一事件类型，断言都收到
@pytest.mark.asyncio
async def test_multiple_subscribers_all_receive():
    bus = EventBus()
    results: list[str] = []

    async def h1(event: FakeEvent) -> None:
        results.append("h1")

    async def h2(event: FakeEvent) -> None:
        results.append("h2")

    bus.subscribe(FakeEvent, h1)
    bus.subscribe(FakeEvent, h2)
    await bus.publish(FakeEvent(payload="x"))
    assert results == ["h1", "h2"]


# 功能：验证订阅者只收到自己订阅的事件类型
# 设计：h1 订阅 Fake，h2 订阅 Another，publish Fake 只触发 h1
@pytest.mark.asyncio
async def test_subscriber_only_receives_subscribed_type():
    bus = EventBus()
    fake_received: list[str] = []
    another_received: list[str] = []

    async def fake_handler(event: FakeEvent) -> None:
        fake_received.append(event.payload)

    async def another_handler(event: AnotherEvent) -> None:
        another_received.append(str(event.value))

    bus.subscribe(FakeEvent, fake_handler)
    bus.subscribe(AnotherEvent, another_handler)
    await bus.publish(FakeEvent(payload="only_fake"))
    assert len(fake_received) == 1
    assert len(another_received) == 0


# 功能：验证无订阅者时 publish 不抛异常
# 设计：发布无人关注的事件是合法场景
@pytest.mark.asyncio
async def test_publish_no_subscribers_no_error():
    bus = EventBus()
    await bus.publish(FakeEvent(payload="nobody"))
    # 不抛异常即通过


# 功能：验证一个订阅者抛异常不影响其他订阅者
# 设计：bus 应隔离异常，其他 handler 正常执行
@pytest.mark.asyncio
async def test_handler_exception_isolated():
    bus = EventBus()
    called: list[str] = []

    async def crashing(event: FakeEvent) -> None:
        raise RuntimeError("boom")

    async def normal(event: FakeEvent) -> None:
        called.append("normal")

    bus.subscribe(FakeEvent, crashing)
    bus.subscribe(FakeEvent, normal)
    await bus.publish(FakeEvent(payload="x"))
    assert called == ["normal"]


# 功能：验证 subscribe 返回取消订阅的回调
# 设计：调用返回的函数后，订阅者不再收到事件
@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received: list[str] = []

    async def handler(event: FakeEvent) -> None:
        received.append(event.payload)

    unsubscribe = bus.subscribe(FakeEvent, handler)
    unsubscribe()
    await bus.publish(FakeEvent(payload="after_unsub"))
    assert len(received) == 0
