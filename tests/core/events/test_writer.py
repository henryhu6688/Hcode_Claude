"""EventWriter 测试"""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from hcode_claude.core.events.bus import EventBus
from hcode_claude.core.events.writer import EventWriter


class FakeEvent(BaseModel):
    type: str = "fake"
    msg: str


# 功能：验证 EventWriter 将事件写入 events.jsonl，每行一个 JSON
# 设计：publish 两个事件后读文件，验证 NDJSON 格式（每行完整 JSON）
@pytest.mark.asyncio
async def test_writer_writes_ndjson(tmp_path: Path):
    bus = EventBus()
    writer = EventWriter()
    file_path = tmp_path / "events.jsonl"
    await writer.start(bus, file_path)

    await bus.publish(FakeEvent(msg="hello"))
    await bus.publish(FakeEvent(msg="world"))

    lines = file_path.read_text().strip().split("\n")
    assert len(lines) == 2
    e1 = json.loads(lines[0])
    e2 = json.loads(lines[1])
    assert e1["msg"] == "hello"
    assert e2["msg"] == "world"


# 功能：验证 EventWriter 序列化时用到 pydantic model_dump
# 设计：pydantic 默认 type 字段在 model_dump 中存在
@pytest.mark.asyncio
async def test_writer_includes_type_field(tmp_path: Path):
    bus = EventBus()
    writer = EventWriter()
    file_path = tmp_path / "events.jsonl"
    await writer.start(bus, file_path)

    await bus.publish(FakeEvent(msg="test"))

    data = json.loads(file_path.read_text().strip())
    assert data["type"] == "fake"
    assert data["msg"] == "test"
