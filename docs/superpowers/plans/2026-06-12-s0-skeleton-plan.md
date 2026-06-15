# S0 骨架与协议契约 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 TDD 方式从零构建 CLI 和 daemon，通过真实 TCP/NDJSON IPC 完成一次 ping/pong

**Architecture:** 双进程——`hcode` CLI 通过 TCP NDJSON 连 `hcode-core` daemon，协议层用 pydantic discriminated union 定义 JSON-RPC 2.0 类型，structlog 结构化日志

**Tech Stack:** Python 3.12, uv + Hatchling, pydantic v2, structlog, pytest + pytest-asyncio, Ruff + mypy strict

---

## 文件结构总览

### 创建清单

| 文件 | 职责 |
|------|------|
| `pyproject.toml` | 项目元数据、依赖、工具配置 |
| `src/hcode_claude/__init__.py` | 顶层包标识 |
| `src/hcode_claude/core/__init__.py` | `__version__ = "0.0.1"` |
| `src/hcode_claude/core/protocol/__init__.py` | 协议包子模块标识 |
| `src/hcode_claude/core/protocol/envelope.py` | JSON-RPC 2.0 信封类型 + 错误码 |
| `src/hcode_claude/core/protocol/commands.py` | Command 判别联合 (PingCommand/PongResult) |
| `src/hcode_claude/core/protocol/events.py` | Event 判别联合 (CoreStartedEvent) |
| `src/hcode_claude/core/config.py` | Config dataclass + 四级优先级加载 + structlog 初始化 |
| `src/hcode_claude/core/transport/__init__.py` | 传输包子模块标识 |
| `src/hcode_claude/core/transport/socket_server.py` | TCP NDJSON SocketServer |
| `src/hcode_claude/core/app.py` | CoreApp + run() 入口 + handle_ping |
| `src/hcode_claude/cli/__init__.py` | CLI 包子模块标识 |
| `src/hcode_claude/cli/main.py` | hcode ping / --version / --help |
| `scripts/gen_protocol_doc.py` | pydantic → WIRE_PROTOCOL.md |
| `tests/__init__.py` | 测试根包标识 |
| `tests/conftest.py` | free_port fixture + running_daemon fixture |
| `tests/core/__init__.py` | 测试 core 包标识 |
| `tests/core/protocol/__init__.py` | 测试 protocol 包标识 |
| `tests/core/protocol/test_envelope.py` | envelope 编解码测试 |
| `tests/core/protocol/test_commands.py` | commands 序列化 + discriminator 测试 |
| `tests/core/protocol/test_events.py` | events 创建 + 序列化测试 |
| `tests/core/test_config.py` | config 优先级 + 校验测试 |
| `tests/core/test_app.py` | 集成测试：启动 daemon → ping → 校验 |
| `tests/cli/__init__.py` | 测试 cli 包标识 |
| `tests/cli/test_main.py` | CLI --version / --help / --nonce 测试 |

---

### Task 1: 项目骨架 — pyproject.toml + 目录结构 + uv sync

**Files:**
- Create: `pyproject.toml`
- Create: `src/hcode_claude/__init__.py`
- Create: `src/hcode_claude/core/__init__.py`
- Create: `src/hcode_claude/core/protocol/__init__.py`
- Create: `src/hcode_claude/core/transport/__init__.py`
- Create: `src/hcode_claude/cli/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `tests/core/protocol/__init__.py`
- Create: `tests/cli/__init__.py`

- [ ] **Step 1: 写入 pyproject.toml**

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

- [ ] **Step 2: 创建所有包目录和 `__init__.py`**

```bash
mkdir -p src/hcode_claude/core/protocol src/hcode_claude/core/transport src/hcode_claude/cli tests/core/protocol tests/cli scripts
```

Write empty `__init__.py` files（Windows 兼容）：

```bash
echo. > src/hcode_claude/__init__.py
echo. > src/hcode_claude/core/__init__.py
echo. > src/hcode_claude/core/protocol/__init__.py
echo. > src/hcode_claude/core/transport/__init__.py
echo. > src/hcode_claude/cli/__init__.py
echo. > tests/__init__.py
echo. > tests/core/__init__.py
echo. > tests/core/protocol/__init__.py
echo. > tests/cli/__init__.py
```

注意：Windows 上 `echo.` 创建空文件，Unix 上用 `touch`。

- [ ] **Step 3: 写入 `src/hcode_claude/core/__init__.py` — 版本号**

```python
# Hcode daemon 和 CLI 的统一版本号
__version__ = "0.0.1"
```

- [ ] **Step 4: uv sync 安装所有依赖**

```bash
uv sync
```

Expected: 无报错，所有依赖安装成功。输出显示 `pydantic`、`python-dotenv`、`structlog`、`pytest`、`pytest-asyncio`、`ruff`、`mypy` 已安装。

- [ ] **Step 5: 验证 hcode --version 尚未可用（预期失败）**

```bash
uv run hcode --version
```

Expected: 报错（main 函数未定义），证明骨架就绪但代码未写。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: set up project skeleton with pyproject.toml and package structure"
```

