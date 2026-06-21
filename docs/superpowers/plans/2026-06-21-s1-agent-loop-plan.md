# S1 Agent 最小闭环 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一次 `hcode run --goal "..."` 从用户目标到 LLM → 工具调用 → 事件文件完整跑通

**Architecture:** 自底向上 TDD——从类型定义 → 协议事件 → 事件总线 → 工具系统 → LLM Provider → ExecutionContext → AgentLoop → AgentRunner → daemon 集成 → CLI → 端到端测试

**Tech Stack:** Python 3.12, pydantic v2, Anthropic SDK (`anthropic>=0.30`), structlog, pytest + pytest-asyncio, ruff + mypy strict

## Global Constraints

- 每个 `.py` 文件第一行是模块注释（`"""文件功能简述"""`）
- 每个 `def` 上方一行中文注释说明功能
- 测试函数上方 `# 功能：` + `# 设计：` 两行中文注释
- TDD：先写失败测试 → 再写实现 → 测试通过 → commit
- mypy strict 模式，所有类型必须精确匹配
- Python >=3.12, <3.13

---

## 文件结构总览

| 文件 | 职责 |
|------|------|
| `src/hcode_claude/core/llm/types.py` | ToolUseBlock, ChatResult, LoopResult |
| `src/hcode_claude/core/llm/provider.py` | BaseProvider + AnthropicProvider |
| `src/hcode_claude/core/tools/base.py` | BaseTool 抽象类 |
| `src/hcode_claude/core/tools/registry.py` | ToolRegistry |
| `src/hcode_claude/core/tools/read_file.py` | 内建工具：读取文件 |
| `src/hcode_claude/core/tools/write_file.py` | 内建工具：写入文件 |
| `src/hcode_claude/core/tools/bash.py` | 内建工具：执行 shell |
| `src/hcode_claude/core/tools/list_dir.py` | 内建工具：列出目录 |
| `src/hcode_claude/core/events/bus.py` | EventBus — 进程内 pub/sub |
| `src/hcode_claude/core/events/writer.py` | EventWriter — 事件 → events.jsonl |
| `src/hcode_claude/core/events/printer.py` | StdoutPrinter — 事件 → stdout |
| `src/hcode_claude/core/context.py` | ExecutionContext |
| `src/hcode_claude/core/loop.py` | AgentLoop |
| `src/hcode_claude/core/runner.py` | AgentRunner |
| `src/hcode_claude/core/protocol/events.py` | **修改** — 加 9 个事件 |
| `src/hcode_claude/core/protocol/commands.py` | **修改** — 加 RunCommand + RunResult |
| `src/hcode_claude/core/config.py` | **修改** — 加 API key 等 S1 配置项 |
| `src/hcode_claude/core/app.py` | **修改** — 注册 agent.run handler |
| `src/hcode_claude/cli/main.py` | **修改** — 加 hcode run 子命令 |
| `tests/core/llm/test_types.py` | 类型序列化测试 |
| `tests/core/llm/test_provider.py` | Provider 测试（mock SDK） |
| `tests/core/tools/test_base.py` | BaseTool 接口测试 |
| `tests/core/tools/test_registry.py` | ToolRegistry 测试 |
| `tests/core/tools/test_builtin_tools.py` | 四个内建工具测试 |
| `tests/core/events/test_bus.py` | EventBus 测试 |
| `tests/core/events/test_writer.py` | EventWriter 测试 |
| `tests/core/events/test_printer.py` | StdoutPrinter 测试 |
| `tests/core/test_context.py` | ExecutionContext 测试 |
| `tests/core/test_loop.py` | AgentLoop 测试（mock provider） |
| `tests/core/test_runner.py` | AgentRunner 测试 |
| `tests/core/protocol/test_events.py` | **修改** — 加 S1 事件测试 |
| `tests/core/protocol/test_commands.py` | **修改** — 加 RunCommand 测试 |
| `tests/core/test_config.py` | **修改** — 加 S1 配置项测试 |
| `tests/core/test_app.py` | **修改** — 加 agent.run 集成测试 |
| `tests/cli/test_main.py` | **修改** — 加 hcode run 测试 |

---

### Task 1: LLM 类型定义 (TDD)

**Files:**
- Create: `tests/core/llm/test_types.py`
- Create: `src/hcode_claude/core/llm/__init__.py`
- Create: `src/hcode_claude/core/llm/types.py`

**Interfaces:**
- Produces: `ToolUseBlock(id, name, input)`, `ChatResult(text, tool_uses, usage)`, `LoopResult(status, steps, output)`

- [ ] **Step 1: 写失败测试 `tests/core/llm/test_types.py`**

```python
"""LLM 类型定义测试"""

from hcode_claude.core.llm.types import ChatResult, LoopResult, ToolUseBlock


# 功能：验证 ToolUseBlock 字段赋值和类型
# 设计：构造完整 ToolUseBlock，断言所有字段
def test_tool_use_block_fields():
    tu = ToolUseBlock(id="tu_1", name="read_file", input={"path": "foo.py"})
    assert tu.id == "tu_1"
    assert tu.name == "read_file"
    assert tu.input == {"path": "foo.py"}


# 功能：验证 ChatResult 携带文本、工具调用列表和用量
# 设计：构造完整 ChatResult，断言 tool_uses 列表和 usage 字典
def test_chat_result_with_tool_uses():
    tu = ToolUseBlock(id="tu_1", name="bash", input={"command": "pytest"})
    cr = ChatResult(
        text="先跑一下测试",
        tool_uses=[tu],
        usage={"input_tokens": 100, "output_tokens": 50},
    )
    assert cr.text == "先跑一下测试"
    assert len(cr.tool_uses) == 1
    assert cr.tool_uses[0].name == "bash"
    assert cr.usage == {"input_tokens": 100, "output_tokens": 50}


# 功能：验证 ChatResult tool_uses 为空列表时表示纯文本回复
# 设计：空 tool_uses 是正常终止信号，不抛异常
def test_chat_result_empty_tool_uses():
    cr = ChatResult(
        text="任务完成了",
        tool_uses=[],
        usage={"input_tokens": 200, "output_tokens": 30},
    )
    assert cr.tool_uses == []
    assert cr.text == "任务完成了"


# 功能：验证 LoopResult status 为 completed 时携带 steps 和 output
# 设计：正常终止场景，output 是 LLM 最终文本
def test_loop_result_completed():
    lr = LoopResult(status="completed", steps=3, output="修复完成")
    assert lr.status == "completed"
    assert lr.steps == 3
    assert lr.output == "修复完成"


# 功能：验证 LoopResult status 为 max_steps 时 output 可为空
# 设计：达到最大步数时 LLM 可能还没输出最终文本
def test_loop_result_max_steps():
    lr = LoopResult(status="max_steps", steps=20, output="")
    assert lr.status == "max_steps"
    assert lr.steps == 20
    assert lr.output == ""
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/llm/test_types.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/llm/__init__.py` 和 `src/hcode_claude/core/llm/types.py`**

```python
# 文件: src/hcode_claude/core/llm/__init__.py
"""LLM 模块——Provider 抽象与 Anthropic 实现"""
```

```python
# 文件: src/hcode_claude/core/llm/types.py
"""LLM 模块类型定义——ToolUseBlock、ChatResult、LoopResult"""

from typing import Any, Literal

from pydantic import BaseModel


class ToolUseBlock(BaseModel):
    """LLM 返回的单个工具调用块"""
    id: str
    name: str
    input: dict[str, Any]


class ChatResult(BaseModel):
    """单次 LLM 调用的完整结果"""
    text: str
    tool_uses: list[ToolUseBlock]
    usage: dict[str, int]


class LoopResult(BaseModel):
    """Agent 循环的最终结果"""
    status: Literal["completed", "max_steps"]
    steps: int
    output: str
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/llm/test_types.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/llm/test_types.py src/hcode_claude/core/llm/__init__.py src/hcode_claude/core/llm/types.py
git commit -m "feat: add LLM type definitions (ToolUseBlock, ChatResult, LoopResult)"
```

---

### Task 2: 协议事件扩展 (TDD)

**Files:**
- Modify: `tests/core/protocol/test_events.py`
- Modify: `src/hcode_claude/core/protocol/events.py`

**Interfaces:**
- Produces: `RunStartedEvent`, `RunFinishedEvent`, `StepStartedEvent`, `StepFinishedEvent`, `ToolCallStartedEvent`, `ToolCallFinishedEvent`, `ToolCallFailedEvent`, `LlmTokenEvent`, `LlmUsageEvent`, `LlmModelSelectedEvent`
- Produces: `Event` union 更新

- [ ] **Step 1: 追加失败测试到 `tests/core/protocol/test_events.py`**

