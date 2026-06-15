"""JSON-RPC 2.0 信封类型与标准错误码"""

from typing import Any, Literal

from pydantic import BaseModel

# JSON-RPC 2.0 协议版本常量
JSONRPC_VERSION = "2.0"

# 标准 JSON-RPC 错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class Request(BaseModel):
    """JSON-RPC 2.0 请求信封"""

    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str
    method: str
    params: dict[str, Any] = {}


class SuccessResponse(BaseModel):
    """JSON-RPC 2.0 成功响应信封"""

    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str
    result: Any


class ErrorDetail(BaseModel):
    """JSON-RPC 2.0 错误详情"""

    code: int
    message: str
    data: Any | None = None


class ErrorResponse(BaseModel):
    """JSON-RPC 2.0 错误响应信封——id 可为 None（parse error 场景）"""

    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None
    error: ErrorDetail