---

### Task 2: 协议层 — envelope.py (TDD)

**Files:**
- Create: `tests/core/protocol/test_envelope.py`
- Create: `src/hcode_claude/core/protocol/envelope.py`

- [ ] **Step 1: 写失败测试 `tests/core/protocol/test_envelope.py`**

```python
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
    # 错误码常量
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
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/protocol/test_envelope.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'hcode_claude.core.protocol.envelope'`

- [ ] **Step 3: 实现 `src/hcode_claude/core/protocol/envelope.py`**

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/protocol/test_envelope.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/protocol/test_envelope.py src/hcode_claude/core/protocol/envelope.py
git commit -m "feat: add JSON-RPC 2.0 envelope types with error codes"
```

---

### Task 3: 协议层 — commands.py (TDD)

**Files:**
- Create: `tests/core/protocol/test_commands.py`
- Create: `src/hcode_claude/core/protocol/commands.py`

- [ ] **Step 1: 写失败测试 `tests/core/protocol/test_commands.py`**

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/protocol/test_commands.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/protocol/commands.py`**

```python
"""Command 判别联合——按 type 字段路由（S0 仅有 Ping/Pong）"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PingCommand(BaseModel):
    """core.ping 命令——请求 daemon 回应 pong"""

    type: Literal["ping"]


class PongResult(BaseModel):
    """core.ping 的成功响应体"""

    type: Literal["pong"]
    nonce: str
    server_version: str


# Command 判别联合，全系统统一按 type 字段路由
Command = Annotated[
    PingCommand,
    Field(discriminator="type"),
]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/protocol/test_commands.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/protocol/test_commands.py src/hcode_claude/core/protocol/commands.py
git commit -m "feat: add Command discriminated union (PingCommand/PongResult)"
```

---

### Task 4: 协议层 — events.py (TDD)

**Files:**
- Create: `tests/core/protocol/test_events.py`
- Create: `src/hcode_claude/core/protocol/events.py`

- [ ] **Step 1: 写失败测试 `tests/core/protocol/test_events.py`**

```python
"""Event 判别联合测试"""

import pytest
from pydantic import ValidationError

from hcode_claude.core.protocol.events import CoreStartedEvent


# 功能：验证 CoreStartedEvent 所有字段正常赋值
# 设计：构造完整 event 后断言 type/host/port/version
def test_core_started_event_fields():
    event = CoreStartedEvent(type="core.started", host="127.0.0.1", port=47201, version="0.0.1")
    assert event.type == "core.started"
    assert event.host == "127.0.0.1"
    assert event.port == 47201
    assert event.version == "0.0.1"


# 功能：验证 CoreStartedEvent 序列化到 JSON 再反序列化
# 设计：model_dump_json → json.loads，确保字段无丢失
def test_core_started_event_roundtrip():
    event = CoreStartedEvent(type="core.started", host="0.0.0.0", port=9999, version="1.2.3")
    raw = event.model_dump_json()
    import json
    obj = json.loads(raw)
    assert obj["type"] == "core.started"
    assert obj["host"] == "0.0.0.0"
    assert obj["port"] == 9999
    assert obj["version"] == "1.2.3"


# 功能：验证 CoreStartedEvent port 必须为 int
# 设计：传字符串端口号应触发 pydantic ValidationError
def test_core_started_event_port_must_be_int():
    with pytest.raises(ValidationError):
        CoreStartedEvent(type="core.started", host="127.0.0.1", port="47201", version="0.0.1")  # type: ignore[arg-type]
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/protocol/test_events.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/protocol/events.py`**