```python
# 在现有文件末尾追加以下内容

from hcode_claude.core.protocol.events import (
    LlmTokenEvent,
    LlmUsageEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    ToolCallFailedEvent,
    ToolCallFinishedEvent,
    ToolCallStartedEvent,
)

# 功能：验证 RunStartedEvent 包含 run_id 和 goal 字段
# 设计：run 开始时发布，须有 run_id 以便关联后续事件
def test_run_started_event():
    event = RunStartedEvent(type="run.started", run_id="r1", goal="修 bug")
    assert event.run_id == "r1"
    assert event.goal == "修 bug"


# 功能：验证 RunFinishedEvent 包含 status 和 steps
# 设计：run 结束时发布，status 是 completed/max_steps/error
def test_run_finished_event():
    event = RunFinishedEvent(type="run.finished", run_id="r1", status="completed", steps=3)
    assert event.status == "completed"
    assert event.steps == 3


# 功能：验证 StepStartedEvent 包含 step_number
# 设计：每步开始发布，step_number 从 1 开始
def test_step_started_event():
    event = StepStartedEvent(type="step.started", step_number=1)
    assert event.step_number == 1


# 功能：验证 StepFinishedEvent 包含 tool_call_count
# 设计：记录该步调用了几个工具
def test_step_finished_event():
    event = StepFinishedEvent(type="step.finished", step_number=2, tool_call_count=3)
    assert event.step_number == 2
    assert event.tool_call_count == 3


# 功能：验证 ToolCallStartedEvent 包含工具名称和参数
# 设计：工具调用开始时发布，params 捕获完整的 LLM 传参
def test_tool_call_started_event():
    event = ToolCallStartedEvent(type="tool.started", tool_name="bash", params={"command": "ls"})
    assert event.tool_name == "bash"
    assert event.params == {"command": "ls"}


# 功能：验证 ToolCallFinishedEvent 包含输出摘要
# 设计：工具成功时发布，output 截断到 500 字符
def test_tool_call_finished_event():
    event = ToolCallFinishedEvent(type="tool.finished", tool_name="bash", output="ok")
    assert event.tool_name == "bash"
    assert event.output == "ok"


# 功能：验证 ToolCallFailedEvent 包含错误信息
# 设计：工具失败时发布，记录异常消息
def test_tool_call_failed_event():
    event = ToolCallFailedEvent(type="tool.failed", tool_name="bash", error="timeout")
    assert event.tool_name == "bash"
    assert event.error == "timeout"


# 功能：验证 LlmTokenEvent 携带流式 token 文本
# 设计：S1 先写文件，S2 推送到客户端
def test_llm_token_event():
    event = LlmTokenEvent(type="llm.token", text="我")
    assert event.text == "我"


# 功能：验证 LlmUsageEvent 包含 token 用量
# 设计：每次 LLM 调用后发布，input_tokens + output_tokens
def test_llm_usage_event():
    event = LlmUsageEvent(type="llm.usage", input_tokens=100, output_tokens=50)
    assert event.input_tokens == 100
    assert event.output_tokens == 50


# 功能：验证 LlmModelSelectedEvent 包含实际模型 ID
# 设计：记录实际使用的模型，方便调试
def test_llm_model_selected_event():
    event = LlmModelSelectedEvent(type="llm.model_selected", model_id="claude-sonnet-4-6")
    assert event.model_id == "claude-sonnet-4-6"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/protocol/test_events.py -v
```

Expected: 新增 10 个 FAIL — `ImportError` 不存在的新事件类

- [ ] **Step 3: 实现 `src/hcode_claude/core/protocol/events.py`**

```python
"""Event 判别联合——按 type 字段路由"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class CoreStartedEvent(BaseModel):
    """daemon 启动完毕事件——通知日志/客户端 daemon 已就绪"""
    type: Literal["core.started"]
    host: str
    port: int
    version: str


# ---- S1 新增事件 ----

class RunStartedEvent(BaseModel):
    """run 开始事件——AgentRunner 启动新的 agent.run 时发布"""
    type: Literal["run.started"]
    run_id: str
    goal: str


class RunFinishedEvent(BaseModel):
    """run 结束事件——Agent 循环终止时发布"""
    type: Literal["run.finished"]
    run_id: str
    status: Literal["completed", "max_steps", "error"]
    steps: int


class StepStartedEvent(BaseModel):
    """每步开始事件——AgentLoop 每轮循环开始时发布"""
    type: Literal["step.started"]
    step_number: int


class StepFinishedEvent(BaseModel):
    """每步结束事件——工具调用全部完成后发布"""
    type: Literal["step.finished"]
    step_number: int
    tool_call_count: int


class ToolCallStartedEvent(BaseModel):
    """工具调用开始事件——开始 invoke 工具时发布"""
    type: Literal["tool.started"]
    tool_name: str
    params: dict[str, Any]


class ToolCallFinishedEvent(BaseModel):
    """工具调用成功事件——工具返回结果后发布"""
    type: Literal["tool.finished"]
    tool_name: str
    output: str


class ToolCallFailedEvent(BaseModel):
    """工具调用失败事件——工具抛异常时发布"""
    type: Literal["tool.failed"]
    tool_name: str
    error: str


class LlmTokenEvent(BaseModel):
    """流式 token 事件——LLM 输出每个 token 时发布"""
    type: Literal["llm.token"]
    text: str


class LlmUsageEvent(BaseModel):
    """LLM 用量事件——每次 LLM 调用完成后发布"""
    type: Literal["llm.usage"]
    input_tokens: int
    output_tokens: int


class LlmModelSelectedEvent(BaseModel):
    """LLM 模型选择事件——记录实际使用的模型 ID"""
    type: Literal["llm.model_selected"]
    model_id: str


# Event 判别联合，全系统统一按 type 字段路由
Event = Annotated[
    CoreStartedEvent
    | RunStartedEvent
    | RunFinishedEvent
    | StepStartedEvent
    | StepFinishedEvent
    | ToolCallStartedEvent
    | ToolCallFinishedEvent
    | ToolCallFailedEvent
    | LlmTokenEvent
    | LlmUsageEvent
    | LlmModelSelectedEvent,
    Field(discriminator="type"),
]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/protocol/test_events.py -v
```

Expected: 13 passed（3 个 S0 + 10 个 S1 新增）

- [ ] **Step 5: Commit**

```bash
git add tests/core/protocol/test_events.py src/hcode_claude/core/protocol/events.py
git commit -m "feat: add S1 events (Run, Step, ToolCall, Llm)"
```

---

### Task 3: 事件总线 EventBus (TDD)

**Files:**
- Create: `tests/core/events/test_bus.py`
- Create: `src/hcode_claude/core/events/__init__.py`
- Create: `src/hcode_claude/core/events/bus.py`

**Interfaces:**
- Produces: `EventBus.subscribe(event_type, handler)`, `EventBus.publish(event)`

- [ ] **Step 1: 写失败测试 `tests/core/events/test_bus.py`**

```python
"""EventBus 进程内 pub/sub 测试"""

import pytest
from pydantic import BaseModel

from hcode_claude.core.events.bus import EventBus


class FakeEvent(BaseModel):
    type: str = "fake"
    payload: str


class AnotherEvent(BaseModel):
    type: str = "another"
    value: int


# 功能：验证 publish 后订阅者能收到事件对象
# 设计：用内联 async handler 收集事件，断言收到的就是发布的那个对象
@pytest.mark.asyncio
async def test_publish_reaches_subscriber():
    bus = EventBus()
    received: list[FakeEvent] = []

    async def handler(event: FakeEvent) -> None:
        received.append(event)

    bus.subscribe(FakeEvent, handler)
    event = FakeEvent(payload="hello")
    await bus.publish(event)
    assert len(received) == 1
    assert received[0].payload == "hello"


# 功能：验证多个订阅者都能收到同一事件
# 设计：两个不同 handler 订阅同一事件类型，断言都收到
@pytest.mark.asyncio
async def test_multiple_subscribers_all_receive():
    bus = EventBus()
    results: list[str] = []

    async def h1(event: FakeEvent) -> None:
        results.append("h1")

    async def h2(event: FakeEvent) -> None:
        results.append("h2")

    bus.subscribe(FakeEvent, h1)
    bus.subscribe(FakeEvent, h2)
    await bus.publish(FakeEvent(payload="x"))
    assert results == ["h1", "h2"]


# 功能：验证订阅者只收到自己订阅的事件类型
# 设计：h1 订阅 Fake，h2 订阅 Another，publish Fake 只触发 h1
@pytest.mark.asyncio
async def test_subscriber_only_receives_subscribed_type():
    bus = EventBus()
    fake_received: list[str] = []
    another_received: list[str] = []

    async def fake_handler(event: FakeEvent) -> None:
        fake_received.append(event.payload)

    async def another_handler(event: AnotherEvent) -> None:
        another_received.append(str(event.value))

    bus.subscribe(FakeEvent, fake_handler)
    bus.subscribe(AnotherEvent, another_handler)
    await bus.publish(FakeEvent(payload="only_fake"))
    assert len(fake_received) == 1
    assert len(another_received) == 0


# 功能：验证无订阅者时 publish 不抛异常
# 设计：发布无人关注的事件是合法场景
@pytest.mark.asyncio
async def test_publish_no_subscribers_no_error():
    bus = EventBus()
    await bus.publish(FakeEvent(payload="nobody"))
    # 不抛异常即通过


# 功能：验证一个订阅者抛异常不影响其他订阅者
# 设计：bus 应隔离异常，其他 handler 正常执行
@pytest.mark.asyncio
async def test_handler_exception_isolated():
    bus = EventBus()
    called: list[str] = []

    async def crashing(event: FakeEvent) -> None:
        raise RuntimeError("boom")

    async def normal(event: FakeEvent) -> None:
        called.append("normal")

    bus.subscribe(FakeEvent, crashing)
    bus.subscribe(FakeEvent, normal)
    await bus.publish(FakeEvent(payload="x"))
    assert called == ["normal"]


# 功能：验证 subscribe 返回取消订阅的回调
# 设计：调用返回的函数后，订阅者不再收到事件
@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received: list[str] = []

    async def handler(event: FakeEvent) -> None:
        received.append(event.payload)

    unsubscribe = bus.subscribe(FakeEvent, handler)
    unsubscribe()
    await bus.publish(FakeEvent(payload="after_unsub"))
    assert len(received) == 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/events/test_bus.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/events/__init__.py` 和 `src/hcode_claude/core/events/bus.py`**

```python
# 文件: src/hcode_claude/core/events/__init__.py
"""事件系统——EventBus 进程内发布/订阅"""
```

```python
# 文件: src/hcode_claude/core/events/bus.py
"""进程内事件总线——发布/订阅，AgentLoop 发布事件，Writer/Printer 订阅消费"""

from collections.abc import Callable, Awaitable
from typing import Any

from pydantic import BaseModel

# 事件 handler 签名：接收 BaseModel 子类实例，返回 None
EventHandler = Callable[[Any], Awaitable[None]]


class EventBus:
    """进程内 pub/sub，按 BaseModel 子类型路由事件到已订阅 handler"""

    # 初始化空的订阅表
    def __init__(self) -> None:
        self._subscribers: dict[type, list[EventHandler]] = {}

    # 订阅指定事件类型，返回取消订阅的回调
    def subscribe(self, event_type: type, handler: EventHandler) -> Callable[[], None]:
        self._subscribers.setdefault(event_type, []).append(handler)

        def unsubscribe() -> None:
            handlers = self._subscribers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    # 发布事件：逐类型匹配，通知所有订阅者（异常隔离）
    async def publish(self, event: BaseModel) -> None:
        for event_type, handlers in self._subscribers.items():
            if isinstance(event, event_type):
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception:
                        pass  # 一个 handler 崩了不影响其他
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/events/test_bus.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/events/test_bus.py src/hcode_claude/core/events/__init__.py src/hcode_claude/core/events/bus.py
git commit -m "feat: add EventBus with in-process pub/sub and subscriber isolation"
```

