"""hcode CLI——轻量命令行入口（S0: ping / --version / --help）"""

import asyncio
import json
import sys
from uuid import uuid4

from hcode_claude.core import __version__
from hcode_claude.core.protocol.commands import PongResult
from hcode_claude.core.protocol.envelope import ErrorResponse, Request


# hcode CLI 主入口
def main() -> None:
    if len(sys.argv) == 1:
        _usage()
    elif sys.argv[1] == "ping":
        asyncio.run(_ping(
            host=_parse_arg("--host", "127.0.0.1"),
            port=int(_parse_arg("--port", "47201")),
            nonce=_parse_arg("--nonce", uuid4().hex[:8]),
        ))
    elif sys.argv[1] == "--version":
        _version()
    elif sys.argv[1] == "--help":
        _usage()
    else:
        print(f"Unknown command: {sys.argv[1]}", file=sys.stderr)
        _usage()
        sys.exit(1)


# 发送 core.ping 请求到 daemon，打印结果
async def _ping(host: str, port: int, nonce: str) -> None:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5.0,
        )
    except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
        print(f"无法连接到 daemon ({host}:{port})", file=sys.stderr)
        sys.exit(1)

    request = Request(
        id=nonce,
        method="core.ping",
        params={"nonce": nonce},
    )
    writer.write(request.model_dump_json().encode() + b"\n")
    await writer.drain()

    line = await reader.readline()
    writer.close()

    data = json.loads(line.decode())

    if "error" in data:
        err = ErrorResponse(**data)
        print(f"Error [{err.error.code}]: {err.error.message}", file=sys.stderr)
        sys.exit(1)

    result = PongResult(**data["result"])
    print(f"pong from {result.server_version} (nonce={result.nonce})")


# 打印 CLI 版本号
def _version() -> None:
    print(f"hcode v{__version__}")


# 打印使用说明
def _usage() -> None:
    print("hcode - Hcode AI Agent CLI")
    print()
    print("Commands:")
    print("  hcode ping    Send ping to hcode-core daemon")
    print("                --host HOST   (default 127.0.0.1)")
    print("                --port PORT   (default 47201)")
    print("                --nonce NONCE (default random)")
    print("  hcode --version  Show version")
    print("  hcode --help     Show this help")


# 从命令行参数中提取 --key value，找不到返回默认值
def _parse_arg(name: str, default: str) -> str:
    try:
        idx = sys.argv.index(name)
        return sys.argv[idx + 1]
    except (ValueError, IndexError):
        return default


if __name__ == "__main__":
    main()