```python
"""Event 判别联合——按 type 字段路由（S0 仅有 CoreStartedEvent）"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class CoreStartedEvent(BaseModel):
    """daemon 启动完毕事件——通知日志/客户端 daemon 已就绪"""

    type: Literal["core.started"]
    host: str
    port: int
    version: str


# Event 判别联合，全系统统一按 type 字段路由
Event = Annotated[
    CoreStartedEvent,
    Field(discriminator="type"),
]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/protocol/test_events.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/protocol/test_events.py src/hcode_claude/core/protocol/events.py
git commit -m "feat: add Event discriminated union (CoreStartedEvent)"
```

---

### Task 5: 配置系统 — config.py (TDD)

**Files:**
- Create: `tests/core/test_config.py`
- Create: `src/hcode_claude/core/config.py`

- [ ] **Step 1: 写失败测试 `tests/core/test_config.py`**

```python
"""配置系统测试——四级优先级 + 校验"""

import os
import tempfile
from pathlib import Path

import pytest

from hcode_claude.core.config import Config, load_config


# 功能：验证只使用内建默认值时返回正确的 Config
# 设计：不设任何外部配置源，断言 load_config 返回内建默认值
def test_default_config_values():
    cfg = load_config()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 47201
    assert cfg.log_level == "INFO"
    assert cfg.log_file == ""
    assert cfg.log_format == "console"


# 功能：验证环境变量 HCODE_PORT 覆盖默认端口
# 设计：设置环境变量后调用 load_config，断言 port 被覆盖
def test_env_var_overrides_port(monkeypatch):
    monkeypatch.setenv("HCODE_PORT", "9999")
    cfg = load_config()
    assert cfg.port == 9999


# 功能：验证环境变量 HCODE_HOST 覆盖默认 host
# 设计：覆盖 host 为 0.0.0.0
def test_env_var_overrides_host(monkeypatch):
    monkeypatch.setenv("HCODE_HOST", "0.0.0.0")
    cfg = load_config()
    assert cfg.host == "0.0.0.0"


# 功能：验证环境变量 HCODE_LOG_LEVEL 覆盖默认级别
# 设计：设置 DEBUG 后断言生效
def test_env_var_overrides_log_level(monkeypatch):
    monkeypatch.setenv("HCODE_LOG_LEVEL", "DEBUG")
    cfg = load_config()
    assert cfg.log_level == "DEBUG"


# 功能：验证环境变量 HCODE_LOG_FILE 覆盖日志文件路径
# 设计：设为非空路径断言生效
def test_env_var_overrides_log_file(monkeypatch):
    monkeypatch.setenv("HCODE_LOG_FILE", "/tmp/hcode.log")
    cfg = load_config()
    assert cfg.log_file == "/tmp/hcode.log"


# 功能：验证环境变量 HCODE_LOG_FORMAT 覆盖日志格式
# 设计：设为 json 断言生效
def test_env_var_overrides_log_format(monkeypatch):
    monkeypatch.setenv("HCODE_LOG_FORMAT", "json")
    cfg = load_config()
    assert cfg.log_format == "json"


# 功能：验证 .env 文件被加载并覆盖默认值
# 设计：临时目录创建 .env 文件，chdir 后验证覆盖
def test_dotenv_file_overrides_default(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HCODE_PORT=8888\n")
    monkeypatch.chdir(tmp_path)
    # 清除可能存在的环境变量干扰
    monkeypatch.delenv("HCODE_PORT", raising=False)
    cfg = load_config()
    assert cfg.port == 8888


# 功能：验证用户 config.toml 被加载并覆盖默认值
# 设计：创建 ~/.hcode/config.toml，设置 HCODE_HOME 指向 tmp_path
def test_user_config_toml_overrides_default(monkeypatch, tmp_path):
    hcode_dir = tmp_path / ".hcode"
    hcode_dir.mkdir()
    config_file = hcode_dir / "config.toml"
    config_file.write_text('port = 7777\nhost = "10.0.0.1"\n')
    monkeypatch.setenv("HCODE_HOME", str(tmp_path))
    monkeypatch.delenv("HCODE_PORT", raising=False)
    monkeypatch.delenv("HCODE_HOST", raising=False)
    cfg = load_config()
    assert cfg.port == 7777
    assert cfg.host == "10.0.0.1"


# 功能：验证环境变量优先级高于 .env 和 config.toml
# 设计：三层同时设置 port，断言环境变量胜出
def test_env_var_wins_over_all(monkeypatch, tmp_path):
    hcode_dir = tmp_path / ".hcode"
    hcode_dir.mkdir()
    (hcode_dir / "config.toml").write_text('port = 1111\n')
    (tmp_path / ".env").write_text('HCODE_PORT=2222\n')
    monkeypatch.setenv("HCODE_HOME", str(tmp_path))
    monkeypatch.setenv("HCODE_PORT", "3333")
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.port == 3333


# 功能：验证未知配置 key 触发 SystemExit
# 设计：config.toml 写入未定义 key，load_config 应调用 sys.exit(1)
def test_unknown_config_key_causes_hard_exit(monkeypatch, tmp_path):
    hcode_dir = tmp_path / ".hcode"
    hcode_dir.mkdir()
    (hcode_dir / "config.toml").write_text('unknown_key = "value"\n')
    monkeypatch.setenv("HCODE_HOME", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        load_config()
    assert exc_info.value.code == 1


# 功能：验证 Config 是 frozen dataclass，不可修改
# 设计：尝试修改属性触发 FrozenInstanceError
def test_config_is_frozen():
    cfg = Config(host="127.0.0.1", port=47201, log_level="INFO", log_file="", log_format="console")
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        cfg.port = 9999  # type: ignore[misc]
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/test_config.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `src/hcode_claude/core/config.py`**

```python
"""配置系统——四级优先级：内建默认 → ~/.hcode/config.toml → .env → 环境变量"""

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

