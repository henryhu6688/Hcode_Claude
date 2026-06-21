# S0 第一版完成记录——从零到 CLI ↔ Daemon ping/pong 闭环

> **写给学习者的详细记录。** 本文档记录 S0 阶段交付了什么、每个模块为什么这样设计、开发过程中踩过的坑、以及测试策略。适合想理解"如何从零搭建一个类型安全的双进程 Agent 骨架"的开发者阅读。

**日期:** 2026-06-12 → 2026-06-19  
**分支:** v0 → master（16 次提交）  
**测试:** 31 个测试全部通过，ruff + mypy strict 零告警  
**代码量:** ~600 行源码 + ~700 行测试 + ~300 行脚本/doc

---

## 目录

1. [S0 解决了什么问题](#1-s0-解决了什么问题)
2. [最终交付物清单](#2-最终交付物清单)
3. [架构全景图](#3-架构全景图)
4. [逐模块详解](#4-逐模块详解)
   - [4.1 项目骨架与工具链](#41-项目骨架与工具链)
   - [4.2 协议层——类型安全的 JSON-RPC 2.0](#42-协议层类型安全的-json-rpc-20)
   - [4.3 配置系统——四级优先级](#43-配置系统四级优先级)
   - [4.4 传输层——异步 TCP NDJSON 服务器](#44-传输层异步-tcp-ndjson-服务器)
   - [4.5 守护进程入口——CoreApp 生命周期](#45-守护进程入口coreapp-生命周期)
   - [4.6 CLI 客户端](#46-cli-客户端)
   - [4.7 协议文档自动生成](#47-协议文档自动生成)
5. [测试策略详解](#5-测试策略详解)
6. [开发过程与关键决策](#6-开发过程与关键决策)
7. [踩坑记录](#7-踩坑记录)
8. [为 S1 铺好的路](#8-为-s1-铺好的路)
9. [给学习者的建议](#9-给学习者的建议)

---

## 1. S0 解决了什么问题

在写任何 Agent 逻辑之前，先把**系统边界**立住。如果一开始就在一个文件里写"调 LLM + 执行工具 + 打印结果"的脚本，后面要拆成双进程、要加事件流、要支持 TUI，全部要推翻重来。

S0 的核心目标只有一句话：**CLI 和 daemon 通过真实的 TCP NDJSON IPC 完成一次 ping/pong。**

这看起来比"搭个脚手架"重得多——S0 做完，你得到的是一个**类型安全的、可扩展的双进程通信框架**，而不仅仅是一个能跑的脚本。

---

## 2. 最终交付物清单

| 类别 | 文件 | 行数 | 职责 |
|------|------|------|------|
| **项目配置** | `pyproject.toml` | 49 | PEP 621 项目元数据 + uv/mypy/ruff/pytest 配置 |
| **协议层** | `core/protocol/envelope.py` | 49 | JSON-RPC 2.0 信封 + 5 个标准错误码 |
| | `core/protocol/commands.py` | 27 | Command 判别联合（PingCommand/PongResult） |
| | `core/protocol/events.py` | 22 | Event 判别联合（CoreStartedEvent） |
| **配置** | `core/config.py` | 156 | 四级优先级 + structlog 初始化 |
| **传输层** | `core/transport/socket_server.py` | 153 | TCP NDJSON 异步 server + 完整错误处理矩阵 |
| **daemon** | `core/app.py` | 83 | CoreApp 生命周期管理 + 信号处理 |
| **CLI** | `cli/main.py` | 94 | hcode ping / --version / --help |
| **脚本** | `scripts/gen_protocol_doc.py` | 154 | pydantic → WIRE_PROTOCOL.md + --check CI 模式 |
| **文档** | `WIRE_PROTOCOL.md` | 314 | 自动生成的完整协议文档 |
| | `USAGE.md` | 342 | 使用文档 |
| | `CLAUDE.md` / `readme.md` | — | 项目指令 + 路线图 |
| **测试** | `tests/` (9 文件) | ~700 | 31 个测试：16 个协议 + 11 个配置 + 1 个集成 + 3 个 CLI |

---

## 3. 架构全景图

```
┌──────────────────┐                    ┌────────────────────────┐
│     hcode CLI    │                    │     hcode-core daemon   │
│   cli/main.py    │                    │      core/app.py       │
│                  │                    │                        │
│  hcode ping ─────┼── TCP:NDJSON ────→│  ┌──────────────────┐  │
│  hcode --version │                    │  │   SocketServer   │  │
│  hcode --help    │                    │  │   transport/     │  │
└──────────────────┘                    │  └────────┬─────────┘  │
                                        │           │dispatch     │
                                        │  ┌────────▼─────────┐  │
                                        │  │   Handler 注册表  │  │
                                        │  │   core.ping → fn  │  │
                                        │  └────────┬─────────┘  │
                                        │           │             │
                                        │  ┌────────▼─────────┐  │
                                        │  │    Protocol 层    │  │
                                        │  │  envelope/commands│  │
                                        │  │  /events (pydantic)│  │
                                        │  └────────┬─────────┘  │
                                        │           │             │
                                        │  ┌────────▼─────────┐  │
                                        │  │   Config 四级优先  │  │
                                        │  └──────────────────┘  │
                                        └────────────────────────┘
```

**数据流（一次 ping/pong）：**

```
CLI: asyncio.open_connection("127.0.0.1", 47201)
  → 构造 Request(id=nonce, method="core.ping", params={"nonce": nonce})
  → model_dump_json() + "\n" → writer.write()
  → reader.readline() → json.loads() → 校验

Daemon: SocketServer._handle_client()
  → reader.readline() → json.loads() → _dispatch()
  → 校验 jsonrpc=="2.0" → 查 handler["core.ping"] → await handler(params)
  → SuccessResponse(id=nonce, result=PongResult(...))
  → model_dump() → json.dumps() + "\n" → writer.write()
```

---

## 4. 逐模块详解

### 4.1 项目骨架与工具链

**pyproject.toml 的 6 个关键决策：**

```toml
# 1. 构建后端选 Hatchling —— 最轻量的 PEP 517 构建后端
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

# 2. 三个入口点预埋（S1/S2 才实现 tui）
[project.scripts]
hcode = "hcode_claude.cli.main:main"
hcode-core = "hcode_claude.core.app:run"      # ← 模块级函数，不是实例方法
hcode-tui = "hcode_claude.tui.__main__:main"  # ← 预埋，S0 还不能用

# 3. 依赖写兼容范围，uv.lock 锁精确版本
dependencies = [
    "pydantic>=2.0",        # discriminated union 需要 v2
    "python-dotenv>=1.0",   # .env 文件加载
    "structlog>=24.0",      # 结构化日志
]

# 4. mypy strict 模式 —— 从第一天就开启
[tool.mypy]
strict = true

# 5. pytest asyncio_mode = "auto" —— 不需要 @pytest.mark.asyncio 装饰器
[tool.pytest.ini_options]
asyncio_mode = "auto"

# 6. ruff 只开 E/F/I/UP 规则 —— 够用，不过度 lint
[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

**为什么用 `src/` 布局而不是平铺：**

- 避免测试时意外 import 到未安装的本地包
- `mypy` + `explicit_package_bases = true` 可以精确控制类型检查范围
- 与 pytest 的 `testpaths = ["tests"]` 配合，测试目录镜像 src 结构

**版本号放在哪里：**

```python
# src/hcode_claude/core/__init__.py
__version__ = "0.0.1"
```

不用 `importlib.metadata.version()`——那依赖 editable install，开发阶段容易出问题。CLI 和 daemon 都 `from hcode_claude.core import __version__`。

---

### 4.2 协议层——类型安全的 JSON-RPC 2.0

这是整个系统的**契约层**。所有 IPC 消息都走这里，pydantic v2 做校验。

#### 4.2.1 信封（envelope.py）

```python
class Request(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"   # ← Literal 强制编译期校验
    id: int | str                       # ← 支持整数和字符串两种 id
    method: str
    params: dict[str, Any] = {}        # ← 默认空字典，而不是 None

class SuccessResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str
    result: Any                         # ← Any 类型，承载任意 result

class ErrorResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None               # ← None 是合法的（parse error 时无法提取 id）
    error: ErrorDetail

# 5 个标准 JSON-RPC 错误码
PARSE_ERROR = -32700      # JSON 解析失败
INVALID_REQUEST = -32600  # 缺少 jsonrpc 或 method
METHOD_NOT_FOUND = -32601 # handler 未注册
INVALID_PARAMS = -32602   # 参数校验失败
INTERNAL_ERROR = -32603   # handler 内部异常
```

**关键设计点：**

1. **id 类型 `int | str | None`**：JSON-RPC 规范允许 id 为 null（parse error 场景），`None` 序列化后变成 `null`
2. **`Literal["2.0"]`**：如果有人试图传 `jsonrpc="1.0"`，pydantic 在构造时就抛 `ValidationError`——不是运行时才发现
3. **params 默认 `{}`**：避免 handler 里到处写 `if params is None`

#### 4.2.2 Command 判别联合（commands.py）

```python
class PingCommand(BaseModel):
    type: Literal["ping"]              # ← discriminator 字段

class PongResult(BaseModel):
    type: Literal["pong"]
    nonce: str
    server_version: str

# 判别联合 —— 按 type 字段自动路由到正确的子类型
Command = Annotated[
    PingCommand,
    Field(discriminator="type"),
]
```

**为什么用 `discriminator="type"`：**

pydantic v2 的 discriminated union 让序列化/反序列化时自动按 `type` 字段路由。将来加 `RunCommand(type="run")` 只要追加到 `Command = Annotated[PingCommand | RunCommand, ...]`，不需要改任何路由逻辑。

注意 S0 的 `Command` 只有一个成员（`PingCommand`），但已预埋判别联合的语法，给 S1+ 留好了扩展口。

**为什么 PingCommand 不带 nonce：**

nonce 是 JSON-RPC 请求层面的概念（`params.nonce`），不是命令语义的一部分。`PingCommand` 只描述"这是什么命令"（type=ping），参数通过 envelope 的 params 传递。handler 自行从 params 提取 nonce。

#### 4.2.3 Event 判别联合（events.py）

```python
class CoreStartedEvent(BaseModel):
    type: Literal["core.started"]
    host: str
    port: int
    version: str

Event = Annotated[
    CoreStartedEvent,
    Field(discriminator="type"),
]
```

S0 只有这一个事件。daemon 启动完成后发一条 structlog 日志（不是通过 TCP 广播——广播是 S2 EventBus 的事）。

---

### 4.3 配置系统——四级优先级

```
环境变量  HCODE_PORT=9000        ← 最高优先级
    ↑ 覆盖
.env      HCODE_PORT=8000
    ↑ 覆盖
~/.hcode/config.toml  port=7000
    ↑ 覆盖
内建默认   port=47201             ← 最低优先级
```

**实现细节：**

```python
# 加载顺序就是优先级从低到高
def load_config() -> Config:
    merged = dict(_DEFAULTS)                    # 1. 内建默认

    for k, v in _load_user_toml().items():     # 2. ~/.hcode/config.toml
        merged[k] = v

    for k, v in _load_dotenv_values().items():  # 3. .env
        merged[k] = v

    for k, v in _load_env_values().items():     # 4. 环境变量
        merged[k] = v

    return Config(host=..., port=int(...), ...)  # 类型转换
```

**为什么 Config 是 frozen dataclass 而不是 pydantic BaseModel：**

配置在 daemon 启动时加载一次，之后不应被修改。`@dataclass(frozen=True)` 在编译期和运行期都强制不可变，比 pydantic 的 `model_config = ConfigDict(frozen=True)` 更轻量。

**未知 key 硬退出的设计理由：**

```python
_VALID_KEYS = {"host", "port", "log_level", "log_file", "log_format"}

for k, v in raw.items():
    if k not in _VALID_KEYS:
        print(f"Unknown config key: {k}", file=sys.stderr)
        sys.exit(1)           # ← 不是警告，是直接退出
```

如果 `log_leve1` 写成了 `log_leve1`（数字 1 代替字母 l），警告很容易被忽略，用户一直以为自己在用 DEBUG 级别，实际用的是 INFO。硬退出逼你立刻修正。

**类型转换为什么分开写 `_coerce_str` / `_coerce_int`：**

```python
def _coerce_str(key: str, value: object) -> str:
    return str(value)

def _coerce_int(key: str, value: object) -> int:
    return int(value)
```

分开写是为了通过 mypy strict。如果写一个 `_coerce` 返回 `str | int`，调用处的类型收窄会让 mypy 报错。

---

### 4.4 传输层——异步 TCP NDJSON 服务器

这是整个 S0 最核心的模块。`SocketServer` 负责 TCP 连接管理 + NDJSON 逐行解析 + JSON-RPC 分发 + 错误处理。

#### 4.4.1 端口探测

```python
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
        pass  # 端口空闲，正常启动

    self._server = await asyncio.start_server(...)
```

**为什么不是 `SO_REUSEADDR`：**

`SO_REUSEADDR` 会让两个进程同时 bind 同一端口——请求被随机路由到其中一个。这比"启动失败"更难排查。端口探测 + 明确报错是最安全的做法。

探测逻辑利用了 `asyncio.open_connection` 的行为——如果端口已监听，连接成功（说明被占用）；如果 `ConnectionRefusedError`，说明端口空闲。

#### 4.4.2 请求分发流程

```python
async def _dispatch(self, line: str) -> ErrorResponse | SuccessResponse:
    # 1. JSON 解析
    msg = json.loads(line)
    # ↓ JSONDecodeError → -32700 Parse error (id=null)

    # 2. 校验 jsonrpc 和 method
    if msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        # → -32600 Invalid Request

    # 3. 查找 handler
    handler = self._handlers.get(msg["method"])
    if handler is None:
        # → -32601 Method not found

    # 4. 执行 handler
    result = await handler(params)
    # ↓ 异常 → -32603 Internal error

    return SuccessResponse(id=req_id, result=result)
```

#### 4.4.3 错误处理矩阵

| 场景 | 错误码 | id 值 | 触发条件 |
|------|--------|-------|----------|
| 非 JSON 字符串 | `-32700` | `null` | `json.loads()` 抛 `JSONDecodeError` |
| 消息不是 dict | `-32600` | `null` | `not isinstance(msg, dict)` |
| 缺少 jsonrpc/method | `-32600` | 请求中的 id | `jsonrpc != "2.0"` |
| method 未注册 | `-32601` | 请求中的 id | `handler is None` |
| handler 内部异常 | `-32603` | 请求中的 id | `await handler(params)` 抛异常 |

**注意**：前两种场景 id 为 `null`，因为此时还无法从请求中提取 id。这正是 JSON-RPC 规范的设计——parse error 和 invalid request 时 id 必须为 null。

#### 4.4.4 Handler 类型签名

```python
Handler = Callable[[dict[str, object]], Awaitable[object]]
```

接收 `dict[str, object]`（params），返回 `Awaitable[object]`（任意可序列化对象）。这个类型签名贯穿全项目——register 时校验、_dispatch 里调用、app.py 里实现。mypy strict 模式下所有类型必须精确匹配。

---

### 4.5 守护进程入口——CoreApp 生命周期

```python
class CoreApp:
    async def run(self) -> None:
        cfg = load_config()                    # 1. 配置（四级优先级）
        setup_logging(cfg)                     # 2. structlog 初始化
        server = SocketServer(cfg.host, cfg.port)
        server.register("core.ping", self._handle_ping)  # 3. 注册 handler
        await server.start()                   # 4. 端口探测 + bind
        # 5. 发 CoreStartedEvent（structlog 日志）
        logger.info("core_started", **event.model_dump())
        # 6. 等待 SIGINT/SIGTERM
        await shutdown_event.wait()
        # 7. 优雅关闭
        await server.stop()
```

**生命周期设计原则：**

1. **配置加载失败 → 进程退出**（未知 key 硬退出，port 类型错误抛异常）
2. **端口被占用 → 进程退出**（端口探测拦截）
3. **正常关闭 → 先停 accept 新连接 → 处理完现有连接 → 退出**

**Windows 兼容处理：**

```python
def _setup_signal_handlers(self, shutdown_event):
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
        except NotImplementedError:
            pass  # Windows ProactorEventLoop 不支持，但 Ctrl+C 仍可终止进程
```

Windows 上的 `asyncio` 默认使用 `ProactorEventLoop`，不支持 `add_signal_handler`。用 try/except 兜底——虽然信号注册失败，但 `Ctrl+C` 会直接终止进程，不影响开发体验。

**模块级入口的设计：**

```python
# 供 pyproject.scripts 中的 hcode-core 调用
def run() -> None:
    app = CoreApp()
    asyncio.run(app.run())

# 直接 python -m hcode_claude.core.app 也启动
if __name__ == "__main__":
    run()
```

两个入口：`uv run hcode-core` 调用模块级 `run()` 函数；`python -m hcode_claude.core.app` 触发 `__main__` 保护。测试用后者（subprocess + `-m`），开发用前者更方便。

---

### 4.6 CLI 客户端

```python
def main() -> None:
    if len(sys.argv) == 1:
        _usage()
    elif sys.argv[1] == "ping":
        asyncio.run(_ping(...))
    elif sys.argv[1] == "--version":
        _version()
    elif sys.argv[1] == "--help":
        _usage()
    else:
        # 未知命令 → 报错 + exit 1
```

**为什么不用 argparse/Click/Typer：**

S0 只有 3 个分支（ping / --version / --help），引入命令行框架是过度设计。手写的 `_parse_arg(name, default)` 只有 4 行代码。

```python
def _parse_arg(name: str, default: str) -> str:
    try:
        idx = sys.argv.index(name)
        return sys.argv[idx + 1]
    except (ValueError, IndexError):
        return default
```

S3+ 当命令变多时再引入 Typer——那时候决策是有依据的。

**ping 流程的关键细节：**

```python
async def _ping(host, port, nonce):
    # 1. TCP 连接（5 秒超时）
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=5.0)

    # 2. 用 pydantic 构造请求（类型安全）
    request = Request(id=nonce, method="core.ping", params={"nonce": nonce})
    writer.write(request.model_dump_json().encode() + b"\n")

    # 3. 读一行，解析 JSON
    line = await reader.readline()
    data = json.loads(line.decode())

    # 4. 先判断 error 再解 result
    if "error" in data:
        err = ErrorResponse(**data)     # ← pydantic 校验错误响应结构
        ...
    result = PongResult(**data["result"])  # ← pydantic 校验 pong 字段
```

**先判断 error 再解 result**——如果 daemon 返回了错误响应，直接取 `data["result"]` 会 KeyError。先检查 `"error" in data` 是防御性编程。

**nonce 默认值：** `uuid.uuid4().hex[:8]`——8 位十六进制足够在单机开发环境中做请求配对，不需要完整的 UUID。

---

### 4.7 协议文档自动生成

```python
# 核心逻辑只有一行
schema = model.model_json_schema()
```

pydantic v2 自带 `model_json_schema()` 方法，直接输出 JSON Schema。生成器主要做格式化 + 拼 Markdown + 加示例。

**`--check` CI 模式的设计：**

```python
if "--check" in sys.argv:
    current = output_path.read_text(encoding="utf-8")
    expected = generate()
    if current != expected:
        print("WIRE_PROTOCOL.md is out of date")
        sys.exit(1)    # ← CI 失败，阻止合并
```

这保证了一个重要的约定：**改协议类型必须同时更新文档**。如果有人改了 `PongResult` 加了字段但忘记跑 `gen_protocol_doc.py`，CI 会拦下来。

**WIRE_PROTOCOL.md 为什么提交到 git：**

- clone 后直接可读，不需要安装依赖 + 跑脚本
- `--check` 模式依赖 git 中的版本做对比

---

## 5. 测试策略详解

S0 结束了 31 个测试，覆盖四个层级：

```
31 tests total
├── 单元测试（协议层）: 16 tests
│   ├── test_envelope.py  (8 tests) — 信封编解码 + 错误码 + Literal 校验
│   ├── test_commands.py  (5 tests) — PingCommand/PongResult 序列化
│   └── test_events.py    (3 tests) — CoreStartedEvent 序列化 + 类型校验
├── 单元测试（配置层）: 11 tests
│   └── test_config.py   (11 tests) — 四级优先级 + 未知 key 退出 + frozen
├── 集成测试: 1 test
│   └── test_app.py      — 启动 daemon 子进程 → ping → 校验 pong
└── CLI 测试: 3 tests
    └── test_main.py     — --version 输出 / --help 输出 / ping 失败场景
```

### 5.1 测试代码风格

每个测试函数必须有两行注释：

```python
# 功能：验证 ErrorResponse 的 id 可以为 None（parse error 场景）
# 设计：id=None 不会触发 ValidationError，对应标准中无法提取 id 的情况
def test_error_response_allows_none_id():
    ...
```

- `# 功能：` 说明测什么
- `# 设计：` 说明为什么这样测——边界条件、fixture 选择理由、断言方式

这不是形式主义。当测试失败时，`# 设计：` 帮助快速理解测试意图，判断是代码 bug 还是测试本身需要更新。

### 5.2 free_port fixture

```python
@pytest.fixture
def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))      # port 0 = OS 分配空闲端口
        return s.getsockname()[1]      # 获取实际端口号
    # socket 自动 close，端口释放
```

**关键设计：** bind port 0 → 获取实际端口 → close socket → 返回端口号。释放后再传回来给 daemon 用。这避免了硬编码端口号导致的测试冲突。

**竞态条件？** bind 和 close 之间有微小的时间窗口，另一个进程可能抢走这个端口。但在本地测试环境中概率极低，而且 daemon 的端口探测会兜底（检测到被占用就报错退出，测试失败而不是静默用错端口）。

### 5.3 集成测试：test_daemon_ping_pong

这是 S0 最有价值的测试——它验证了**真实进程间的 TCP NDJSON 通信**：

```python
async def test_daemon_ping_pong(free_port, tmp_path):
    # 1. 用 subprocess.Popen 启动 daemon 子进程
    proc = subprocess.Popen(
        [sys.executable, "-m", "hcode_claude.core.app"],
        env={**os.environ, "HCODE_PORT": str(free_port),
             "PYTHONPATH": "src", "HCODE_HOME": str(tmp_path)})

    # 2. 轮询等待 TCP 就绪（最多 5 秒，每 0.1 秒试一次）
    for _ in range(50):
        try:
            reader, writer = await asyncio.open_connection(...)
            break
        except (ConnectionRefusedError, ...):
            if proc.poll() is not None:
                pytest.fail("daemon exited early")  # 提前挂了的诊断
            await asyncio.sleep(0.1)

    # 3. 发 core.ping，收 pong，校验 nonce + version
    # 4. finally 块保证 terminate daemon（即使测试失败）
```

**为什么轮询 50 次而不是用 `asyncio.sleep(5)`：**

如果 daemon 在 0.5 秒就启动了，sleep 5 秒浪费 4.5 秒。轮询让测试尽可能快完成（通常 < 1s）。

**为什么在轮询循环里检查 `proc.poll()`：**

如果 daemon 因为配置错误或端口冲突直接退出了，不检查 `proc.poll()` 会让我们等满 5 秒超时。提前检查 + `pytest.fail` 可以把 daemon 的 stdout/stderr 打印出来，节省排查时间。

**为什么用 `subprocess.Popen` 而不是 `asyncio.create_subprocess_exec`：**

S0 阶段保持简单。`Popen` 的跨平台行为更稳定，`terminate()` + `wait()` + `kill()` 的关闭模式在 Windows 和 Unix 上都能正常工作。

---

## 6. 开发过程与关键决策

### 6.1 推进策略：TDD 自底向上

```
Task 1: 项目骨架（pyproject.toml + 目录）
Task 2: envelope.py    ← 先写测试，8 个全红，再写实现，8 个全绿
Task 3: commands.py    ← 先写测试，5 个全红，再写实现，5 个全绿
Task 4: events.py      ← 先写测试，3 个全红，再写实现，3 个全绿
Task 5: config.py      ← 先写测试，11 个全红，再写实现，11 个全绿
Task 6: socket_server  ← 先写 conftest（free_port fixture），再写实现
Task 7: app.py         ← 先写集成测试（1 个大红），再写实现，变绿
Task 8: cli/main.py    ← 先写测试，3 个全红，再写实现，3 个全绿
Task 9: gen_protocol_doc.py  ← 脚本类任务，写完 + 运行验证
Task 10: 全量测试 + lint 收尾
```

**每步都有 commit**，每个 commit 只做一件事。16 次提交的历史清晰可追溯。

### 6.2 关键设计决策

| # | 决策点 | 选择 | 为什么 |
|---|--------|------|--------|
| 1 | 协议层目录名 | `core/protocol/` 而非 `core/bus/` | protocol 更语义化；S2 EventBus 是独立模块 |
| 2 | 测试布局 | `tests/` 镜像 `src/` 结构 | 找对应测试无歧义，新人一眼看懂 |
| 3 | 日志库 | structlog 而非标准 logging | 结构化日志 + 绑定额外上下文（conn、method 等），为 S2 事件流打基础 |
| 4 | 配置格式 | TOML 而非 YAML/JSON | Python 3.11+ 内置 tomllib，零依赖；TOML 可读性优于 JSON |
| 5 | discriminator | `"type"` 字段 | 统一的路由键，全项目一致 |
| 6 | 命令行参数 | 手写 `_parse_arg` | S0 只有 3 个分支，不引入 CLI 框架 |
| 7 | 版本号 | `core/__init__.py` 常量 | 避免 `importlib.metadata` 的 editable install 依赖 |
| 8 | S0 目录范围 | 只建 S0 实际文件 | 不预建 S1-S7 空壳目录 |
| 9 | 项目级 config.toml | S0 不做 | 留给 S4（会话与记忆阶段） |

### 6.3 为什么 S0 做得比一般脚手架重

一个典型的脚手架只做：目录 + pyproject.toml + "Hello World" 入口。S0 多做了：

1. **类型安全的协议层**：不是裸 dict 传参，而是 pydantic discriminated union
2. **四级配置系统**：不只是读环境变量，而是建立了完整的优先级链
3. **端口探测**：不是裸 `asyncio.start_server` 然后让 OS 报错
4. **完整错误处理矩阵**：5 种 JSON-RPC 标准错误场景全覆盖
5. **协议文档自动生成**：改了代码忘更新文档会被 CI 拦
6. **31 个测试**：包括真实进程集成测试

**代价是 S0 花了约 10 个任务步骤，收益是 S1-S7 不用推倒任何东西重来。**

---

## 7. 踩坑记录

### 7.1 Windows 兼容性

| 问题 | 表现 | 解决 |
|------|------|------|
| `touch` 命令不存在 | `mkdir -p` + `touch` 脚本报错 | 改用 Windows 兼容的 `echo. > file` 或 Python `Path.touch()` |
| `add_signal_handler` 不支持 | daemon 启动时 Warning | try/except `NotImplementedError`，Ctrl+C 仍可终止 |
| `SIGTERM` vs `terminate()` | 集成测试中 daemon 杀不掉 | 用 `proc.terminate()` + `wait(timeout=5)` + `proc.kill()` 三层兜底 |
| `PYTHONPATH` 必须显式设 | `ModuleNotFoundError: hcode_claude` | 因为 uv 不做 editable install，子进程需要 `PYTHONPATH=src` |

### 7.2 mypy strict 模式下的类型问题

```python
# 问题：tomllib.load 返回 dict[str, Any]，myy 不允许直接赋值给 dict[str, object]
raw = tomllib.load(f)  # → dict[str, Any]
result: dict[str, object] = {}
for k, v in raw.items():
    result[k] = v      # ← mypy error: incompatible type

# 解决：显式类型收窄
result: dict[str, object] = {}
for k, v in raw.items():
    if k not in _VALID_KEYS:
        sys.exit(1)
    result[k] = v       # ← mypy 通过（因为 Any → object 是合法的向上转型）
```

### 7.3 pydantic discriminated union 的语法

```python
# 错误写法（pydantic v2 不支持 | 语法和 Field(discriminator) 混用）
Command = PingCommand | RunCommand  # ← 这不是 discriminated union

# 正确写法
Command = Annotated[
    PingCommand,                    # ← S0 只有一个成员
    Field(discriminator="type"),
]
```

S1 加 `RunCommand` 时改成 `Annotated[PingCommand | RunCommand, Field(discriminator="type")]`。

---

## 8. 为 S1 铺好的路

S0 结束时，以下能力已经就绪，S1 直接复用：

| 能力 | S0 位置 | S1 怎么用 |
|------|---------|-----------|
| JSON-RPC 协议 | `protocol/envelope.py` | S1 的 `agent.run` 命令复用同一套 Request/SuccessResponse/ErrorResponse |
| 判别联合扩展 | `protocol/commands.py` | `Command` 加 `RunCommand` 成员 |
| 事件扩展 | `protocol/events.py` | `Event` 加 `RunStartedEvent`、`ToolCallEvent` 等 |
| SocketServer handler 注册 | `transport/socket_server.py` | `server.register("agent.run", handler)` |
| 配置扩展 | `config.py` | `_VALID_KEYS` 加 `anthropic_api_key`、`max_steps` 等 |
| 模块级入口 | `app.py` | `CoreApp.run()` 里注册更多 handler |
| CLI 扩展 | `cli/main.py` | 加 `hcode run --goal "..."` 子命令 |
| 集成测试 fixture | `conftest.py` | 复用 `free_port` fixture |
| 协议文档生成 | `scripts/gen_protocol_doc.py` | 自动纳入新的 Command/Event 类型 |

---

## 9. 给学习者的建议

### 如果你想从零做一个类似的系统

1. **先从协议契约开始。** 在写任何业务逻辑之前，先把"系统之间怎么通信"定义清楚。pydantic discriminated union 是 Python 生态里做这件事最好的工具。

2. **TDD 不是教条，但在协议层和配置层特别值。** 协议层的测试（"这个 JSON 能正确序列化/反序列化吗"）写起来快，跑起来快，但能拦住的 bug 非常多。配置层的测试同样——"环境变量覆盖 .env 了吗"这类逻辑，不写测试一个月后你自己也记不住优先级。

3. **双进程架构越早建立越好。** 不要先写单进程脚本再拆——拆的时候 IPC 协议、错误处理、信号管理全部要重做。S0 虽然看起来"重"，但它换来的是 S1-S7 不用推倒任何东西。

4. **集成测试不要 mock TCP。** `test_daemon_ping_pong` 是真实子进程 + 真实 TCP 连接。mock 掉 `asyncio.start_server` 的测试只能验证"代码写对了"，不能验证"能跑起来"。S0 阶段就建立真实集成测试的能力，后面加功能时这个测试框架直接复用。

5. **Windows 兼容性从第一天就考虑。** 信号处理、`subprocess` 终止方式、路径分隔符——这些在 Unix 上能跑但 Windows 上报错的问题，越早处理代价越小。

6. **mypy strict 从第一天就开启。** 类型系统的价值是累积的——代码越多，类型检查越有价值。如果 S3 再开 strict，前面的几百行代码全是类型错误，修复成本极高。

### 如果你想学习这个项目的代码

建议按以下顺序阅读：

```
1. readme.md                     ← 理解全局路线图
2. WIRE_PROTOCOL.md              ← 理解 IPC 协议格式
3. src/.../protocol/envelope.py  ← 协议信封（最底层）
4. src/.../protocol/commands.py  ← 命令定义
5. src/.../protocol/events.py    ← 事件定义
6. src/.../config.py             ← 配置加载
7. src/.../transport/socket_server.py  ← 传输层（最核心）
8. src/.../app.py                ← daemon 组装
9. src/.../cli/main.py           ← CLI 客户端
10. tests/core/test_app.py       ← 集成测试（看完整数据流）
```

---

> **下一步：** S1 — Agent 最小闭环。`hcode run --goal "..."` 从用户目标到 LLM → 工具调用 → 事件文件完整跑通。
