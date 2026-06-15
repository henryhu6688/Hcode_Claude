"""Event 判别联合测试"""

import json

import pytest
from pydantic import ValidationError

from hcode_claude.core.protocol.events import CoreStartedEvent


# 功能：验证 CoreStartedEvent 所有字段正常赋值
# 设计：构造完整 event 后断言 type/host/port/version
def test_core_started_event_fields():
    event = CoreStartedEvent(type="core.started", host="127.0.0.1", port=47201, version="0.0.1")
    assert event.type == "core.started"
    assert event.host == "127.0.0.1"
    assert event.port == 47201
    assert event.version == "0.0.1"


# 功能：验证 CoreStartedEvent 序列化到 JSON 再反序列化
# 设计：model_dump_json → json.loads，确保字段无丢失
def test_core_started_event_roundtrip():
    event = CoreStartedEvent(type="core.started", host="0.0.0.0", port=9999, version="1.2.3")
    raw = event.model_dump_json()
    obj = json.loads(raw)
    assert obj["type"] == "core.started"
    assert obj["host"] == "0.0.0.0"
    assert obj["port"] == 9999
    assert obj["version"] == "1.2.3"


# 功能：验证 CoreStartedEvent port 不接受非数字类型
# 设计：pydantic v2 默认强制 string→int，但 list→int 不可强转，应触发 ValidationError
def test_core_started_event_port_rejects_list():
    with pytest.raises(ValidationError):
        CoreStartedEvent(type="core.started", host="127.0.0.1", port=[1, 2, 3], version="0.0.1")  # type: ignore[arg-type]