# S0 合法配置键集合
_VALID_KEYS = {"host", "port", "log_level", "log_file", "log_format"}

# 内建默认值
_DEFAULTS: dict[str, object] = {
    "host": "127.0.0.1",
    "port": 47201,
    "log_level": "INFO",
    "log_file": "",
    "log_format": "console",
}

# env var → config key 映射
_ENV_MAP = {
    "HCODE_HOST": "host",
    "HCODE_PORT": "port",
    "HCODE_LOG_LEVEL": "log_level",
    "HCODE_LOG_FILE": "log_file",
    "HCODE_LOG_FORMAT": "log_format",
}


@dataclass(frozen=True)
class Config:
    """Hcode daemon 不可变配置"""

    host: str
    port: int
    log_level: str
    log_file: str
    log_format: str


# 加载用户级 ~/.hcode/config.toml，返回键值字典
def _load_user_toml() -> dict[str, object]:
    home = os.environ.get("HCODE_HOME", str(Path.home()))
    toml_path = Path(home) / ".hcode" / "config.toml"
    if not toml_path.is_file():
        return {}
    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)
    # 类型收窄：tomllib 返回 dict[str, Any]，所有值应为基础类型
    result: dict[str, object] = {}
    for k, v in raw.items():
        if k not in _VALID_KEYS:
            print(f"Unknown config key: {k}", file=sys.stderr)
            sys.exit(1)
        result[k] = v
    return result


# 加载 .env 文件（如存在），覆盖到 env 并提取 HCODE_ 前缀变量
def _load_dotenv_values() -> dict[str, object]:
    try:
        from dotenv import dotenv_values
    except ImportError:
        return {}
    raw = dotenv_values()
    result: dict[str, object] = {}
    for env_key, config_key in _ENV_MAP.items():
        if env_key in raw:
            result[config_key] = raw[env_key]
    return result


# 从环境变量提取 HCODE_ 前缀配置
def _load_env_values() -> dict[str, object]:
    result: dict[str, object] = {}
    for env_key, config_key in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is not None:
            result[config_key] = val
    return result


# 类型转换：将字符串值转为目标字段类型
def _coerce(key: str, value: object) -> object:
    if key == "port":
        return int(value)
    return str(value)


# 加载配置：四级合并（内建默认 → ~/.hcode/config.toml → .env → 环境变量）
def load_config() -> Config:
    merged: dict[str, object] = dict(_DEFAULTS)

    # 第一层：用户 TOML
    for k, v in _load_user_toml().items():
        merged[k] = v

    # 第二层：.env
    for k, v in _load_dotenv_values().items():
        merged[k] = v

    # 第三层：环境变量（最高优先级）
    for k, v in _load_env_values().items():
        merged[k] = v

    # 类型转换
    return Config(
        host=_coerce("host", merged["host"]),
        port=_coerce("port", merged["port"]),
        log_level=_coerce("log_level", merged["log_level"]),
        log_file=_coerce("log_file", merged["log_file"]),
        log_format=_coerce("log_format", merged["log_format"]),
    )


