# S0 — 骨架与协议契约设计

**日期:** 2026-06-12  
**状态:** 已确认  
**分支:** v0  
**目标:** CLI 和 daemon 通过真实 IPC 完成一次 ping/pong

---

## 1. 决策汇总

| # | 决策点 | 选项 | 选择 |
|---|--------|------|------|
| 1 | 协议层目录 | core/bus/ vs core/protocol/ | **core/protocol/** |
| 2 | 测试布局 | 多种 | **tests/ 镜像 src/ 结构** |
| 3 | 依赖版本 | 宽松 vs 锁定 vs uv.lock | **pyproject 宽松 + uv.lock 锁死** |
| 4 | pyproject.toml | 用户提供 | **采用，加 structlog** |
| 5 | 日志输出 | stdout vs 文件 vs 双写 | **stdout + 文件双写** |
| 6 | 日志库 | logging vs structlog | **structlog** |
| 7 | S0 目录范围 | 只建 S0 vs 预建 S1-S7 | **只建 S0 实际文件** |
| 8 | 推进策略 | 自底向上 vs 自顶向下 vs TDD | **TDD（测试锚定）** |
| 9 | 项目级 config.toml | 要 vs 不要（S4 再加） | **S0 不要，只做 ~/.hcode/config.toml** |

---

## 2. 开发流程约束

后续所有开发严格走 superpowers 流程链：

```
brainstorming → writing-plans → executing-plans → verification → code-review → branch-complete
```

不跳过任何环节。每阶段结束都能运行、能验证、能留下文件证据。

---

## 3. 整体架构

```
┌──────────┐                    ┌────────────────────┐
│ hcode CLI │── TCP:NDJSON ──→  │     hcode-core       │
│ cli/main  │                   │    core/app.py      │
└──────────┘                    │  ┌──────────────┐   │
                                │  │ SocketServer │   │
                                │  │  transport/  │   │
                                │  └──────┬───────┘   │
                                │         │dispatch    │
                                │  ┌──────▼───────┐   │
                                │  │   Handlers   │   │
                                │  │  core.ping   │   │
                                │  └──────┬───────┘   │
                                │         │           │
                                │  ┌──────▼───────┐   │
                                │  │   Protocol   │   │
                                │  │  envelope    │   │
                                │  │  commands    │   │
                                │  │  events      │   │
                                │  └──────────────┘   │
                                │         │           │
                                │  ┌──────▼───────┐   │
                                │  │    Config    │   │
                                │  └──────────────┘   │
                                └────────────────────┘
```

**数据流：** CLI `hcode ping` → TCP 连接 → 发 NDJSON 的 JSON-RPC request → daemon 解析 envelope → 路由到 `core.ping` handler → 返回 JSON-RPC success → CLI 打印 `pong`

---

## 4. 目录结构（S0 只建实际使用的）

```
Hcode_claude/
├── pyproject.toml
├── readme.md
├── .gitignore
├── WIRE_PROTOCOL.md          # 自动生成
├── src/hcode_claude/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py       # __version__ = "0.0.1"
│   │   ├── app.py            # CoreApp + run() 入口
│   │   ├── config.py         # 四级优先级配置 + structlog 初始化
│   │   ├── protocol/
│   │   │   ├── __init__.py
│   │   │   ├── envelope.py   # Request/SuccessResponse/ErrorResponse/ErrorDetail + 错误码
│   │   │   ├── commands.py   # Command 判别联合,PingCommand/PongResult
│   │   │   └── events.py     # Event 判别联合,CoreStartedEvent
│   │   └── transport/
│   │       ├── __init__.py
│   │       └── socket_server.py  # TCP NDJSON server
│   └── cli/
│       ├── __init__.py
│       └── main.py           # hcode ping, hcode --version
├── scripts/
│   └── gen_protocol_doc.py   # pydantic 模型 → WIRE_PROTOCOL.md
└── tests/
    ├── conftest.py           # free_port fixture + daemon 子进程管理
    ├── core/
    │   ├── protocol/
    │   │   ├── test_envelope.py
    │   │   ├── test_commands.py
    │   │   └── test_events.py
    │   ├── test_config.py
    │   └── test_app.py       # 集成：启动 daemon → ping → 校验
    └── cli/
        └── test_main.py
```

---

## 5. pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "HcodeClaude"
version = "0.0.1"
requires-python = ">=3.12,<3.13"
dependencies = [
    "pydantic>=2.0",
    "python-dotenv>=1.0",
    "structlog>=24.0",
]

[project.scripts]
hcode = "hcode_claude.cli.main:main"
hcode-core = "hcode_claude.core.app:run"
hcode-tui = "hcode_claude.tui.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/hcode_claude"]

[dependency-groups]
dev = [
    "ruff>=0.4",
    "mypy>=1.10",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.ruff]
src = ["src"]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
ignore = []

[tool.mypy]
python_version = "3.12"
strict = true
mypy_path = "src"
explicit_package_bases = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

注意：`hcode-core` 入口指向模块级函数 `hcode_claude.core.app:run`，不是 `CoreApp.run` 实例方法。

---

## 6. 协议层（`core/protocol/`）

### 6.1 envelope.py — JSON-RPC 2.0 信封

```python
from typing import Any, Literal
from pydantic import BaseModel

JSONRPC_VERSION = "2.0"

class Request(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str
    method: str
    params: dict = {}

class SuccessResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str
    result: Any

class ErrorDetail(BaseModel):
    code: int
    message: str
    data: Any | None = None

class ErrorResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None
    error: ErrorDetail

# 标准 JSON-RPC 错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
```

### 6.2 commands.py — Command 判别联合

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field

class PingCommand(BaseModel):
    type: Literal["ping"]

class PongResult(BaseModel):
    type: Literal["pong"]
    nonce: str
    server_version: str

Command = Annotated[
    PingCommand | ...,
    Field(discriminator="type")
]
```

### 6.3 events.py — Event 判别联合

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field

class CoreStartedEvent(BaseModel):
    type: Literal["core.started"]
    host: str
    port: int
    version: str

Event = Annotated[
    CoreStartedEvent | ...,
    Field(discriminator="type")
]
```

### 设计要点

- discriminator 统一用 `"type"` 字段路由
- 错误时 `id` 允许 `None`（parse error 无法提取 id）
- `PingCommand` 不带 nonce 字段——nonce 通过 JSON-RPC 的 `params` 传递，由 handler 自行提取
- `PongResult.nonce` 让 CLI 验证响应对应自己的请求

---

## 7. 配置（`core/config.py`）

### 7.1 四级优先级

```
环境变量  HCODE_PORT=9000          (最高)
    ↑ 覆盖
.env      HCODE_PORT=8000
    ↑ 覆盖
~/.hcode/config.toml  port = 7000
    ↑ 覆盖
内建默认   port = 47201             (最低)
```

### 7.2 S0 配置项

| Key | 默认值 | 说明 |
|-----|--------|------|
| `host` | `"127.0.0.1"` | daemon 监听地址 |
| `port` | `47201` | daemon 监听端口 |
| `log_level` | `"INFO"` | structlog 级别 |
| `log_file` | `""`（空=不写文件） | 日志文件路径 |
| `log_format` | `"console"` | `"console"` 或 `"json"` |

### 7.3 核心约束

- **未知 key 硬退出** — 报 `Unknown config key: xxx` + exit 1，防止拼写错误悄无声息
- **port 类型校验** — 必须可转为 int，传字符串报错
- **S0 不做项目级 `.hcode/config.toml`** — 留给 S4

### 7.4 Config 类

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    host: str
    port: int
    log_level: str
    log_file: str
    log_format: str

# 加载配置：内建默认 → ~/.hcode/config.toml → .env → 环境变量
def load_config() -> Config:
    ...
```

### 7.5 structlog 初始化

```python
def setup_logging(cfg: Config) -> None:
    import structlog
    import logging

    logging.basicConfig(level=cfg.log_level.upper())

    renderer = (
        structlog.dev.ConsoleRenderer()
        if cfg.log_format == "console"
        else structlog.processors.JSONRenderer()
    )

    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,
        renderer,
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    # 如果配置了 log_file，额外挂 FileHandler
    if cfg.log_file:
        file_handler = logging.FileHandler(cfg.log_file)
        logging.getLogger().addHandler(file_handler)
```

---

## 8. 传输层（`core/transport/socket_server.py`）

### 8.1 NDJSON 格式

每行一个完整 JSON-RPC 2.0 消息，`\n` 分隔，消息体内部不允许换行：

```
→ {"jsonrpc":"2.0","id":1,"method":"core.ping","params":{}}
← {"jsonrpc":"2.0","id":1,"result":{"type":"pong","nonce":"","server_version":"0.0.1"}}
```

### 8.2 SocketServer 类

```python
from collections.abc import Callable

class SocketServer:
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._handlers: dict[str, Callable] = {}
        self._server: asyncio.Server | None = None

    def register(self, method: str, handler: Callable) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

### 8.3 连接处理流程

```
_client_handler(reader, writer)
    ├── 逐行读 StreamReader.readline()
    ├── 空行忽略
    ├── json.loads() 解析
    │   └── JSONDecodeError → 回 -32700 parse error
    ├── 校验 jsonrpc=="2.0" && "method" in msg
    │   └── 不合法 → 回 -32600 invalid request
    ├── 查 handlers[method]
    │   └── 未注册 → 回 -32601 method not found
    ├── await handler(params)
    │   └── 抛异常 → 回 -32603 internal error
    └── 构造 SuccessResponse → json.dumps + "\n" → writer.write → drain
```

### 8.4 端口探测

启动前先尝试连接目标端口——如果已有进程在监听，报错退出，防止端口冲突：

```python
async def start(self) -> None:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=1.0
        )
        writer.close()
        raise RuntimeError(f"Port {self._port} already in use")
    except (ConnectionRefusedError, OSError):
        pass  # 端口空闲，正常启动

    self._server = await asyncio.start_server(
        self._client_handler, self._host, self._port
    )
```

### 8.5 错误处理矩阵

| 场景 | 错误码 | id 值 |
|------|--------|-------|
| 非 JSON 字符串 | `-32700` Parse error | `null` |
| 缺少 jsonrpc/method | `-32600` Invalid Request | 请求中的 id 或 `null` |
| method 未注册 | `-32601` Method not found | 请求中的 id |
| handler 抛异常 | `-32603` Internal error | 请求中的 id |

### 8.6 日志埋点

每条连接/请求都打 structlog，绑定上下文：

```python
logger = structlog.get_logger().bind(conn=peer_name)
logger.info("client_connected")
logger.info("request", method="core.ping", id=1)
logger.info("response", method="core.ping", duration_ms=0.5)
logger.info("client_disconnected")
```

---

## 9. 守护进程入口（`core/app.py`）

### 9.1 生命周期

```
CoreApp.run()
  │
  ├── 1. load_config()          # 四级优先级，未知 key 硬退出
  ├── 2. setup_logging(cfg)     # structlog: console + 文件
  ├── 3. SocketServer(cfg.host, cfg.port)
  ├── 4. server.register("core.ping", handle_ping)
  ├── 5. server.start()         # 端口探测 + bind + accept 循环
  ├── 6. 发 CoreStartedEvent    # 日志输出
  ├── 7. asyncio.Event().wait() # 阻塞等待 SIGINT/SIGTERM
  │       ├── SIGINT  → shutdown_event.set()
  │       └── SIGTERM → shutdown_event.set()
  └── 8. server.stop()          # 优雅关闭
```

### 9.2 信号处理（Windows 兼容）

```python
def _setup_signal_handlers(shutdown_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)
```

Windows 没有 `SIGUSR1`/`SIGUSR2`，`add_signal_handler` 不支持 `SIGKILL`。S0 只处理 `SIGINT` 和 `SIGTERM`。

### 9.3 core.ping handler

```python
# 处理 core.ping 请求：提取 nonce，返回 PongResult
async def handle_ping(params: dict) -> PongResult:
    nonce = params.get("nonce", "") if isinstance(params, dict) else ""
    return PongResult(
        type="pong",
        nonce=nonce,
        server_version=__version__,
    )
```

### 9.4 模块级入口

```python
# 模块级入口，供 pyproject.scripts 中的 hcode-core 调用
def run() -> None:
    app = CoreApp()
    asyncio.run(app.run())
```

### 9.5 版本号

`src/hcode_claude/core/__init__.py` 定义 `__version__ = "0.0.1"`，CLI 和 daemon 共用。

---

## 10. CLI 入口（`cli/main.py`）

### 10.1 命令结构

```
hcode
├── hcode ping [--host HOST] [--port PORT] [--nonce NONCE]
├── hcode --version
└── hcode --help
```

S0 用 `sys.argv` 手写参数解析，不引入 Click/Typer（3 个分支不值得）。

### 10.2 ping 流程

```
hcode ping
  │
  ├── 1. 解析参数：--host(默认127.0.0.1) --port(默认47201) --nonce(默认uuid4.hex[:8])
  ├── 2. asyncio.open_connection(host, port)
  │       └── 连不上 → stderr "无法连接到 daemon" + exit 1
  ├── 3. 构造 Request(jsonrpc="2.0", id=nonce, method="core.ping", params={"nonce":nonce})
  ├── 4. json.dumps → writer.write → drain
  ├── 5. reader.readline() → json.loads → 校验
  ├── 6. 打印结果
  │       ├── 成功 → stdout "pong from v0.0.1"
  │       └── 错误 → stderr code + message + exit 1
  └── 7. writer.close() → exit 0
```

### 10.3 关键实现细节

- nonce 默认用 `uuid.uuid4().hex[:8]`，8 位十六进制足够 S0 做请求配对
- `--version` 复用 `core.__version__`，保证 CLI 和 daemon 版本一致
- `_parse_arg(name, default)`：从 `sys.argv` 提取参数值，找不到返回默认值

---

## 11. 协议文档生成（`scripts/gen_protocol_doc.py`）

### 11.1 输入输出

```
输入: src/hcode_claude/core/protocol/
      ├── envelope.py  (Request, SuccessResponse, ErrorResponse)
      ├── commands.py  (PingCommand, PongResult)
      └── events.py    (CoreStartedEvent)

输出: WIRE_PROTOCOL.md (项目根目录)
      └── 每个类型的 JSON Schema (pydantic model_json_schema()) + 示例
```

### 11.2 头注

```markdown
# Wire Protocol

自动生成，请勿手动编辑。
生成自: src/hcode_claude/core/protocol/
```

### 11.3 --check 模式

```bash
python scripts/gen_protocol_doc.py --check
# exit 0: 文档与代码一致
# exit 1: 文档过期，需重新生成
```

用于 CI pipeline 防止"改了代码但忘重新生成协议文档"的 PR。

### 11.4 WIRE_PROTOCOL.md 纳入 git

生成物提交到仓库。好处：
- clone 后直接看协议，不需要跑脚本
- CI 的 `--check` 能发现不一致

---

## 12. 测试设计（TDD 顺序）

### 12.1 conftest.py — free_port fixture

```python
# 返回空闲端口号：bind port 0 → 获取地址 → 关闭 → 释放端口 → 返回端口号
@pytest.fixture
def free_port() -> int:
    ...

# 启动 daemon 子进程，等待 TCP 可达，返回端口号
@pytest.fixture
async def running_daemon(free_port: int) -> int:
    ...
```

### 12.2 单元测试

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_envelope.py` | Request/Response 编解码、JSON-RPC 错误码、parse error 时 id=null |
| `test_commands.py` | PingCommand/PongResult 序列化、discriminator 路由 |
| `test_events.py` | CoreStartedEvent 创建、序列化 |
| `test_config.py` | 四级优先级合并、未知 key 硬退出、port 类型校验、env var 覆盖 |
| `test_main.py` | `--version` 输出、`--help` 输出、参数解析 |

### 12.3 集成测试（`test_app.py`）

```
test_ping_pong:
  1. free_port → 启动 daemon 子进程（传 HCODE_PORT 环境变量）
  2. 轮询直到 TCP 连接成功
  3. 发 core.ping → 收 pong
  4. 校验 server_version 和 nonce
  5. SIGTERM → daemon 退出
```

### 12.4 测试代码风格

所有测试函数遵循两行中文注释风格：

```python
# 功能：验证 publish 后订阅者能收到事件对象
# 设计：用内联 handler 收集事件引用，断言 is 而非 ==，排除序列化中间步骤的干扰
async def test_publish_reaches_subscriber() -> None:
    ...
```

两行缺一不可。`# 功能：` 说明测什么，`# 设计：` 说明为什么这样测。

---

## 13. 代码风格（全局）

所有函数 `def` 行上方有**一行中文注释**说明功能，不写多行 docstring：

```python
# 发送 JSON-RPC 响应并刷新写缓冲区
async def _send(self, writer: asyncio.StreamWriter, msg: BaseModel) -> None:
    ...
```

---

## 14. 不纳入 S0 的内容

- 不建 S1-S7 的空壳目录
- 不做项目级 `.hcode/config.toml`（S4）
- 不做 permissions / session / EventBus / compaction / skills / subagent / MCP
- 不引入 argparse / Click / Typer（S0 CLI 只有 3 个分支）
- 不引入 `importlib.metadata` 读版本号（避免 editable install 依赖）
- 日志库不用标准库 `logging`（S0 直接上 structlog）