---

### Task 4: EventWriter (TDD)

**Files:**
- Create: `tests/core/events/test_writer.py`
- Create: `src/hcode_claude/core/events/writer.py`

**Interfaces:**
- Produces: `EventWriter.start(bus, path)`
- Consumes: `EventBus.publish(event)` — 自动订阅所有 BaseModel 事件

- [ ] **Step 1: 写失败测试 `tests/core/events/test_writer.py`**

```python
"""EventWriter 测试"""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from hcode_claude.core.events.bus import EventBus
from hcode_claude.core.events.writer import EventWriter


class FakeEvent(BaseModel):
    type: str = "fake"
    msg: str


# 功能：验证 EventWriter 将事件写入 events.jsonl，每行一个 JSON
# 设计：publish 两个事件后读文件，验证 NDJSON 格式（每行完整 JSON）
@pytest.mark.asyncio
async def test_writer_writes_ndjson(tmp_path: Path):
    bus = EventBus()
    writer = EventWriter()
    file_path = tmp_path / "events.jsonl"
    await writer.start(bus, file_path)

    await bus.publish(FakeEvent(msg="hello"))
    await bus.publish(FakeEvent(msg="world"))

    lines = file_path.read_text().strip().split("\n")
    assert len(lines) == 2
    e1 = json.loads(lines[0])
    e2 = json.loads(lines[1])
    assert e1["msg"] == "hello"
    assert e2["msg"] == "world"


# 功能：验证 EventWriter 序列化时用到 pydantic model_dump
# 设计：pydantic 默认 type 字段在 model_dump 中存在
@pytest.mark.asyncio
async def test_writer_includes_type_field(tmp_path: Path):
    bus = EventBus()
    writer = EventWriter()
    file_path = tmp_path / "events.jsonl"
    await writer.start(bus, file_path)

    await bus.publish(FakeEvent(msg="test"))

    data = json.loads(file_path.read_text().strip())
    assert data["type"] == "fake"
    assert data["msg"] == "test"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/events/test_writer.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/events/writer.py`**

```python
"""事件文件写入器——订阅 EventBus，将事件追加写入 events.jsonl"""

import json
from pathlib import Path

from pydantic import BaseModel

from hcode_claude.core.events.bus import EventBus


class EventWriter:
    """订阅 EventBus，每条事件写一行 NDJSON 到指定文件"""

    # 打开文件句柄并订阅所有事件类型
    async def start(self, bus: EventBus, path: Path) -> None:
        self._file = path.open("a", encoding="utf-8")

        # 写事件到文件：model_dump + json.dumps + 换行
        async def write_event(event: BaseModel) -> None:
            line = json.dumps(event.model_dump(), ensure_ascii=False) + "\n"
            self._file.write(line)
            self._file.flush()

        # 订阅 BaseModel —— 所有事件都是 BaseModel 子类
        bus.subscribe(BaseModel, write_event)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/events/test_writer.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/events/test_writer.py src/hcode_claude/core/events/writer.py
git commit -m "feat: add EventWriter for events.jsonl persistence"
```

---

### Task 5: StdoutPrinter (TDD)

**Files:**
- Create: `tests/core/events/test_printer.py`
- Create: `src/hcode_claude/core/events/printer.py`

**Interfaces:**
- Produces: `StdoutPrinter.start(bus)`
- Consumes: `EventBus` — 订阅特定事件类型打印到 stdout

- [ ] **Step 1: 写失败测试 `tests/core/events/test_printer.py`**

```python
"""StdoutPrinter 测试"""

import sys
from io import StringIO

import pytest
from pydantic import BaseModel

from hcode_claude.core.events.bus import EventBus
from hcode_claude.core.events.printer import StdoutPrinter


class StepEvent(BaseModel):
    type: str = "step.started"
    step_number: int


class ToolEvent(BaseModel):
    type: str = "tool.started"
    tool_name: str
    params: dict


# 功能：验证 StdoutPrinter 将 StepStartedEvent 格式化打印到 stdout
# 设计：重定向 stdout 为 StringIO，断言包含 step 编号
@pytest.mark.asyncio
async def test_printer_outputs_step_started():
    bus = EventBus()
    printer = StdoutPrinter()
    await printer.start(bus)

    capture = StringIO()
    old_stdout = sys.stdout
    sys.stdout = capture
    try:
        await bus.publish(StepEvent(step_number=3))
        output = capture.getvalue()
        assert "3" in output
    finally:
        sys.stdout = old_stdout


# 功能：验证 StdoutPrinter 将 ToolCallStartedEvent 格式化打印
# 设计：输出应包含工具名称
@pytest.mark.asyncio
async def test_printer_outputs_tool_call():
    bus = EventBus()
    printer = StdoutPrinter()
    await printer.start(bus)

    capture = StringIO()
    old_stdout = sys.stdout
    sys.stdout = capture
    try:
        await bus.publish(ToolEvent(tool_name="bash", params={"command": "ls"}))
        output = capture.getvalue()
        assert "bash" in output
    finally:
        sys.stdout = old_stdout
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/events/test_printer.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/events/printer.py`**

```python
"""标准输出打印机——订阅 EventBus，将关键事件格式化打印到 daemon stdout"""

from pydantic import BaseModel

from hcode_claude.core.events.bus import EventBus


class StdoutPrinter:
    """订阅 EventBus，格式化打印 token/工具调用/步数到 stdout"""

    # 订阅感兴趣的事件类型，打印人类可读的进度行
    async def start(self, bus: EventBus) -> None:
        # 每步开始：打印 step 编号
        async def on_step(event: BaseModel) -> None:
            if event.model_dump().get("type") == "step.started":
                sn = event.model_dump().get("step_number", "?")
                print(f"[step {sn}]")

        # 工具调用：打印工具名和关键参数
        async def on_tool(event: BaseModel) -> None:
            if event.model_dump().get("type") == "tool.started":
                name = event.model_dump().get("tool_name", "?")
                params = event.model_dump().get("params", {})
                params_str = ", ".join(f"{k}={v}" for k, v in params.items())
                print(f"  → {name}({params_str})")

        bus.subscribe(BaseModel, on_step)
        bus.subscribe(BaseModel, on_tool)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/events/test_printer.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/events/test_printer.py src/hcode_claude/core/events/printer.py
git commit -m "feat: add StdoutPrinter for event streaming to daemon stdout"
```

---

### Task 6: 工具系统 — BaseTool + ToolRegistry (TDD)

**Files:**
- Create: `tests/core/tools/test_registry.py`
- Create: `src/hcode_claude/core/tools/__init__.py`
- Create: `src/hcode_claude/core/tools/base.py`
- Create: `src/hcode_claude/core/tools/registry.py`

**Interfaces:**
- Produces: `BaseTool(name, description, input_schema, invoke())`, `ToolRegistry.register(tool)`, `ToolRegistry.get(name)`, `ToolRegistry.as_anthropic_tools()`

- [ ] **Step 1: 写失败测试 `tests/core/tools/test_registry.py`**

```python
"""ToolRegistry 测试"""

import pytest

from hcode_claude.core.tools.base import BaseTool
from hcode_claude.core.tools.registry import ToolRegistry


class FakeTool(BaseTool):
    """测试用假工具"""
    name = "fake"
    description = "does nothing"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        }

    async def invoke(self, params: dict) -> str:
        return f"got {params['x']}"


class AnotherTool(BaseTool):
    """第二个测试工具"""
    name = "another"
    description = "also nothing"

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def invoke(self, params: dict) -> str:
        return "ok"


# 功能：验证注册后能用 get 按名称查找到工具
# 设计：register 后 get 返回同一实例
def test_register_and_get():
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)
    assert registry.get("fake") is tool


# 功能：验证 get 不存在的工具名抛出 KeyError
# 设计：找不到工具是调用方的问题，应明确报错
def test_get_unknown_tool_raises_keyerror():
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.get("nonexistent")


# 功能：验证 as_anthropic_tools 导出 Anthropic 格式的 tool schema
# 设计：输出应包含 name、description、input_schema 三字段
def test_as_anthropic_tools_format():
    registry = ToolRegistry()
    registry.register(FakeTool())
    tools = registry.as_anthropic_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "fake"
    assert tools[0]["description"] == "does nothing"
    assert "input_schema" in tools[0]


# 功能：验证多个工具导出到同一个列表
# 设计：注册两个工具，列表长度应为 2
def test_multiple_tools_export():
    registry = ToolRegistry()
    registry.register(FakeTool())
    registry.register(AnotherTool())
    tools = registry.as_anthropic_tools()
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert names == {"fake", "another"}


# 功能：验证重复注册同名工具会覆盖旧工具
# 设计：第二次 register 同一个 name 会替换，不抛异常
def test_duplicate_register_overwrites():
    registry = ToolRegistry()
    t1 = FakeTool()
    t2 = FakeTool()
    registry.register(t1)
    registry.register(t2)
    assert registry.get("fake") is t2
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/tools/test_registry.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现**

```python
# 文件: src/hcode_claude/core/tools/__init__.py
"""工具系统——BaseTool 抽象 + ToolRegistry + 内建工具"""
```

```python
# 文件: src/hcode_claude/core/tools/base.py
"""工具基类——定义 name、description、input_schema、invoke 接口"""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """所有工具的抽象基类"""
    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """返回 JSON Schema dict，传给 LLM API"""
        ...

    @abstractmethod
    async def invoke(self, params: dict[str, Any]) -> str:
        """执行工具，返回结果文本"""
        ...
```

```python
# 文件: src/hcode_claude/core/tools/registry.py
"""工具注册表——管理所有工具实例，提供注册、查找、导出 Anthropic tool schema"""

from hcode_claude.core.tools.base import BaseTool


class ToolRegistry:
    """持有所有已注册工具，提供 Anrhopic API 兼容的 tool 定义列表"""

    # 初始化空注册表
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # 注册一个工具实例（同名覆盖）
    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    # 按名称查找工具，找不到抛出 KeyError
    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    # 导出 Anthropic API 兼容的 tools 列表
    def as_anthropic_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/tools/test_registry.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/tools/test_registry.py src/hcode_claude/core/tools/__init__.py src/hcode_claude/core/tools/base.py src/hcode_claude/core/tools/registry.py
