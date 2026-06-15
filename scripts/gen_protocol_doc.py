"""从 pydantic 协议类型生成 WIRE_PROTOCOL.md——JSON Schema + 字段说明 + 示例

用法:
    python scripts/gen_protocol_doc.py          # 生成 WIRE_PROTOCOL.md
    python scripts/gen_protocol_doc.py --check  # CI 模式：检查是否过期
"""

import sys
from pathlib import Path

# 将 src 加入搜索路径，以便 import hcode_claude
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hcode_claude.core.protocol.commands import PingCommand, PongResult
from hcode_claude.core.protocol.envelope import (
    ErrorDetail,
    ErrorResponse,
    Request,
    SuccessResponse,
)
from hcode_claude.core.protocol.events import CoreStartedEvent


# 生成完整的 WIRE_PROTOCOL.md 内容
def generate() -> str:
    lines: list[str] = [
        "# Wire Protocol",
        "",
        "> 自动生成，请勿手动编辑。",
        "> 生成自: `src/hcode_claude/core/protocol/`",
        "",
        "## JSON-RPC 2.0 over NDJSON",
        "",
        "每行一个完整 JSON 消息，`\\n` 分隔，消息体内部不允许换行。",
        "",
        "---",
        "",
        "## 请求信封",
        "",
    ]

    # Request
    lines.append("### Request\n")
    lines.append("```json")
    lines.append(json_schema_block(Request))
    lines.append("```\n")

    # SuccessResponse
    lines.append("### SuccessResponse\n")
    lines.append("```json")
    lines.append(json_schema_block(SuccessResponse))
    lines.append("```\n")

    # ErrorResponse
    lines.append("### ErrorResponse\n")
    lines.append("```json")
    lines.append(json_schema_block(ErrorResponse))
    lines.append("```\n")

    # ErrorDetail
    lines.append("### ErrorDetail\n")
    lines.append("```json")
    lines.append(json_schema_block(ErrorDetail))
    lines.append("```\n")

    # 错误码
    lines.append("### 标准错误码\n")
    lines.append("| Code | Name | 说明 |")
    lines.append("|------|------|------|")
    lines.append("| -32700 | Parse Error | JSON 解析失败 |")
    lines.append("| -32600 | Invalid Request | 缺少 jsonrpc 或 method |")
    lines.append("| -32601 | Method Not Found | handler 未注册 |")
    lines.append("| -32602 | Invalid Params | 参数校验失败 |")
    lines.append("| -32603 | Internal Error | handler 内部异常 |")
    lines.append("")

    lines.append("---\n")
    lines.append("## Commands\n")

    # PingCommand
    lines.append("### core.ping\n")
    lines.append("**Request:** `PingCommand`\n")
    lines.append("```json")
    lines.append(json_schema_block(PingCommand))
    lines.append("```\n")

    lines.append("**Success Response:** `PongResult`\n")
    lines.append("```json")
    lines.append(json_schema_block(PongResult))
    lines.append("```\n")

    lines.append("**示例:**\n")
    lines.append("```")
    ping_req = '→ {"jsonrpc":"2.0","id":"abc123","method":"core.ping","params":{"nonce":"abc123"}}'
    lines.append(ping_req)
    pong_resp = (
        '← {"jsonrpc":"2.0","id":"abc123",'
        '"result":{"type":"pong","nonce":"abc123","server_version":"0.0.1"}}'
    )
    lines.append(pong_resp)
    lines.append("```\n")

    lines.append("---\n")
    lines.append("## Events\n")

    # CoreStartedEvent
    lines.append("### core.started\n")
    lines.append("```json")
    lines.append(json_schema_block(CoreStartedEvent))
    lines.append("```\n")

    lines.append("**示例:**\n")
    lines.append("```json")
    lines.append('{"type":"core.started","host":"127.0.0.1","port":47201,"version":"0.0.1"}')
    lines.append("```\n")

    return "\n".join(lines)


# 将 pydantic 模型的 JSON Schema 格式化为可读 JSON 字符串
def json_schema_block(model: type) -> str:
    import json
    schema = model.model_json_schema()
    return json.dumps(schema, indent=2, ensure_ascii=False)


# CLI 主入口
def main() -> None:
    output_path = Path(__file__).resolve().parent.parent / "WIRE_PROTOCOL.md"

    if "--check" in sys.argv:
        # CI 模式：对比当前文件与生成内容
        if not output_path.exists():
            print("WIRE_PROTOCOL.md missing — run python scripts/gen_protocol_doc.py to generate")
            sys.exit(1)
        current = output_path.read_text(encoding="utf-8")
        expected = generate()
        if current != expected:
            msg = (
                "WIRE_PROTOCOL.md is out of date — "
                "run python scripts/gen_protocol_doc.py to regenerate"
            )
            print(msg)
            sys.exit(1)
        print("WIRE_PROTOCOL.md is up to date")
    else:
        content = generate()
        output_path.write_text(content, encoding="utf-8")
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
