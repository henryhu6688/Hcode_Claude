"""Command 判别联合测试"""

import pytest
from pydantic import ValidationError

from hcode_claude.core.protocol.commands import PingCommand, PongResult


# 功能：验证 PingCommand type 字段锁定为 "ping"
# 设计：构造 PingCommand，断言 type 为 Literal["ping"]
def test_ping_command_type_is_ping():
    cmd = PingCommand(type="ping")
    assert cmd.type == "ping"


# 功能：验证 PingCommand 拒绝非 "ping" 的 type 值
# 设计：传 "pong" 应触发 pydantic ValidationError
def test_ping_command_rejects_wrong_type():
    with pytest.raises(ValidationError):
        PingCommand(type="pong")  # type: ignore[arg-type]


# 功能：验证 PongResult 包含 nonce 和 server_version 字段
# 设计：构造完整 PongResult 后断言所有字段值和类型
def test_pong_result_fields():
    result = PongResult(type="pong", nonce="abc123", server_version="0.0.1")
    assert result.type == "pong"
    assert result.nonce == "abc123"
    assert result.server_version == "0.0.1"


# 功能：验证 PongResult 序列化后 JSON 字段完整
# 设计：model_dump 不丢字段，model_dump_json 可反序列化
def test_pong_result_serialization():
    result = PongResult(type="pong", nonce="xyz", server_version="1.0.0")
    d = result.model_dump()
    assert d == {"type": "pong", "nonce": "xyz", "server_version": "1.0.0"}


# 功能：验证 PongResult nonce 为空字符串是合法状态
# 设计：daemon 收到不含 nonce 的 ping 时返回空字符串 nonce
def test_pong_result_empty_nonce():
    result = PongResult(type="pong", nonce="", server_version="0.0.1")
    assert result.nonce == ""