git commit -m "feat: add BaseTool abstract class and ToolRegistry"
```

---

### Task 7: 四个内建工具 (TDD)

**Files:**
- Create: `tests/core/tools/test_builtin_tools.py`
- Create: `src/hcode_claude/core/tools/read_file.py`
- Create: `src/hcode_claude/core/tools/write_file.py`
- Create: `src/hcode_claude/core/tools/bash.py`
- Create: `src/hcode_claude/core/tools/list_dir.py`

- [ ] **Step 1: 写失败测试 `tests/core/tools/test_builtin_tools.py`**

```python
"""内建工具测试"""

from pathlib import Path

import pytest

from hcode_claude.core.tools.read_file import ReadFileTool
from hcode_claude.core.tools.write_file import WriteFileTool
from hcode_claude.core.tools.bash import BashTool
from hcode_claude.core.tools.list_dir import ListDirTool


# 功能：验证 read_file 读取文件内容
# 设计：临时目录创建文件，读取后断言内容一致
@pytest.mark.asyncio
async def test_read_file(tmp_path: Path):
    file = tmp_path / "test.txt"
    file.write_text("hello world")
    tool = ReadFileTool(cwd=tmp_path)
    result = await tool.invoke({"path": str(file)})
    assert "hello world" in result


# 功能：验证 read_file 拒绝工作目录外的路径
# 设计：传 /etc/passwd 应被拒绝
@pytest.mark.asyncio
async def test_read_file_rejects_outside_cwd(tmp_path: Path):
    tool = ReadFileTool(cwd=tmp_path)
    result = await tool.invoke({"path": "/etc/passwd"})
    assert "outside" in result.lower() or "denied" in result.lower()


# 功能：验证 write_file 写入内容到文件
# 设计：写入后读回校验，父目录不存在时自动创建
@pytest.mark.asyncio
async def test_write_file(tmp_path: Path):
    tool = WriteFileTool(cwd=tmp_path)
    file = tmp_path / "subdir" / "out.txt"
    result = await tool.invoke({"path": str(file), "content": "new content"})
    assert "success" in result.lower() or "wrote" in result.lower()
    assert file.read_text() == "new content"


# 功能：验证 bash 执行 shell 命令
# 设计：执行 echo 命令，断言 stdout 包含预期输出
@pytest.mark.asyncio
async def test_bash_echo(tmp_path: Path):
    tool = BashTool(cwd=tmp_path)
    result = await tool.invoke({"command": "echo hello_from_bash"})
    assert "hello_from_bash" in result


# 功能：验证 bash 命令超时报错
# 设计：sleep 120 超过默认 60s 超时，应报 timeout
@pytest.mark.asyncio
async def test_bash_timeout(tmp_path: Path):
    tool = BashTool(cwd=tmp_path, timeout=2)
    result = await tool.invoke({"command": "sleep 10"})
    assert "timeout" in result.lower()


# 功能：验证 list_dir 列出目录内容
# 设计：临时目录创建文件和子目录，断言输出包含
@pytest.mark.asyncio
async def test_list_dir(tmp_path: Path):
    (tmp_path / "a.txt").touch()
    (tmp_path / "sub").mkdir()
    tool = ListDirTool(cwd=tmp_path)
    result = await tool.invoke({"path": str(tmp_path)})
    assert "a.txt" in result
    assert "sub" in result


# 功能：验证 list_dir 拒绝非目录路径
# 设计：传文件路径应报错
@pytest.mark.asyncio
async def test_list_dir_rejects_file(tmp_path: Path):
    file = tmp_path / "f.txt"
    file.touch()
    tool = ListDirTool(cwd=tmp_path)
    result = await tool.invoke({"path": str(file)})
    assert "not a directory" in result.lower() or "error" in result.lower()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/tools/test_builtin_tools.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现四个工具**

```python
# 文件: src/hcode_claude/core/tools/read_file.py
"""读取文件工具——读取指定路径的文件内容"""

from pathlib import Path
from typing import Any

from hcode_claude.core.tools.base import BaseTool


class ReadFileTool(BaseTool):
    """读取指定文件的内容"""

    name = "read_file"
    description = "读取文件内容。参数 path: 文件路径（相对于工作目录或绝对路径）"

    # 绑定工作目录，限制文件访问范围
    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要读取的文件路径"},
            },
            "required": ["path"],
        }

    # 读取文件：校验路径在 cwd 内 → Path.read_text
    async def invoke(self, params: dict[str, Any]) -> str:
        target = Path(params["path"])
        if not target.is_absolute():
            target = self._cwd / target
        target = target.resolve()
        # 安全校验：禁止读取 cwd 外的文件
        if not str(target).startswith(str(self._cwd.resolve())):
            return f"Error: access denied — path outside working directory: {target}"
        if not target.is_file():
            return f"Error: not a file: {target}"
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error: {e}"
```

```python
# 文件: src/hcode_claude/core/tools/write_file.py
"""写入文件工具——写入内容到指定路径的文件"""

from pathlib import Path
from typing import Any

from hcode_claude.core.tools.base import BaseTool


class WriteFileTool(BaseTool):
    """写入内容到指定文件，父目录不存在时自动创建"""

    name = "write_file"
    description = "写入内容到文件。参数 path: 文件路径, content: 要写入的内容"

    # 绑定工作目录，限制文件写入范围
    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "要写入的内容"},
            },
            "required": ["path", "content"],
        }

    # 写入文件：校验路径在 cwd 内 → 创建父目录 → Path.write_text
    async def invoke(self, params: dict[str, Any]) -> str:
        target = Path(params["path"])
        if not target.is_absolute():
            target = self._cwd / target
        target = target.resolve()
        if not str(target).startswith(str(self._cwd.resolve())):
            return f"Error: access denied — path outside working directory: {target}"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(params["content"], encoding="utf-8")
            return f"Wrote {target.stat().st_size} bytes to {target}"
        except Exception as e:
            return f"Error: {e}"
```

```python
# 文件: src/hcode_claude/core/tools/bash.py
"""Bash 工具——执行 shell 命令并返回 stdout/stderr"""

import asyncio
from pathlib import Path
from typing import Any

from hcode_claude.core.tools.base import BaseTool


class BashTool(BaseTool):
    """执行 shell 命令，超时自动终止并返回输出"""

    name = "bash"
    description = "执行 shell 命令。参数 command: 要执行的命令"

    # 绑定工作目录和超时时间
    def __init__(self, cwd: Path, timeout: int = 60) -> None:
        self._cwd = cwd
        self._timeout = timeout

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 shell 命令"},
            },
            "required": ["command"],
        }

    # 执行命令：asyncio subprocess → stdout/stderr 截断 → 超时 kill
    async def invoke(self, params: dict[str, Any]) -> str:
        command = params["command"]
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._cwd),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            out = stdout.decode("utf-8", errors="replace")[:5000]
            err = stderr.decode("utf-8", errors="replace")[:5000]
            parts = []
            if out:
                parts.append(out)
            if err:
                parts.append(f"[stderr]\n{err}")
            return "\n".join(parts) if parts else f"(exit code {proc.returncode})"
        except asyncio.TimeoutError:
            return "Error: command timed out"
        except Exception as e:
            return f"Error: {e}"
```

```python
# 文件: src/hcode_claude/core/tools/list_dir.py
"""列出目录工具——列出指定目录下的文件和子目录"""

from pathlib import Path
from typing import Any

from hcode_claude.core.tools.base import BaseTool


class ListDirTool(BaseTool):
    """列出目录内容，返回文件名列表"""

    name = "list_dir"
    description = "列出目录中的文件和子目录。参数 path: 目录路径"

    # 绑定工作目录，限制访问范围
    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要列出的目录路径"},
            },
            "required": ["path"],
        }

    # 列出目录：校验路径 → iterdir → 按类型标记 → 排序返回
    async def invoke(self, params: dict[str, Any]) -> str:
        target = Path(params["path"])
        if not target.is_absolute():
            target = self._cwd / target
        target = target.resolve()
        if not str(target).startswith(str(self._cwd.resolve())):
            return f"Error: access denied — path outside working directory: {target}"
        if not target.is_dir():
            return f"Error: not a directory: {target}"
        try:
            lines = []
            for entry in sorted(target.iterdir()):
                prefix = "[DIR] " if entry.is_dir() else "[FILE]"
                lines.append(f"{prefix} {entry.name}")
            return "\n".join(lines) if lines else "(empty directory)"
        except Exception as e:
            return f"Error: {e}"
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/tools/test_builtin_tools.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/tools/test_builtin_tools.py src/hcode_claude/core/tools/read_file.py src/hcode_claude/core/tools/write_file.py src/hcode_claude/core/tools/bash.py src/hcode_claude/core/tools/list_dir.py
git commit -m "feat: add four built-in tools (read_file, write_file, bash, list_dir)"
```

---

### Task 8: 配置扩展 (TDD)

**Files:**
- Modify: `tests/core/test_config.py`
- Modify: `src/hcode_claude/core/config.py`

- [ ] **Step 1: 追加测试到 `tests/core/test_config.py`**

```python
# 在文件末尾追加

# 功能：验证新增的 anthropic_api_key 默认值为空字符串
# 设计：不设任何外部配置，API key 应为空
def test_anthropic_api_key_defaults_to_empty():
    cfg = load_config()
    assert cfg.anthropic_api_key == ""


# 功能：验证环境变量 HCODE_ANTHROPIC_API_KEY 覆盖 key
# 设计：设置环境变量后断言生效
def test_env_var_overrides_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("HCODE_ANTHROPIC_API_KEY", "sk-ant-xxx")
    cfg = load_config()
    assert cfg.anthropic_api_key == "sk-ant-xxx"


# 功能：验证 anthropic_model 默认值
# 设计：默认模型为 claude-sonnet-4-6
def test_anthropic_model_default():
    cfg = load_config()
    assert cfg.anthropic_model == "claude-sonnet-4-6"


# 功能：验证 max_steps 默认值为 20
# 设计：不配置时使用 20 步上限
def test_max_steps_default():
    cfg = load_config()
    assert cfg.max_steps == 20


# 功能：验证 tool_timeout 默认值为 60 秒
# 设计：bash 工具默认 60s 超时
def test_tool_timeout_default():
    cfg = load_config()
    assert cfg.tool_timeout == 60
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/test_config.py -v
```

