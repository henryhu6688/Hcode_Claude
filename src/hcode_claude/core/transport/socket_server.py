"""TCP NDJSON SocketServer——逐行读取 JSON-RPC 请求并分发到注册的 handler"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable

import structlog

from hcode_claude.core.protocol.envelope import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    JSONRPC_VERSION,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    ErrorDetail,
    ErrorResponse,
    SuccessResponse,
)

# JSON-RPC handler 签名：接收 params dict，返回可序列化的 result
Handler = Callable[[dict[str, object]], Awaitable[object]]


class SocketServer:
    """JSON-RPC 2.0 over NDJSON 异步 TCP server"""

    # 创建 server 实例，绑定地址和端口
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._handlers: dict[str, Handler] = {}
        self._server: asyncio.Server | None = None
        self._logger = structlog.get_logger()

    # 注册 RPC method handler
    def register(self, method: str, handler: Handler) -> None:
        self._handlers[method] = handler

    # 探测端口 + 启动 asyncio TCP server
    async def start(self) -> None:
        # 先探测端口是否被占用
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=1.0,
            )
            writer.close()
            raise RuntimeError(f"Port {self._port} already in use")
        except (ConnectionRefusedError, OSError):
            pass  # 端口空闲

        self._server = await asyncio.start_server(
            self._handle_client, self._host, self._port
        )
        self._logger.info(
            "server_started",
            host=self._host,
            port=self._port,
        )

    # 优雅关闭
    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._logger.info("server_stopped")

    # 处理单个 TCP 连接：循环读行 → 解析 → 分发 → 响应
    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        conn_logger = self._logger.bind(conn=str(peer))
        conn_logger.info("client_connected")

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break  # EOF——客户端断开

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue  # 跳过空行

                t0 = time.monotonic()
                response = await self._dispatch(line_str)
                elapsed_ms = (time.monotonic() - t0) * 1000

                raw = json.dumps(response.model_dump(), ensure_ascii=False) + "\n"
                writer.write(raw.encode("utf-8"))
                await writer.drain()
                conn_logger.info("response", duration_ms=round(elapsed_ms, 2))
        except Exception:
            conn_logger.exception("client_error")
        finally:
            writer.close()
            conn_logger.info("client_disconnected")

    # 分发单条 JSON 行到已注册 handler，返回 ErrorResponse 或 SuccessResponse
    async def _dispatch(self, line: str) -> ErrorResponse | SuccessResponse:
        # 1. JSON 解析
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return ErrorResponse(
                id=None,
                error=ErrorDetail(code=PARSE_ERROR, message="Parse error"),
            )

        if not isinstance(msg, dict):
            return ErrorResponse(
                id=None,
                error=ErrorDetail(code=INVALID_REQUEST, message="Invalid Request"),
            )

        req_id = msg.get("id")
        req_method = msg.get("method")

        # 2. 校验 jsonrpc 和 method
        if msg.get("jsonrpc") != JSONRPC_VERSION or not isinstance(req_method, str):
            return ErrorResponse(
                id=req_id,
                error=ErrorDetail(code=INVALID_REQUEST, message="Invalid Request"),
            )

        # 3. 查找 handler
        handler = self._handlers.get(req_method)
        if handler is None:
            return ErrorResponse(
                id=req_id,
                error=ErrorDetail(
                    code=METHOD_NOT_FOUND,
                    message=f"Method not found: {req_method}",
                ),
            )

        # 4. 执行 handler
        params = msg.get("params", {})
        if not isinstance(params, dict):
            params = {}
        try:
            result = await handler(params)
            return SuccessResponse(id=req_id, result=result)  # type: ignore[arg-type]
        except Exception as exc:
            return ErrorResponse(
                id=req_id,
                error=ErrorDetail(
                    code=INTERNAL_ERROR,
                    message=str(exc),
                ),
            )
