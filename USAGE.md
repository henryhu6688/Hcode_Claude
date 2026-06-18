# HcodeClaude 使用文档

> 当前版本: v0.0.1 — S0 阶段（CLI ↔ daemon ping/pong 闭环）

## 快速开始

**前置条件：** Python 3.12、uv

```bash
# 1. 克隆并安装
git clone git@github.com:henryhu6688/Hcode_Claude.git
cd Hcode_Claude
uv sync

# 2. 启动 daemon（终端 1）
PYTHONPATH=src uv run python -m hcode_claude.core.app

# 3. 发送 ping（终端 2）
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping

# 输出: pong from v0.0.1 (nonce=a1b2c3d4)
```

---

## 安装

```bash
uv sync
```

这会在 `.venv/` 创建虚拟环境并安装所有依赖（pydantic、structlog、python-dotenv、测试工具链）。

安装后可通过入口点调用（需要先 `uv sync`）：

```bash
uv run hcode ping          # CLI ping
uv run hcode --version     # 显示版本
uv run hcode-core          # 启动 daemon
```

开发模式下推荐直接用 `python -m`（更灵活，支持 `PYTHONPATH`）：

```bash
PYTHONPATH=src uv run python -m hcode_claude.core.app     # daemon
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping  # CLI
```

---

## 命令参考

### hcode-core — 启动守护进程

```bash
PYTHONPATH=src uv run python -m hcode_claude.core.app
```

启动后 daemon 在 `127.0.0.1:47201`（默认）监听 TCP 连接，等待 JSON-RPC 请求。日志输出到 stdout（默认 console 格式）。

**停止：** `Ctrl+C`（SIGINT）或 SIGTERM。

### hcode ping — 探测 daemon 是否存活

```bash
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping [选项]
```

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--host HOST` | `127.0.0.1` | daemon 地址 |
| `--port PORT` | `47201` | daemon 端口 |
| `--nonce NONCE` | 随机 8 位 hex | 请求标识，用于匹配响应 |

**示例：**

```bash
# 默认连接本地 daemon
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping

# 指定端口
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping --port 9999

# 指定 nonce
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping --nonce my-test-001
```

**成功输出：** `pong from v0.0.1 (nonce=my-test-001)`

**daemon 未启动：** `无法连接到 daemon (127.0.0.1:47201)`（exit code 1）

### hcode --version — 查看版本

```bash
PYTHONPATH=src uv run python -m hcode_claude.cli.main --version
# 输出: hcode v0.0.1
```

### hcode --help — 查看帮助

```bash
PYTHONPATH=src uv run python -m hcode_claude.cli.main --help
```

---

## 配置

四级优先级（高到低）：

```
环境变量  HCODE_PORT=9000          ← 最高
    ↑ 覆盖
.env      HCODE_PORT=8000
    ↑ 覆盖
~/.hcode/config.toml  port = 7000
    ↑ 覆盖
内建默认   port = 47201             ← 最低
```

### S0 配置项

| 键 | 类型 | 默认值 | 环境变量 | 说明 |
|----|------|--------|----------|------|
| `host` | string | `127.0.0.1` | `HCODE_HOST` | daemon 监听地址 |
| `port` | int | `47201` | `HCODE_PORT` | daemon 监听端口 |
| `log_level` | string | `INFO` | `HCODE_LOG_LEVEL` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `log_file` | string | `""`（空=不写文件） | `HCODE_LOG_FILE` | 日志文件路径 |
| `log_format` | string | `console` | `HCODE_LOG_FORMAT` | 日志格式：`console`（彩色文本）或 `json`（结构化 JSON） |

**重要约束：** 未知配置键会导致硬退出（`sys.exit(1)`），防止拼写错误被忽略。

### 配置方式 1：用户 TOML 文件

创建 `~/.hcode/config.toml`（Windows: `%USERPROFILE%\.hcode\config.toml`）：

```toml
port = 9000
log_level = "DEBUG"
log_format = "json"
```

> 测试环境可用 `HCODE_HOME` 环境变量覆盖 `~` 路径，指向自定义目录。

### 配置方式 2：项目 .env 文件

在运行 daemon 的目录创建 `.env`：

```
HCODE_PORT=8000
HCODE_LOG_FORMAT=json
```

### 配置方式 3：环境变量

```bash
# Linux/Mac
export HCODE_PORT=9999
hcode-core