# 根据 Config 初始化 structlog
def setup_logging(cfg: Config) -> None:
    import logging

    import structlog

    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level)

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
        cache_logger_on_first_use=True,
    )

    if cfg.log_file:
        file_handler = logging.FileHandler(cfg.log_file)
        logging.getLogger().addHandler(file_handler)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/test_config.py -v
```

Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/test_config.py src/hcode_claude/core/config.py
git commit -m "feat: add config system with four-level priority and structlog setup"
```

---

### Task 6: 传输层 — socket_server.py (TDD)

**Files:**
- Create: `src/hcode_claude/core/transport/socket_server.py`
- Note: socket_server 的测试通过 Task 7 的集成测试覆盖（需要真实 TCP 连接，单元测试 mock 价值不大）

- [ ] **Step 1: 写完成后运行的验证测试（先写，后实现）**

SocketServer 的单元测试价值有限——核心行为是 bind/accept/dispatch，mock 掉 asyncio 就只测赋值了。因此这一步"先写测试"的形式是：写出集成测试的 daemon 启动部分（与 Task 7 共用 conftest），然后实现 socket_server 使得 daemon 能启动。

先写 `tests/conftest.py`：

```python
"""测试 fixtures——free_port 和 running_daemon"""

import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


# 返回空闲端口号：bind port 0 → getsockname → close → 返回端口号
@pytest.fixture
def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
```

- [ ] **Step 2: 实现 `src/hcode_claude/core/transport/socket_server.py`**

```python
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
Handler = Callable[[dict], Awaitable[object]]


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
            return SuccessResponse(id=req_id, result=result)
        except Exception as exc:
            return ErrorResponse(
                id=req_id,
                error=ErrorDetail(
                    code=INTERNAL_ERROR,
                    message=str(exc),
                ),
            )
```

- [ ] **Step 3: 验证代码可以被 import（因还没有 daemon 集成，先做语法级验证）**

```bash
uv run python -c "from hcode_claude.core.transport.socket_server import SocketServer; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py src/hcode_claude/core/transport/socket_server.py
git commit -m "feat: add TCP NDJSON SocketServer with JSON-RPC dispatch"
```

---

### Task 7: 守护进程入口 + 集成测试 (TDD)

**Files:**
- Create: `src/hcode_claude/core/app.py`
- Create: `tests/core/test_app.py`

- [ ] **Step 1: 先写集成测试 `tests/core/test_app.py`**

```python
"""集成测试：启动 daemon → core.ping → 校验 pong"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


# 功能：验证完整的 ping/pong 流程——daemon 启动 → 发 ping → 收 pong
# 设计：用 free_port 启动子进程 daemon，轮询 TCP 直到可达，发请求并验证响应
@pytest.mark.asyncio
async def test_daemon_ping_pong(free_port: int, tmp_path: Path):
    # 确保 daemon 有代码可跑（PYTHONPATH=src 使其能找到 hcode_claude）
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["HCODE_PORT"] = str(free_port)
    env["HCODE_LOG_FILE"] = str(tmp_path / "hcode.log")
    env["HCODE_HOME"] = str(tmp_path)  # 避免读取真实的 ~/.hcode/config.toml

    # 启动 daemon 子进程
    proc = subprocess.Popen(
        [sys.executable, "-m", "hcode_claude.core.app"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # 轮询等待 daemon TCP 就绪（最多 5 秒）
        connected = False
        for _ in range(50):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", free_port),
                    timeout=0.3,
                )
                connected = True
                break
            except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
                if proc.poll() is not None:
                    # daemon 已经挂了
                    stdout, stderr = proc.communicate()
                    pytest.fail(
                        f"Daemon exited early (code={proc.returncode})\n"
                        f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
                    )
                await asyncio.sleep(0.1)

        assert connected, "Cannot connect to daemon after 5s"

        # 发送 core.ping
        nonce = "test-nonce-123"
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": nonce,
            "method": "core.ping",
            "params": {"nonce": nonce},
        }) + "\n"
        writer.write(request.encode())
        await writer.drain()

        # 读取响应
        line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        response = json.loads(line.decode())

        writer.close()

        # 校验响应
        assert "result" in response, f"Expected success, got: {response}"
        assert response["id"] == nonce
        assert response["result"]["type"] == "pong"
        assert response["result"]["nonce"] == nonce
        assert response["result"]["server_version"] == "0.0.1"

    finally:
        # 不管测试结果如何都要杀掉 daemon（跨平台 terminate）
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/test_app.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'hcode_claude.core.app'` 或 daemon 启动失败