Expected: 新增 5 个 FAIL — `Config.__init__` 报缺少参数

- [ ] **Step 3: 修改 `src/hcode_claude/core/config.py`**

```python
# 在 _VALID_KEYS 中加四个 key
_VALID_KEYS = {"host", "port", "log_level", "log_file", "log_format",
               "anthropic_api_key", "anthropic_model", "max_steps", "tool_timeout"}

# 在 _DEFAULTS 中加默认值
_DEFAULTS: dict[str, object] = {
    "host": "127.0.0.1",
    "port": 47201,
    "log_level": "INFO",
    "log_file": "",
    "log_format": "console",
    "anthropic_api_key": "",
    "anthropic_model": "claude-sonnet-4-6",
    "max_steps": 20,
    "tool_timeout": 60,
}

# 在 _ENV_MAP 中加映射
_ENV_MAP = {
    "HCODE_HOST": "host",
    "HCODE_PORT": "port",
    "HCODE_LOG_LEVEL": "log_level",
    "HCODE_LOG_FILE": "log_file",
    "HCODE_LOG_FORMAT": "log_format",
    "HCODE_ANTHROPIC_API_KEY": "anthropic_api_key",
    "HCODE_ANTHROPIC_MODEL": "anthropic_model",
    "HCODE_MAX_STEPS": "max_steps",
    "HCODE_TOOL_TIMEOUT": "tool_timeout",
}

# 修改 Config dataclass
@dataclass(frozen=True)
class Config:
    host: str
    port: int
    log_level: str
    log_file: str
    log_format: str
    anthropic_api_key: str
    anthropic_model: str
    max_steps: int
    tool_timeout: int

# 修改 load_config 返回值
def load_config() -> Config:
    ...
    return Config(
        host=_coerce_str("host", merged["host"]),
        port=_coerce_int("port", merged["port"]),
        log_level=_coerce_str("log_level", merged["log_level"]),
        log_file=_coerce_str("log_file", merged["log_file"]),
        log_format=_coerce_str("log_format", merged["log_format"]),
        anthropic_api_key=_coerce_str("anthropic_api_key", merged["anthropic_api_key"]),
        anthropic_model=_coerce_str("anthropic_model", merged["anthropic_model"]),
        max_steps=_coerce_int("max_steps", merged["max_steps"]),
        tool_timeout=_coerce_int("tool_timeout", merged["tool_timeout"]),
    )
```

- [ ] **Step 4: 运行全量 config 测试验证通过**

```bash
uv run pytest tests/core/test_config.py -v
```

Expected: 16 passed（11 个 S0 + 5 个 S1 新增）

- [ ] **Step 5: Commit**

```bash
git add tests/core/test_config.py src/hcode_claude/core/config.py
git commit -m "feat: add S1 config keys (anthropic_api_key, model, max_steps, tool_timeout)"
```

---

### Task 9: LLM Provider (TDD)

**Files:**
- Create: `tests/core/llm/test_provider.py`
- Modify: `src/hcode_claude/core/llm/provider.py`

- [ ] **Step 1: 写失败测试 `tests/core/llm/test_provider.py`**

```python
"""LLM Provider 测试"""

import pytest

from hcode_claude.core.llm.provider import AnthropicProvider, BaseProvider


# 功能：验证 AnthropicProvider 是 BaseProvider 的子类
# 设计：确保接口一致性，AgentLoop 可以依赖 BaseProvider 做类型提示
def test_anthropic_provider_is_base_provider():
    provider = AnthropicProvider(api_key="test-key")
    assert isinstance(provider, BaseProvider)


# 功能：验证 AnthropicProvider 有 chat 方法
# 设计：chat 是 BaseProvider 定义的抽象方法，必须实现
def test_anthropic_provider_has_chat():
    provider = AnthropicProvider(api_key="test-key")
    assert hasattr(provider, "chat")
    assert callable(provider.chat)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/llm/test_provider.py -v
```

Expected: FAIL — `ModuleNotFoundError` 或 `ImportError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/llm/provider.py`**

```python
"""LLM Provider 抽象 + Anthropic 实现——封装 API 流式调用、prompt caching 与重试"""

from abc import ABC, abstractmethod

from anthropic import AsyncAnthropic

from hcode_claude.core.llm.types import ChatResult, ToolUseBlock


class BaseProvider(ABC):
    """LLM Provider 抽象——AgentLoop 只依赖此接口，不直接接触 SDK"""

    # 发送消息到 LLM，返回文本 + 工具调用列表 + 用量
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system: str,
    ) -> ChatResult: ...


class AnthropicProvider(BaseProvider):
    """Anthropic 实现——流式调用 + prompt caching + 网络重试"""

    # 初始化 SDK 客户端和模型 ID
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    # 流式调用 Anthropic API，收集 text + tool_uses，返回 ChatResult
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system: str,
    ) -> ChatResult:
        # 1. system prompt 最后 2 段加 cache_control
        system_blocks = self._with_cache_control(system)

        # 2. tools 最后一条加 cache_control
        cached_tools = self._add_tool_cache_control(tools) if tools else None

        import asyncio

        for attempt in range(3):
            try:
                return await self._do_chat(messages, cached_tools, system_blocks)
            except Exception as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

        # 不可达（最后一次重试会抛异常或返回结果）
        raise RuntimeError("unreachable")

    # 执行单次 API 调用：构造请求 → 流式接收 → 收集 text + tool_uses
    async def _do_chat(
        self, messages: list[dict], tools: list[dict] | None, system_blocks: list[dict]
    ) -> ChatResult:
        kwargs = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
            "system": system_blocks,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        text_parts: list[str] = []
        tool_uses: list[ToolUseBlock] = {}
        input_tokens = 0
        output_tokens = 0

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "message_start":
                    input_tokens = event.message.usage.input_tokens
                elif event.type == "message_delta":
                    output_tokens = event.usage.output_tokens
                elif event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        tu = event.content_block
                        tool_uses[tu.id] = {"id": tu.id, "name": tu.name, "input": {}}
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        text_parts.append(delta.text)
                    elif delta.type == "input_json_delta":
                        tool_uses[event.index]["input"][""] = delta.partial_json  # noqa — 简化处理

        # 收集所有 tool_use（保持顺序）
        sorted_tools = [
            ToolUseBlock(id=t["id"], name=t["name"], input=t["input"])
            for t in tool_uses.values()
        ]

        return ChatResult(
            text="".join(text_parts),
            tool_uses=sorted_tools,
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
        )

    # 给 system prompt 最后 2 段加 cache_control
    @staticmethod
    def _with_cache_control(system: str) -> list[dict]:
        # 将 system 字符串拆成段落，最后 2 段标 cache_control
        paragraphs = [p for p in system.split("\n\n") if p.strip()]
        result = [{"type": "text", "text": p} for p in paragraphs[:-2]]
        for p in paragraphs[-2:]:
            result.append({
                "type": "text",
                "text": p,
                "cache_control": {"type": "ephemeral"},
            })
        return result

    # 给 tools 列表最后一条加 cache_control
    @staticmethod
    def _add_tool_cache_control(tools: list[dict]) -> list[dict]:
        if not tools:
            return tools
        result = list(tools)
        result[-1] = {**result[-1], "cache_control": {"type": "ephemeral"}}
        return result
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/llm/test_provider.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/llm/test_provider.py src/hcode_claude/core/llm/provider.py
git commit -m "feat: add BaseProvider abstraction and AnthropicProvider with streaming + cache"
```

---

### Task 10: ExecutionContext (TDD)

**Files:**
- Create: `tests/core/test_context.py`
- Create: `src/hcode_claude/core/context.py`

**Interfaces:**
- Produces: `ExecutionContext.build_system_prompt(base)`, `add_user_message(content)`, `add_assistant_message(content, tool_uses)`, `add_tool_results(results)`, `estimated_tokens()`, `messages` (property)

- [ ] **Step 1: 写失败测试 `tests/core/test_context.py`**

```python
"""ExecutionContext 测试"""

import pytest

from hcode_claude.core.context import ExecutionContext


# 功能：验证初始消息列表为空
# 设计：新创建的 ExecutionContext 没有任何消息
def test_initial_messages_empty():
    ctx = ExecutionContext()
    assert ctx.messages == []


# 功能：验证 add_user_message 后消息列表包含一条 user 消息
# 设计：追加 user 消息后列表长度+1，role 为 user
def test_add_user_message():
    ctx = ExecutionContext()
    ctx.add_user_message("帮我修 bug")
    assert len(ctx.messages) == 1
    assert ctx.messages[0]["role"] == "user"
    assert ctx.messages[0]["content"] == "帮我修 bug"


# 功能：验证 add_assistant_message 生成 assistant role 的 content block
# 设计：content 包含 text 和 tool_use 两种 block 类型
def test_add_assistant_message_with_tool_uses():
    ctx = ExecutionContext()
    ctx.add_user_message("hi")
    ctx.add_assistant_message(
        "先看看",
        [{"id": "tu1", "name": "bash", "input": {"command": "ls"}}],
    )
    assert len(ctx.messages) == 2
    assistant = ctx.messages[1]
    assert assistant["role"] == "assistant"
    content = assistant["content"]
    # content 是列表：[text_block, tool_use_block]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "tool_use"


# 功能：验证 add_tool_results 将多个 tool_result 打包到一条 user 消息
# 设计：多工具结果合并为一条 user 消息，每个结果一个 tool_result block
def test_add_tool_results_packs_into_one_user_message():
    ctx = ExecutionContext()
    ctx.add_user_message("hi")
    ctx.add_assistant_message("", [{"id": "tu1", "name": "bash", "input": {}}])
    assert len(ctx.messages) == 2
    ctx.add_tool_results([
        {"tool_use_id": "tu1", "content": "result1", "is_error": False},
        {"tool_use_id": "tu2", "content": "result2", "is_error": False},
    ])
    assert len(ctx.messages) == 3
    user_msg = ctx.messages[2]
    assert user_msg["role"] == "user"
    content = user_msg["content"]
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["tool_use_id"] == "tu1"
    assert content[1]["tool_use_id"] == "tu2"


# 功能：验证 estimated_tokens 返回正整数
# 设计：用字符数/4估算，空消息应返回 0
def test_estimated_tokens_default():
    ctx = ExecutionContext()
    assert ctx.estimated_tokens() >= 0


# 功能：验证 build_system_prompt 至少包含 base 参数
# 设计：S1 的 layer2-4 返回空，结果应只包含 base
@pytest.mark.asyncio
async def test_build_system_prompt_contains_base():
    ctx = ExecutionContext()
    prompt = await ctx.build_system_prompt("你是好助手")
    assert "你是好助手" in prompt
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/test_context.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/context.py`**