# Windows (PowerShell)
$env:HCODE_PORT="9999"
uv run hcode-core
```

### 日志配置示例

**开发模式（彩色终端）：**
```toml
log_format = "console"
log_level = "DEBUG"
```

**生产模式（JSON 输出到文件）：**
```toml
log_format = "json"
log_level = "INFO"
log_file = "/var/log/hcode/daemon.log"
```

---

## Wire Protocol（开发者参考）

CLI 和 daemon 通过 **JSON-RPC 2.0 over NDJSON over TCP** 通信。

- **NDJSON**：每行一个完整 JSON，`\n` 分隔，消息体内部不能出现换行
- **JSON-RPC 2.0**：标准请求/响应格式，错误码遵循规范

### 请求格式

```json
{"jsonrpc":"2.0","id":"abc123","method":"core.ping","params":{"nonce":"abc123"}}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `jsonrpc` | `"2.0"` | 固定值 |
| `id` | int \| string | 请求标识，响应原样返回 |
| `method` | string | RPC 方法名，如 `"core.ping"` |
| `params` | object | 方法参数，默认 `{}` |

### 成功响应

```json
{"jsonrpc":"2.0","id":"abc123","result":{"type":"pong","nonce":"abc123","server_version":"0.0.1"}}
```

### 错误响应

```json
{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"Parse error"}}
```

| 错误码 | 名称 | 说明 |
|--------|------|------|
| -32700 | Parse Error | JSON 解析失败 |
| -32600 | Invalid Request | 缺少 jsonrpc 或 method |
| -32601 | Method Not Found | 方法未注册 |
| -32602 | Invalid Params | 参数校验失败 |
| -32603 | Internal Error | handler 内部异常 |

完整协议文档见 [WIRE_PROTOCOL.md](WIRE_PROTOCOL.md)（由 `scripts/gen_protocol_doc.py` 自动生成）。

---

## 开发指南

### 运行测试

```bash
# 全部测试
uv run pytest tests/ -v

# 单个测试文件
uv run pytest tests/core/test_config.py -v

# 单个测试函数
uv run pytest tests/core/protocol/test_envelope.py::test_request_serializes_to_jsonrpc -v

# 仅运行集成测试
uv run pytest tests/core/test_app.py -v
```

### 代码质量

```bash
# Ruff lint
uv run ruff check src/ tests/ scripts/

# Ruff 自动修复
uv run ruff check --fix src/ tests/ scripts/

# Mypy 类型检查（strict 模式）
uv run mypy src/
```

### 协议文档

```bash
# 生成 WIRE_PROTOCOL.md
uv run python scripts/gen_protocol_doc.py

# CI 模式：检查文档是否过期
uv run python scripts/gen_protocol_doc.py --check
```

### 测试目录结构

```
tests/
├── conftest.py                       # free_port fixture
├── core/
│   ├── protocol/
│   │   ├── test_envelope.py          # 信封编解码（8 tests）
│   │   ├── test_commands.py          # 命令序列化（5 tests）
│   │   └── test_events.py            # 事件序列化（3 tests）
│   ├── test_config.py                # 配置优先级（11 tests）
│   └── test_app.py                   # 集成测试：ping/pong（1 test）
└── cli/
    └── test_main.py                  # CLI 输出（3 tests）
```

> 测试镜像 `src/` 结构。测试函数上方有 `# 功能：` + `# 设计：` 两行中文注释。

---

## 项目结构

```
Hcode_claude/
├── pyproject.toml                    # PEP 621 项目配置 + 工具链
├── readme.md                         # 完整路线图 S0–S7
├── CLAUDE.md                         # Claude Code 指令
├── USAGE.md                          # 本文档
├── WIRE_PROTOCOL.md                  # 协议文档（自动生成）
├── uv.lock                           # 精确依赖锁
├── .gitignore
├── src/hcode_claude/
│   ├── core/
│   │   ├── __init__.py               # __version__ = "0.0.1"
│   │   ├── app.py                    # CoreApp daemon 入口
│   │   ├── config.py                 # 配置系统 + structlog 初始化
│   │   ├── protocol/                 # JSON-RPC 2.0 协议类型
│   │   │   ├── envelope.py           #   信封 + 错误码
│   │   │   ├── commands.py           #   Command 判别联合
│   │   │   └── events.py             #   Event 判别联合
│   │   └── transport/
│   │       └── socket_server.py      # TCP NDJSON 异步 server
│   └── cli/
│       └── main.py                   # hcode 命令行入口
├── scripts/
│   └── gen_protocol_doc.py           # pydantic → WIRE_PROTOCOL.md
├── tests/                            # 测试（镜像 src/ 结构）
└── docs/superpowers/
    ├── specs/                        # 设计文档
    └── plans/                        # 实现计划
```

---

## 常见问题

**Q: 启动 daemon 报 `Port 47201 already in use`？**

A: daemon 启动前会探测端口。已有实例在跑——关掉它，或换个端口：
```bash
export HCODE_PORT=47202
PYTHONPATH=src uv run python -m hcode_claude.core.app
```

**Q: `ModuleNotFoundError: No module named 'hcode_claude'`？**

A: 忘记设 `PYTHONPATH=src` 了。完整命令：
```bash
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping
```

**Q: Windows 上 `add_signal_handler` 报错？**

A: 已处理。`app.py` 在 Windows ProactorEventLoop 上自动跳过信号注册，`Ctrl+C` 仍可正常终止进程。