- [ ] **Step 3: 实现 `src/hcode_claude/core/app.py`**

```python
"""Hcode daemon 入口——CoreApp 组装并运行整个生命周期"""

import asyncio
import signal

import structlog

from hcode_claude.core import __version__
from hcode_claude.core.config import Config, load_config, setup_logging
from hcode_claude.core.protocol.commands import PongResult
from hcode_claude.core.protocol.events import CoreStartedEvent
from hcode_claude.core.transport.socket_server import SocketServer


class CoreApp:
    """Hcode daemon 应用主体——组装配置、日志、Server、handler，管理生命周期"""

    # 启动 daemon 完整生命周期
    async def run(self) -> None:
        # 1. 加载配置
        cfg = load_config()

        # 2. 初始化 structlog
        setup_logging(cfg)
        logger = structlog.get_logger()

        # 3. 创建 SocketServer
        server = SocketServer(cfg.host, cfg.port)

        # 4. 注册 core.ping handler
        server.register("core.ping", self._handle_ping)

        # 5. 端口探测 + bind
        await server.start()

        # 6. 发 CoreStartedEvent
        event = CoreStartedEvent(
            type="core.started",
            host=cfg.host,
            port=cfg.port,
            version=__version__,
        )
        logger.info("core_started", **event.model_dump())

        # 7. 挂起等待关闭信号
        shutdown_event = asyncio.Event()
        self._setup_signal_handlers(shutdown_event)
        await shutdown_event.wait()
        logger.info("shutting_down")

        # 8. 优雅关闭
        await server.stop()

    # 处理 core.ping 请求：提取 nonce，返回 PongResult
    async def _handle_ping(self, params: dict) -> PongResult:
        nonce = params.get("nonce", "") if isinstance(params, dict) else ""
        return PongResult(
            type="pong",
            nonce=nonce,
            server_version=__version__,
        )

    # 注册 SIGINT/SIGTERM handler 到 event loop
    def _setup_signal_handlers(self, shutdown_event: asyncio.Event) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_event.set)


# 模块级入口，供 pyproject.scripts 中的 hcode-core 调用
def run() -> None:
    app = CoreApp()
    asyncio.run(app.run())


# 直接 python -m hcode_claude.core.app 时也启动 daemon
if __name__ == "__main__":
    run()
```

- [ ] **Step 4: 运行集成测试验证通过**

```bash
uv run pytest tests/core/test_app.py -v
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/hcode_claude/core/app.py tests/core/test_app.py
git commit -m "feat: add CoreApp daemon with ping handler and integration test"
```

---

### Task 8: CLI 入口 — main.py (TDD)

**Files:**
- Create: `tests/cli/test_main.py`
- Create: `src/hcode_claude/cli/main.py`

- [ ] **Step 1: 写失败测试 `tests/cli/test_main.py`**

```python
"""CLI 入口测试"""

import os
import subprocess
import sys

import pytest

# 确保 src/ 在 PYTHONPATH 中——uv sync 不做 editable install，子进程需要显式路径
_TESTS_ENV = os.environ.copy()
_TESTS_ENV["PYTHONPATH"] = "src"


# 功能：验证 hcode --version 输出 "hcode v0.0.1"
# 设计：用 subprocess 调用 python -m hcode_claude.cli.main --version，PYTHONPATH=src
def test_cli_version():
    result = subprocess.run(
        [sys.executable, "-m", "hcode_claude.cli.main", "--version"],
        capture_output=True,
        text=True,
        env=_TESTS_ENV,
    )
    assert result.returncode == 0
    assert "hcode v0.0.1" in result.stdout.strip()


# 功能：验证 hcode --help 输出使用说明
# 设计：无参数调用默认显示 help，PYTHONPATH=src
def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "hcode_claude.cli.main", "--help"],
        capture_output=True,
        text=True,
        env=_TESTS_ENV,
    )
    assert result.returncode == 0
    assert "hcode ping" in result.stdout


# 功能：验证 hcode ping 不带 daemon 运行时输出错误
# 设计：daemon 未启动，应报连接失败并 exit 1
def test_ping_without_daemon_fails():
    result = subprocess.run(
        [
            sys.executable, "-m", "hcode_claude.cli.main",
            "ping", "--port", "1",
            "--host", "127.0.0.1",
        ],
        capture_output=True,
        text=True,
        env=_TESTS_ENV,
    )
    assert result.returncode != 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/cli/test_main.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 `src/hcode_claude/cli/main.py`**

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/cli/test_main.py -v
```