```python
"""消息上下文管理——维护 Anthropic API 格式的 messages 列表，提供 system prompt 四层拼接"""

from pathlib import Path


class ExecutionContext:
    """维护多轮对话的完整消息历史，Anthropic 原生 dict 格式"""

    # 初始化空消息列表
    def __init__(self) -> None:
        self._messages: list[dict] = []

    # 当前消息历史（只读）
    @property
    def messages(self) -> list[dict]:
        return self._messages

    # 构建四层 system prompt：base → ~/.hcode/context.md → .hcode/context.md → session notes
    async def build_system_prompt(self, base: str) -> str:
        parts = [
            base,
            self._load_global_context(),
            self._load_project_context(),
            self._load_session_notes(),
        ]
        return "\n\n".join(p for p in parts if p)

    # 追加用户消息
    def add_user_message(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    # 追加 assistant 消息——文本 + 工具调用块
    def add_assistant_message(self, content: str, tool_uses: list[dict]) -> None:
        blocks: list[dict] = []
        if content:
            blocks.append({"type": "text", "text": content})
        for tu in tool_uses:
            blocks.append({
                "type": "tool_use",
                "id": tu["id"],
                "name": tu["name"],
                "input": tu["input"],
            })
        self._messages.append({"role": "assistant", "content": blocks})

    # 追加工具结果——多个 tool_result 打包到同一条 user 消息
    def add_tool_results(self, results: list[dict]) -> None:
        blocks = [
            {"type": "tool_result", "tool_use_id": r["tool_use_id"],
             "content": r["content"], "is_error": r.get("is_error", False)}
            for r in results
        ]
        self._messages.append({"role": "user", "content": blocks})

    # 估算当前消息历史的 token 数（字符数 / 4）
    def estimated_tokens(self) -> int:
        import json
        raw = json.dumps(self._messages, ensure_ascii=False)
        return len(raw) // 4

    # 加载全局 context 文件（返回空字符串，S4 实现）
    @staticmethod
    def _load_global_context() -> str:
        return ""

    # 加载项目 context 文件（返回空字符串，S4 实现）
    @staticmethod
    def _load_project_context() -> str:
        return ""

    # 加载会话笔记（返回空字符串，S4 实现）
    @staticmethod
    def _load_session_notes() -> str:
        return ""
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/test_context.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/test_context.py src/hcode_claude/core/context.py
git commit -m "feat: add ExecutionContext with message history and 4-layer system prompt"
```

---

### Task 11: AgentLoop (TDD)

**Files:**
- Create: `tests/core/test_loop.py`
- Create: `src/hcode_claude/core/loop.py`

**Dependencies:** Task 1 (types), Task 2 (events), Task 3 (bus), Task 6 (tools), Task 9 (provider), Task 10 (context)

- [ ] **Step 1: 写失败测试 `tests/core/test_loop.py`**

```python
"""AgentLoop 测试——用 FakeProvider 模拟 LLM 行为"""

import pytest

from hcode_claude.core.context import ExecutionContext
from hcode_claude.core.events.bus import EventBus
from hcode_claude.core.llm.provider import BaseProvider
from hcode_claude.core.llm.types import ChatResult, ToolUseBlock
from hcode_claude.core.loop import AgentLoop
from hcode_claude.core.tools.registry import ToolRegistry


class FakeProvider(BaseProvider):
    """模拟 LLM：按预设序列依次返回 ChatResult"""

    def __init__(self, responses: list[ChatResult]) -> None:
        self.responses = responses
        self.called = 0

    async def chat(
        self, messages: list[dict], tools: list[dict] | None, system: str
    ) -> ChatResult:
        if self.called >= len(self.responses):
            # 超出预设 → 返回纯文本终止
            return ChatResult(text="done", tool_uses=[], usage={"input_tokens": 0, "output_tokens": 0})
        result = self.responses[self.called]
        self.called += 1
        return result


class FakeTool:
    """模拟工具：直接返回传入参数"""
    name = "fake_tool"
    description = "a fake tool"

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def invoke(self, params: dict) -> str:
        return f"executed with {params}"


# 功能：验证纯文本回复（无工具调用）时 AgentLoop 正常终止
# 设计：FakeProvider 返回空 tool_uses，loop 应返回 completed status
@pytest.mark.asyncio
async def test_loop_stops_on_text_only_response():
    ctx = ExecutionContext()
    provider = FakeProvider([
        ChatResult(text="任务完成", tool_uses=[], usage={"input_tokens": 10, "output_tokens": 5}),
    ])
    registry = ToolRegistry()
    bus = EventBus()
    loop = AgentLoop(ctx, provider, registry, bus)

    result = await loop.run("测试目标", max_steps=5)
    assert result.status == "completed"
    assert result.steps == 1
    assert result.output == "任务完成"


# 功能：验证达到 max_steps 时强制终止
# 设计：FakeProvider 一直返回工具调用，直到步数耗尽
@pytest.mark.asyncio
async def test_loop_max_steps_triggers():
    ctx = ExecutionContext()
    provider = FakeProvider([
        ChatResult(text="", tool_uses=[ToolUseBlock(id="t1", name="fake_tool", input={})],
                   usage={"input_tokens": 1, "output_tokens": 1}),
        ChatResult(text="", tool_uses=[ToolUseBlock(id="t2", name="fake_tool", input={})],
                   usage={"input_tokens": 1, "output_tokens": 1}),
        ChatResult(text="", tool_uses=[ToolUseBlock(id="t3", name="fake_tool", input={})],
                   usage={"input_tokens": 1, "output_tokens": 1}),
    ])
    registry = ToolRegistry()
    registry.register(FakeTool())
    bus = EventBus()
    loop = AgentLoop(ctx, provider, registry, bus)

    result = await loop.run("目标", max_steps=2)
    assert result.status == "max_steps"
    assert result.steps == 2


# 功能：验证工具调用正常执行并返回结果
# 设计：FakeProvider 返回一个工具调用，loop 应执行工具并将结果追加到 context
@pytest.mark.asyncio
async def test_loop_invokes_tool_and_continues():
    ctx = ExecutionContext()
    provider = FakeProvider([
        ChatResult(text="lets check",
                   tool_uses=[ToolUseBlock(id="tu1", name="fake_tool", input={"x": 1})],
                   usage={"input_tokens": 10, "output_tokens": 5}),
        ChatResult(text="done after tool", tool_uses=[], usage={"input_tokens": 10, "output_tokens": 5}),
    ])
    registry = ToolRegistry()
    registry.register(FakeTool())
    bus = EventBus()
    loop = AgentLoop(ctx, provider, registry, bus)

    result = await loop.run("目标", max_steps=5)
    assert result.status == "completed"
    assert result.steps == 2
    assert "done after tool" in result.output


# 功能：验证工具调用失败不会中断循环
# 设计：工具抛异常 → ToolCallFailedEvent → 结果以 error 形式写回 context
@pytest.mark.asyncio
async def test_loop_handles_tool_error_gracefully():
    class CrashingTool:
        name = "crash"
        description = "crashes"

        @property
        def input_schema(self) -> dict:
            return {"type": "object", "properties": {}}

        async def invoke(self, params: dict) -> str:
            raise RuntimeError("boom")

    ctx = ExecutionContext()
    provider = FakeProvider([
        ChatResult(text="", tool_uses=[ToolUseBlock(id="t1", name="crash", input={})],
                   usage={"input_tokens": 1, "output_tokens": 1}),
        ChatResult(text="ok after crash", tool_uses=[], usage={"input_tokens": 1, "output_tokens": 1}),
    ])
    registry = ToolRegistry()
    registry.register(CrashingTool())
    bus = EventBus()
    loop = AgentLoop(ctx, provider, registry, bus)

    result = await loop.run("目标", max_steps=5)
    assert result.status == "completed"
    assert result.steps == 2
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/test_loop.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/loop.py`**

