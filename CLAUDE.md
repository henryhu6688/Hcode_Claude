# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

从零实现本地 AI Agent 系统（mini 版 Claude Code）。最终形态：`hcode-core`（常驻 daemon） + `hcode-tui`（终端 UI） + `hcode` CLI。
完整路线图 S0-S7 在 `readme.md`。

**当前阶段：S0 完成。** CLI ↔ daemon 通过 TCP NDJSON 完成 ping/pong 闭环。

## 常用命令

```bash
# 安装依赖
uv sync

# 运行所有测试
uv run pytest tests/ -v

# 运行单个测试文件
uv run pytest tests/core/test_config.py -v

# 运行单个测试函数
uv run pytest tests/core/protocol/test_envelope.py::test_request_serializes_to_jsonrpc -v

# Lint（ruff + mypy）
uv run ruff check src/ tests/ scripts/
uv run ruff check --fix src/ tests/ scripts/   # 自动修复
uv run mypy src/

# 启动 daemon（开发模式，需要 PYTHONPATH=src）
PYTHONPATH=src uv run python -m hcode_claude.core.app

# CLI ping（另一终端）
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping

# 协议文档生成
uv run python scripts/gen_protocol_doc.py          # 生成 WIRE_PROTOCOL.md
uv run python scripts/gen_protocol_doc.py --check  # CI 模式：检查是否过期
```

## 架构

```
hcode CLI ── TCP:NDJSON ──→ hcode-core daemon
                             ├── transport/socket_server.py  （asyncio TCP server）
                             ├── protocol/                   （JSON-RPC 2.0 类型）
                             ├── config.py                   （四级优先级）
                             └── app.py                      （CoreApp 生命周期）
```

- **双进程架构**：CLI/TUI 是客户端，核心逻辑在 daemon。CLI 崩了 Agent 不跟着死
- **IPC 协议**：JSON-RPC 2.0 over NDJSON（每行一个完整 JSON）over TCP
- **协议层**：pydantic v2 discriminated union，按 `type` 字段路由。Request/SuccessResponse/ErrorResponse 信封 + Command/Event 判别联合
- **传输层**：`SocketServer` 逐行读 NDJSON → `json.loads` → 分发到 `register()` 注册的 handler
- **配置**：四级优先级——内建默认 → `~/.hcode/config.toml` → `.env` → 环境变量。未知 key 硬退出

## 代码风格

- 函数 `def` 上方**一行**中文注释说明功能，不写多行 docstring
- 测试函数上方**两行**中文注释：`# 功能：`（测什么）+ `# 设计：`（为什么这样测）
- 测试目录 `tests/` 镜像 `src/` 结构
- `pyproject.toml` 中依赖写兼容范围，`uv.lock` 锁精确版本

## 开发流程

严格遵循 superpowers 流程：`brainstorming → writing-plans → executing-plans → verification → code-review → branch-complete`。
每阶段结束都能独立运行和验证。