Expected: 3 passed

- [ ] **Step 5: 手动验证 hcode --version 和 hcode --help**

```bash
uv run hcode --version
```

Expected: `hcode v0.0.1`

```bash
uv run hcode --help
```

Expected: 打印使用说明

- [ ] **Step 6: Commit**

```bash
git add tests/cli/test_main.py src/hcode_claude/cli/main.py
git commit -m "feat: add hcode CLI with ping/--version/--help commands"
```

---

### Task 9: 协议文档生成器 — gen_protocol_doc.py

**Files:**
- Create: `scripts/gen_protocol_doc.py`

- [ ] **Step 1: 实现 `scripts/gen_protocol_doc.py`**

```python
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
        f"> 生成自: `src/hcode_claude/core/protocol/`",
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
    lines.append('→ {"jsonrpc":"2.0","id":"abc123","method":"core.ping","params":{"nonce":"abc123"}}')
    lines.append('← {"jsonrpc":"2.0","id":"abc123","result":{"type":"pong","nonce":"abc123","server_version":"0.0.1"}}')
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
            print("WIRE_PROTOCOL.md is out of date — run python scripts/gen_protocol_doc.py to regenerate")
            sys.exit(1)
        print("WIRE_PROTOCOL.md is up to date")
    else:
        content = generate()
        output_path.write_text(content, encoding="utf-8")
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行脚本生成 WIRE_PROTOCOL.md**

```bash
uv run python scripts/gen_protocol_doc.py
```

Expected: `Wrote .../WIRE_PROTOCOL.md`

- [ ] **Step 3: 运行 --check 模式验证一致性**

```bash
uv run python scripts/gen_protocol_doc.py --check
```

Expected: `WIRE_PROTOCOL.md is up to date`

- [ ] **Step 4: Commit**

```bash
git add scripts/gen_protocol_doc.py WIRE_PROTOCOL.md
git commit -m "feat: add protocol doc generator with --check CI mode"
```

---

### Task 10: 全量测试 + Lint 收尾

**Files:** None new

- [ ] **Step 1: 运行全量测试**

```bash
uv run pytest tests/ -v
```

Expected: 所有测试通过

- [ ] **Step 2: 运行 Ruff lint + import 排序**

```bash
uv run ruff check src/ tests/ scripts/
```

Expected: 无错误（或仅少量需修复）

- [ ] **Step 3: 自动修复 Ruff 问题**

```bash
uv run ruff check --fix src/ tests/ scripts/
```

- [ ] **Step 4: 运行 mypy 类型检查**

```bash
uv run mypy src/
```

Expected: 无错误（或少量需修复）

- [ ] **Step 5: 修复 mypy 类型错误（如有）**

检查并修复。常见问题：
- `dict` 未标注类型 → `dict[str, Any]`
- `Callable` 未标注参数 → `Handler = Callable[[dict], Awaitable[object]]`

- [ ] **Step 6: 运行端到端验证**

终端 1 启动 daemon：
```bash
uv run hcode-core
```
Expected: 日志显示 core_started 事件

终端 2 发送 ping：
```bash
uv run hcode ping
```
Expected: `pong from v0.0.1 (nonce=xxxxxxxx)`

- [ ] **Step 7: 最终 Commit**

```bash
git add -A
git commit -m "chore: final lint fixes and full test pass"
```

---

### Task 11 (收尾): 运行全量测试确认所有功能通过

- [ ] **Step 1: 全量测试 + 验证**

```bash
uv run pytest tests/ -v
uv run ruff check src/ tests/ scripts/
uv run mypy src/
uv run python scripts/gen_protocol_doc.py --check
```

Expected: 全部通过