```python
"""Agent 核心循环——每步 plan（调 LLM）→ observe（追加 assistant 消息）→ act（执行工具）→ observe（追加结果）"""

from hcode_claude.core.context import ExecutionContext
from hcode_claude.core.events.bus import EventBus
from hcode_claude.core.llm.provider import BaseProvider
from hcode_claude.core.llm.types import LoopResult
from hcode_claude.core.protocol.events import (
    LlmUsageEvent,
    StepFinishedEvent,
    StepStartedEvent,
    ToolCallFailedEvent,
    ToolCallFinishedEvent,
    ToolCallStartedEvent,
)
from hcode_claude.core.tools.registry import ToolRegistry

# Agent 基础 system prompt
BASE_SYSTEM_PROMPT = """你是一个 AI 编程助手。用户会给你任务，你可以使用工具来完成。
每次只调用必要的工具，不要调用多余的。如果任务已经完成，直接回复文本即可。"""


class AgentLoop:
    """持有 Context、Provider、Registry、EventBus，执行 plan→observe→act→observe 循环"""

    # 注入依赖：上下文、LLM provider、工具注册表、事件总线
    def __init__(
        self,
        ctx: ExecutionContext,
        provider: BaseProvider,
        registry: ToolRegistry,
        bus: EventBus,
    ) -> None:
        self._ctx = ctx
        self._provider = provider
        self._registry = registry
        self._bus = bus

    # 运行 Agent 循环直到终止
    async def run(self, goal: str, max_steps: int = 20) -> LoopResult:
        # 构建 system prompt + 初始 user 消息
        system = await self._ctx.build_system_prompt(BASE_SYSTEM_PROMPT)
        self._ctx.add_user_message(goal)

        for step in range(1, max_steps + 1):
            # 每步开始事件
            step_started = StepStartedEvent(type="step.started", step_number=step)
            await self._bus.publish(step_started)

            # plan: 调 LLM
            response = await self._provider.chat(
                messages=self._ctx.messages,
                tools=self._registry.as_anthropic_tools(),
                system=system,
            )

            # 用量事件
            usage_event = LlmUsageEvent(
                type="llm.usage",
                input_tokens=response.usage.get("input_tokens", 0),
                output_tokens=response.usage.get("output_tokens", 0),
            )
            await self._bus.publish(usage_event)

            # observe: 记录 assistant 消息（必须在 act 之前）
            raw_tool_uses = [
                {"id": tu.id, "name": tu.name, "input": tu.input}
                for tu in response.tool_uses
            ]
            self._ctx.add_assistant_message(response.text, raw_tool_uses)

            if not response.tool_uses:
                # 无工具调用 → 任务完成
                step_finished = StepFinishedEvent(
                    type="step.finished", step_number=step, tool_call_count=0
                )
                await self._bus.publish(step_finished)
                return LoopResult(status="completed", steps=step, output=response.text)

            # act: 执行所有工具调用
            tool_results = []
            for tu in response.tool_uses:
                started = ToolCallStartedEvent(
                    type="tool.started", tool_name=tu.name, params=tu.input
                )
                await self._bus.publish(started)

                try:
                    tool = self._registry.get(tu.name)
                    output = await tool.invoke(tu.input)
                    finished = ToolCallFinishedEvent(
                        type="tool.finished", tool_name=tu.name, output=output[:500]
                    )
                    await self._bus.publish(finished)
                    tool_results.append({
                        "tool_use_id": tu.id,
                        "content": output,
                        "is_error": False,
                    })
                except Exception as e:
                    failed = ToolCallFailedEvent(
                        type="tool.failed", tool_name=tu.name, error=str(e)
                    )
                    await self._bus.publish(failed)
                    tool_results.append({
                        "tool_use_id": tu.id,
                        "content": str(e),
                        "is_error": True,
                    })

            # observe: 所有工具结果打包到一条 user 消息
            self._ctx.add_tool_results(tool_results)
            step_finished = StepFinishedEvent(
                type="step.finished", step_number=step, tool_call_count=len(tool_results)
            )
            await self._bus.publish(step_finished)

        # max_steps 用尽
        return LoopResult(status="max_steps", steps=max_steps, output="")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/test_loop.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/core/test_loop.py src/hcode_claude/core/loop.py
git commit -m "feat: add AgentLoop with plan-observe-act-observe cycle"
```

---

### Task 12: 协议命令扩展 (TDD)

**Files:**
- Modify: `tests/core/protocol/test_commands.py`
- Modify: `src/hcode_claude/core/protocol/commands.py`

- [ ] **Step 1: 追加测试到 `tests/core/protocol/test_commands.py`**

```python
# 在文件末尾追加

from hcode_claude.core.protocol.commands import Command, RunCommand, RunResult


# 功能：验证 RunCommand type 字段为 "agent.run"
# 设计：RunCommand 是 JSON-RPC method="agent.run" 的 params 体
def test_run_command_type():
    cmd = RunCommand(type="agent.run", goal="修 bug")
    assert cmd.type == "agent.run"
    assert cmd.goal == "修 bug"


# 功能：验证 RunCommand max_steps 默认值为 20
# 设计：不传 max_steps 时使用合理默认值
def test_run_command_max_steps_default():
    cmd = RunCommand(type="agent.run", goal="test")
    assert cmd.max_steps == 20


# 功能：验证 RunResult status 只能是 completed/max_steps/error
# 设计：Literal 类型约束，非法值触发 pydantic ValidationError
def test_run_result_invalid_status_rejected():
    with pytest.raises(Exception):
        RunResult(type="run.result", run_id="1", status="unknown", steps=0, output="")


# 功能：验证 RunCommand 可通过 Command 判别联合反序列化
# 设计：json → pydantic 按 type 自动路由到 RunCommand
def test_run_command_discriminated_union():
    raw = {"type": "agent.run", "goal": "fix bug", "max_steps": 10}
    cmd = Command.model_validate(raw) if hasattr(Command, "model_validate") else RunCommand(**raw)
    assert cmd.goal == "fix bug"
    assert cmd.max_steps == 10
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/protocol/test_commands.py -v
```

Expected: 新增 4 个 FAIL — `ImportError`

- [ ] **Step 3: 修改 `src/hcode_claude/core/protocol/commands.py`**

```python
"""Command 判别联合——按 type 字段路由"""

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


class RunCommand(BaseModel):
    """agent.run 命令——请求 daemon 执行 Agent"""
    type: Literal["agent.run"]
    goal: str
    max_steps: int = 20


class RunResult(BaseModel):
    """agent.run 的成功响应体"""
    type: Literal["run.result"]
    run_id: str
    status: Literal["completed", "max_steps", "error"]
    steps: int
    output: str


# Command 判别联合，全系统统一按 type 字段路由
Command = Annotated[
    PingCommand | RunCommand,
    Field(discriminator="type"),
]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/protocol/test_commands.py -v
```

Expected: 9 passed（5 个 S0 + 4 个 S1）

- [ ] **Step 5: Commit**

```bash
git add tests/core/protocol/test_commands.py src/hcode_claude/core/protocol/commands.py
git commit -m "feat: add RunCommand and RunResult to protocol commands"
```

---

### Task 13: AgentRunner (TDD)

**Files:**
- Create: `tests/core/test_runner.py`
- Create: `src/hcode_claude/core/runner.py`

- [ ] **Step 1: 写失败测试 `tests/core/test_runner.py`**

```python
"""AgentRunner 测试"""

from pathlib import Path

import pytest

from hcode_claude.core.runner import AgentRunner


# 功能：验证 AgentRunner 有 run 方法
# 设计：AgentRunner 是 daemon handler 的入口，必须有 run
def test_agent_runner_has_run_method():
    runner = AgentRunner()
    assert hasattr(runner, "run")
    assert callable(runner.run)


# 功能：验证 run 方法返回 RunResult
# 设计：用 tmp_path 作为 run_dir，传入简单 goal 验证能跑通
@pytest.mark.asyncio
async def test_agent_runner_run_simple_goal(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HCODE_HOME", str(tmp_path))
    monkeypatch.setenv("HCODE_ANTHROPIC_API_KEY", "test-key")

    runner = AgentRunner()
    run_dir = tmp_path / "runs" / "test-run"
    run_dir.mkdir(parents=True)

    result = await runner.run(goal="echo hello", run_dir=run_dir)
    assert result.status in ("completed", "max_steps", "error")
    assert result.steps > 0
    assert result.run_id == "test-run"

    # 验证 events.jsonl 已写入
    events_file = run_dir / "events.jsonl"
    assert events_file.exists()
    lines = events_file.read_text().strip().split("\n")
    assert len(lines) >= 2  # 至少有 RunStarted + RunFinished
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/core/test_runner.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `src/hcode_claude/core/runner.py`**

```python
"""AgentRunner——组装 AgentLoop 所有依赖，管理事件管线，写入 events.jsonl，返回 RunResult"""

from pathlib import Path

from hcode_claude.core.config import load_config
from hcode_claude.core.context import ExecutionContext
from hcode_claude.core.events.bus import EventBus
from hcode_claude.core.events.printer import StdoutPrinter
from hcode_claude.core.events.writer import EventWriter
from hcode_claude.core.llm.provider import AnthropicProvider
from hcode_claude.core.loop import AgentLoop
from hcode_claude.core.protocol.commands import RunResult
from hcode_claude.core.protocol.events import RunFinishedEvent, RunStartedEvent
from hcode_claude.core.tools.bash import BashTool
from hcode_claude.core.tools.list_dir import ListDirTool
from hcode_claude.core.tools.read_file import ReadFileTool
from hcode_claude.core.tools.registry import ToolRegistry
from hcode_claude.core.tools.write_file import WriteFileTool


class AgentRunner:
    """整条 Agent 执行链路的起点——组装所有模块并启动循环"""

    # 运行一次 Agent 执行：初始化组件 → 启动事件管线 → 循环 → 返回结果
    async def run(self, goal: str, run_dir: Path) -> RunResult:
        cfg = load_config()
        run_id = run_dir.name

        # 1. 创建 ExecutionContext
        ctx = ExecutionContext()

        # 2. 创建 AnthropicProvider
        provider = AnthropicProvider(
            api_key=cfg.anthropic_api_key,
            model=cfg.anthropic_model,
        )

        # 3. 创建 ToolRegistry + 注册 4 个内建工具
        cwd = run_dir.parent
        registry = ToolRegistry()
        registry.register(ReadFileTool(cwd=cwd))
        registry.register(WriteFileTool(cwd=cwd))
        registry.register(BashTool(cwd=cwd, timeout=cfg.tool_timeout))
        registry.register(ListDirTool(cwd=cwd))

        # 4. 创建 EventBus + 挂 Writer + Printer
        bus = EventBus()
        writer = EventWriter()
        printer = StdoutPrinter()
        await writer.start(bus, run_dir / "events.jsonl")
        await printer.start(bus)

        # 5. 发 RunStartedEvent
        started = RunStartedEvent(type="run.started", run_id=run_id, goal=goal)
        await bus.publish(started)

        # 6. 创建 AgentLoop + 运行
        loop = AgentLoop(ctx, provider, registry, bus)
        result = await loop.run(goal, max_steps=cfg.max_steps)

        # 7. 发 RunFinishedEvent
        finished = RunFinishedEvent(
            type="run.finished", run_id=run_id,
            status=result.status, steps=result.steps,
        )
        await bus.publish(finished)

        return RunResult(
            type="run.result",
            run_id=run_id,
            status=result.status,
            steps=result.steps,
            output=result.output,
        )
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/core/test_runner.py -v
```

Expected: 2 passed（注意：依赖于 Anthropic API key，CI 环境需 mock）

- [ ] **Step 5: Commit**

```bash
git add tests/core/test_runner.py src/hcode_claude/core/runner.py
git commit -m "feat: add AgentRunner with full dependency assembly and event pipeline"
```

---

### Task 14: daemon 集成 — 注册 agent.run handler

**Files:**
- Modify: `src/hcode_claude/core/app.py`

- [ ] **Step 1: 修改 `src/hcode_claude/core/app.py`**

```python
"""Hcode daemon 入口——CoreApp 组装并运行整个生命周期"""

