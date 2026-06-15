"""JSON-RPC 2.0 信封类型测试"""

import json

import pytest
from pydantic import ValidationError

from hcode_claude.core.protocol.envelope import (
    JSONRPC_VERSION,
    ErrorDetail,
    ErrorResponse,
    Request,
    SuccessResponse,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
)


# 功能：验证 Request 序列化生成合法的 JSON-RPC 2.0 请求
# 设计：全覆盖 4 个必填字段和 params 默认值
def test_request_serializes_to_jsonrpc():
    req = Request(id=1, method="core.ping", params={"nonce": "abc"})
    data = req.model_dump()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert data["method"] == "core.ping"
    assert data["params"] == {"nonce": "abc"}


# 功能：验证 Request params 字段默认值为空字典
# 设计：不传 params 构造，dump 后断言 params 为 {}
def test_request_params_defaults_to_empty_dict():
    req = Request(id="x", method="test")
    assert req.params == {}


# 功能：验证 SuccessResponse 携带任意类型 result
# 设计：result 声明为 Any，传入嵌套 dict 校验不丢字段
def test_success_response_holds_result():
    resp = SuccessResponse(id=1, result={"type": "pong", "nonce": "abc", "server_version": "0.0.1"})
    d = resp.model_dump()
    assert d["jsonrpc"] == "2.0"
    assert d["id"] == 1
    assert d["result"]["type"] == "pong"
    assert d["result"]["server_version"] == "0.0.1"


# 功能：验证 ErrorResponse 的 id 可以为 None（parse error 场景）
# 设计：id=None 不会触发 ValidationError，对应标准中无法提取 id 的情况
def test_error_response_allows_none_id():
    err = ErrorResponse(id=None, error=ErrorDetail(code=PARSE_ERROR, message="Parse error"))
    d = err.model_dump()
    assert d["id"] is None
    assert d["error"]["code"] == PARSE_ERROR


# 功能：验证 ErrorResponse JSON 序列化后 id 为 null
# 设计：model_dump_json 确保 None → null，deserialize 后 id 为 None
def test_error_response_json_null_id():
    err = ErrorResponse(id=None, error=ErrorDetail(code=PARSE_ERROR, message="Parse error"))
    raw = err.model_dump_json()
    obj = json.loads(raw)
    assert obj["id"] is None


# 功能：验证标准 JSON-RPC 错误码常量定义正确
# 设计：逐项对比规范值，错误码变更会立即失败
def test_standard_error_codes():
    assert PARSE_ERROR == -32700
    assert INVALID_REQUEST == -32600
    assert METHOD_NOT_FOUND == -32601
    assert INVALID_PARAMS == -32602
    assert INTERNAL_ERROR == -32603


# 功能：验证 JSONRPC_VERSION 为 "2.0"
# 设计：全项目唯一的版本常量，测试保证不意外改动
def test_jsonrpc_version_constant():
    assert JSONRPC_VERSION == "2.0"


# 功能：验证 Request 的 jsonrpc 字段只接受 "2.0"，其他字面量被拒绝
# 设计：jsonrpc 声明为 Literal["2.0"]，传 "1.0" 应触发 pydantic ValidationError
def test_request_rejects_non_2_0_version():
    with pytest.raises(ValidationError):
        Request(jsonrpc="1.0", id=1, method="test")  # type: ignore[arg-type]