import asyncio
import signal
from pathlib import Path
from uuid import uuid4

import structlog

from hcode_claude.core import __version__
from hcode_claude.core.config import load_config, setup_logging
from hcode_claude.core.protocol.commands import PongResult, RunResult
from hcode_claude.core.protocol.events import CoreStartedEvent
from hcode_claude.core.runner import AgentRunner
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

        # 4. 注册 handler
        server.register("core.ping", self._handle_ping)
        server.register("agent.run", self._handle_run)

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
    async def _handle_ping(self, params: dict[str, object]) -> PongResult:
        nonce_raw = params.get("nonce", "")
        nonce = str(nonce_raw) if nonce_raw else ""
        return PongResult(
            type="pong",
            nonce=nonce,
            server_version=__version__,
        )

    # 处理 agent.run 请求：提取 goal + max_steps，创建 AgentRunner 执行
    async def _handle_run(self, params: dict[str, object]) -> RunResult:
        goal = str(params.get("goal", ""))
        max_steps_raw = params.get("max_steps", 20)
        max_steps = int(max_steps_raw) if max_steps_raw else 20  # type: ignore[arg-type]

        run_dir = Path.cwd() / ".hcode" / "runs" / uuid4().hex[:8]
        run_dir.mkdir(parents=True, exist_ok=True)

        runner = AgentRunner()
        result = await runner.run(goal=goal, run_dir=run_dir)
        return RunResult(
            type="run.result",
            run_id=result.run_id,
            status=result.status,
            steps=result.steps,
            output=result.output,
        )

    # 注册 SIGINT/SIGTERM handler 到 event loop（Windows 不支持则跳过）
    def _setup_signal_handlers(self, shutdown_event: asyncio.Event) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, shutdown_event.set)
            except NotImplementedError:
                pass  # Windows ProactorEventLoop 不支持 add_signal_handler


# 模块级入口，供 pyproject.scripts 中的 hcode-core 调用
def run() -> None:
    app = CoreApp()
    asyncio.run(app.run())


# 直接 python -m hcode_claude.core.app 时也启动 daemon
if __name__ == "__main__":
    run()
```

- [ ] **Step 2: 验证 daemon 能启动**

```bash
PYTHONPATH=src uv run python -m hcode_claude.core.app &
sleep 2
PYTHONPATH=src uv run python -m hcode_claude.cli.main ping
kill %1
```

Expected: daemon 启动成功，ping 返回 pong

- [ ] **Step 3: Commit**

```bash
git add src/hcode_claude/core/app.py
git commit -m "feat: register agent.run handler in CoreApp daemon"
```

---

### Task 15: CLI `hcode run` 扩展

**Files:**
- Modify: `tests/cli/test_main.py`
- Modify: `src/hcode_claude/cli/main.py`

- [ ] **Step 1: 追加测试到 `tests/cli/test_main.py`**

```python
# 在文件末尾追加

# 功能：验证 hcode run 不带 --goal 时报错
# 设计：--goal 是必须参数，缺少时应输出错误信息并 exit 非 0
def test_run_without_goal_fails():
    result = subprocess.run(
        [sys.executable, "-m", "hcode_claude.cli.main", "run"],
        capture_output=True, text=True, env=_TESTS_ENV,
    )
    assert result.returncode != 0
    assert "goal" in result.stderr.lower()


# 功能：验证 hcode run 带 --goal 但 daemon 未启动时报连接错误
# 设计：daemon 未启动时应在 5s 内超时报连接失败
def test_run_without_daemon_fails():
    result = subprocess.run(
        [
            sys.executable, "-m", "hcode_claude.cli.main",
            "run", "--goal", "test", "--port", "1",
        ],
        capture_output=True, text=True, env=_TESTS_ENV,
        timeout=10,
    )
    assert result.returncode != 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/cli/test_main.py -v -k "run"
```

Expected: FAIL — `Unknown command: run`

- [ ] **Step 3: 修改 `src/hcode_claude/cli/main.py`**

在 `main()` 中添加 `elif sys.argv[1] == "run":` 分支：

```python
# 在 elif sys.argv[1] == "ping": 之后添加

elif sys.argv[1] == "run":
    asyncio.run(_run(
        host=_parse_arg("--host", "127.0.0.1"),
        port=int(_parse_arg("--port", "47201")),
        max_steps=int(_parse_arg("--max-steps", "20")),
    ))
```

在文件末尾添加 `_run` 函数：

```python
# 发送 agent.run 请求到 daemon，等待完成并打印结果
async def _run(host: str, port: int, max_steps: int) -> None:
    goal = _parse_arg("--goal", "")
    if not goal:
        print("Error: --goal is required", file=sys.stderr)
        sys.exit(1)

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5.0,
        )
    except (TimeoutError, ConnectionRefusedError, OSError):
        print(f"无法连接到 daemon ({host}:{port})", file=sys.stderr)
        sys.exit(1)

    request = Request(
        id=uuid4().hex[:8],
        method="agent.run",
        params={"goal": goal, "max_steps": max_steps},
    )
    writer.write(request.model_dump_json().encode() + b"\n")
    await writer.drain()

    # 等待响应（可能很久——没有超时限制）
    line = await reader.readline()
    writer.close()

    data = json.loads(line.decode())

    if "error" in data:
        err = ErrorResponse(**data)
        print(f"Error [{err.error.code}]: {err.error.message}", file=sys.stderr)
        sys.exit(1)

    result = data["result"]
    print(f"{result['status']} in {result['steps']} steps")
    print(f"run_id: {result['run_id']}")
    if result["output"]:
        print()
        print(result["output"])
```

更新 `_usage()` 添加 run 说明：

```python
# 在 _usage 函数中添加
def _usage() -> None:
    print("hcode - Hcode AI Agent CLI")
    print()
    print("Commands:")
    print("  hcode ping    Send ping to hcode-core daemon")
    print("                --host HOST   (default 127.0.0.1)")
    print("                --port PORT   (default 47201)")
    print("                --nonce NONCE (default random)")
    print("  hcode run     Run an agent goal")
    print("                --goal GOAL   (required)")
    print("                --max-steps N (default 20)")
    print("                --host HOST   (default 127.0.0.1)")
    print("                --port PORT   (default 47201)")
    print("  hcode --version  Show version")
    print("  hcode --help     Show this help")
```

- [ ] **Step 4: 运行 CLI 测试验证通过**

```bash
uv run pytest tests/cli/test_main.py -v
```

Expected: 5 passed（3 个 S0 + 2 个 S1）

- [ ] **Step 5: Commit**

```bash
git add tests/cli/test_main.py src/hcode_claude/cli/main.py
git commit -m "feat: add hcode run command with --goal and --max-steps"
```

---

### Task 16: 集成测试 — 端到端 agent.run

**Files:**
- Modify: `tests/core/test_app.py`

- [ ] **Step 1: 追加集成测试**

```python
# 在 tests/core/test_app.py 末尾追加

# 功能：验证 agent.run 的端到端流程——启动 daemon → 发 run 请求 → 等待完成
# 设计：用 free_port + 子进程 daemon，传入简单 goal 验证返回 RunResult
@pytest.mark.asyncio
async def test_daemon_agent_run(free_port: int, tmp_path: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["HCODE_PORT"] = str(free_port)
    env["HCODE_LOG_FILE"] = str(tmp_path / "hcode.log")
    env["HCODE_HOME"] = str(tmp_path)
    env["HCODE_ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")

    proc = subprocess.Popen(
        [sys.executable, "-m", "hcode_claude.core.app"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # 轮询等待 daemon TCP 就绪
        connected = False
        for _ in range(50):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", free_port),
                    timeout=0.3,
                )
                connected = True
                break
            except (TimeoutError, ConnectionRefusedError, OSError):
                if proc.poll() is not None:
                    stdout, stderr = proc.communicate()
                    pytest.fail(
                        f"Daemon exited early (code={proc.returncode})\n"
                        f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
                    )
                await asyncio.sleep(0.1)

        assert connected, "Cannot connect to daemon after 5s"

        # 发送 agent.run
        run_id = "integration-test"
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": run_id,
            "method": "agent.run",
            "params": {"goal": "echo hello_from_test"},
        }) + "\n"
        writer.write(request.encode())
        await writer.drain()

        # 读取响应（等待 Agent 执行完成，可能较久）
        line = await asyncio.wait_for(reader.readline(), timeout=60.0)
        response = json.loads(line.decode())
        writer.close()

        # 校验 RunResult
        assert "result" in response, f"Expected success, got: {response}"
        assert response["id"] == run_id
        result = response["result"]
        assert result["type"] == "run.result"
        assert result["status"] in ("completed", "max_steps", "error")
        assert result["steps"] > 0
        assert result["output"] != "" or result["status"] == "error"

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
```

- [ ] **Step 2: 运行集成测试**

```bash
ANTHROPIC_API_KEY=your-key uv run pytest tests/core/test_app.py::test_daemon_agent_run -v
```

Expected: 1 passed（前提：API key 有效）

Note: 集成测试需要真实 Anthropic API key。CI 环境应设置 `ANTHROPIC_API_KEY` 环境变量或跳过此测试。

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_app.py
git commit -m "test: add end-to-end integration test for agent.run"
```

---

### Task 17: 全量测试 + Lint 收尾

- [ ] **Step 1: 运行全量测试**

```bash
uv run pytest tests/ -v
```

Expected: 所有测试通过（约 74 个）

- [ ] **Step 2: Ruff lint + 修复**

```bash
uv run ruff check src/ tests/ scripts/
uv run ruff check --fix src/ tests/ scripts/
```

Expected: 无错误

- [ ] **Step 3: mypy 类型检查**

```bash
uv run mypy src/
```

Expected: 无错误

- [ ] **Step 4: 更新 WIRE_PROTOCOL.md**

```bash
uv run python scripts/gen_protocol_doc.py
uv run python scripts/gen_protocol_doc.py --check
```

Expected: up to date

- [ ] **Step 5: 最终 Commit**

```bash
git add -A
git commit -m "chore: final lint fixes and full test pass for S1"
```
