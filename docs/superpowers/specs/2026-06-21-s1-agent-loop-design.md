# S1 — Agent 最小闭环设计

**日期:** 2026-06-21  
**状态:** 已确认  
**分支:** v1_agent_loop  
**目标:** 一次 `hcode run --goal "..."` 从用户目标到 LLM → 工具调用 → 事件文件完整跑通

---

## 1. 决策汇总

| # | 决策点 | 选项 | 选择 |
|---|--------|------|------|
| 1 | Agent Loop 运行位置 | CLI 内 vs daemon 内 vs daemon+事件流 | **daemon 内（A）** |
| 2 | LLM Provider | 裸调 SDK vs BaseProvider 抽象 | **BaseProvider 抽象** |
| 3 | LLM 服务商 | Anthropic vs DeepSeek | **Anthropic**（不改 S0 决策） |
| 4 | 一步工具数 | 每步一个 vs 一步多个 | **一步多个（选项 2）** |
| 5 | Agent 终止条件 | end_turn 工具 vs 纯文本终止 vs 混合 | **纯文本终止 + max_steps 兜底** |
| 6 | prompt caching | S1 加 vs 后面补 | **S1 加** |
| 7 | 首批工具 | read_file/write_file/bash/list_dir | **4 个，不变** |
| 8 | 事件管道 | 只写文件 vs EventBus+Writer+Printer | **EventBus + EventWriter + StdoutPrinter** |

---

## 2. 整体架构

```
hcode CLI                               hcode-core daemon
  │                                        │
  │ hcode run --goal "修 bug"              │
  │ → Request(id, method="agent.run",      │
  │           params={"goal":"..."})        │
  │ ────────────────────────────────────→  │
  │                                        │ SocketServer._dispatch()
  │                                        │   → _handle_run(params)
  │                                        │     → AgentRunner.run(goal)
  │                                        │
  │                                        │ AgentRunner.run():
  │                                        │   ① 加载配置（API key）
  │                                        │   ② 创建 ExecutionContext
  │                                        │   ③ 创建 AnthropicProvider
  │                                        │   ④ 创建 ToolRegistry + 注册 4 工具
  │                                        │   ⑤ 创建 EventBus
  │                                        │   ⑥ 挂 EventWriter + StdoutPrinter
  │                                        │   ⑦ 创建 AgentLoop
  │                                        │   ⑧ loop.run()
  │                                        │   ⑨ 返回 RunResult
  │                                        │
  │ ← SuccessResponse(id, RunResult) ──── │
  │                                        │
  │ 打印结果 + exit 0                      │
```

**执行流（AgentRunner 内部）：**

```
AgentRunner（组装起点，整条链路的起点）
  ├── ExecutionContext（维护多轮对话历史）
  ├── AgentLoop（驱动 plan→observe→act→observe 循环）
  │     ├── plan: AnthropicProvider.chat()
  │     ├── observe: context.add_assistant_message()
  │     └── act: invoke_tool() → context.add_tool_results()
  ├── AnthropicProvider（调用 LLM）
  ├── ToolRegistry + 4 个内建工具
  └── EventBus（进程内 pub/sub 管道）
        ├── EventWriter → events.jsonl
        └── StdoutPrinter → daemon stdout
```

---

## 3. 文件结构（S1 新增/修改）

```
src/hcode_claude/core/
├── context.py                  # ExecutionContext — 消息管理与 system prompt
├── loop.py                     # AgentLoop — plan→observe→act→observe 循环
├── runner.py                   # AgentRunner — 组装所有依赖，写事件文件
├── events/
│   ├── __init__.py
│   ├── bus.py                  # EventBus — 进程内 pub/sub
│   ├── writer.py               # EventWriter — 事件 → events.jsonl
│   └── printer.py              # StdoutPrinter — 事件 → daemon stdout
├── llm/
│   ├── __init__.py
│   ├── provider.py             # BaseProvider + AnthropicProvider
│   └── types.py                # ChatResult, ToolUseBlock, ToolResultBlock
├── tools/
│   ├── __init__.py
│   ├── base.py                 # BaseTool 抽象类
│   ├── registry.py             # ToolRegistry
│   ├── read_file.py            # 读取文件
│   ├── write_file.py           # 写入文件
│   ├── bash.py                 # 执行 shell 命令
│   └── list_dir.py             # 列出目录
└── protocol/
    ├── commands.py             # 修改：加 RunCommand + RunResult
    └── events.py               # 修改：加 9 个新事件

tests/
├── core/
│   ├── test_context.py
│   ├── test_loop.py
│   ├── test_runner.py
│   ├── events/
│   │   ├── test_bus.py
│   │   ├── test_writer.py
│   │   └── test_printer.py
│   ├── llm/
│   │   ├── test_provider.py
│   │   └── test_types.py
│   └── tools/
│       ├── test_registry.py
│       └── test_builtin_tools.py
└── cli/
    └── test_main.py            # 修改：加 hcode run 测试
```

**新增依赖：**

```toml
# pyproject.toml
dependencies = [
    "anthropic>=0.30",    # LLM SDK
    "pydantic>=2.0",
    "python-dotenv>=1.0",
    "structlog>=24.0",
]
```

---

## 4. ExecutionContext

```python
# 文件: src/hcode_claude/core/context.py
# 功能: 管理 Anthropic API 格式的 messages 列表，提供 system prompt 四层拼接与消息追加

class ExecutionContext:
    """维护多轮对话的完整消息历史，Anthropic 原生 dict 格式"""

    # 构建四层 system prompt：基础指令 → 全局 context → 项目 context → 会话笔记
    async def build_system_prompt(self, base: str) -> str:
        layer1 = base
        layer2 = self._load_global_context()      # ~/.hcode/context.md
        layer3 = self._load_project_context()      # .hcode/context.md
        layer4 = self._load_session_notes()        # S4 才实现，S1 返回 ""
        return "\n\n".join(filter(None, [layer1, layer2, layer3, layer4]))

    # 追加用户消息到消息历史
    def add_user_message(self, content: str) -> None: ...

    # 追加 assistant 消息（含文本和工具调用块）到消息历史
    def add_assistant_message(self, content: str, tool_uses: list[dict]) -> None: ...

    # 追加工具结果（多条 tool_result 打包到同一条 user 消息）
    def add_tool_results(self, results: list[dict]) -> None: ...

    # 估算当前消息历史的 token 数，为 S6 compaction 预埋
    def estimated_tokens(self) -> int: ...
```

**messages 结构（Anthropic 原生格式）：**

```python
[
    {"role": "user", "content": "帮我看看项目结构"},
    {"role": "assistant", "content": [
        {"type": "text", "text": "先看看项目"},
        {"type": "tool_use", "id": "tu1", "name": "list_dir", "input": {"path": "."}},
        {"type": "tool_use", "id": "tu2", "name": "read_file", "input": {"path": "main.py"}},
    ]},
    {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "tu1", "content": "src/\ntests/\n"},
        {"type": "tool_result", "tool_use_id": "tu2", "content": "import ..."},
    ]},
    {"role": "assistant", "content": "项目结构是..."},
]
```

---

## 5. AgentLoop

```python
# 文件: src/hcode_claude/core/loop.py
# 功能: Agent 核心循环——每步 plan（调 LLM）→ observe（追加 assistant 消息）→ act（执行工具）→ observe（追加结果）

class AgentLoop:
    """持有 Context、Provider、Registry、EventBus，执行 plan→observe→act→observe 循环"""

    # 运行 Agent 循环直到终止
    async def run(self, goal: str, max_steps: int = 20) -> LoopResult:
        # 1. 构建 system prompt + 初始 user 消息
        system = await self._ctx.build_system_prompt(BASE_SYSTEM_PROMPT)
        self._ctx.add_user_message(goal)

        # 2. plan→observe→act→observe 循环
        for step in range(1, max_steps + 1):
            self._bus.publish(StepStartedEvent(step_number=step))

            # plan: 调 LLM
            response = await self._provider.chat(
                messages=self._ctx.messages,
                tools=self._registry.as_anthropic_tools(),
                system=system,
            )

            # observe: 先记录 assistant 消息（Anthropic API 格式要求）
            self._ctx.add_assistant_message(response.text, response.tool_uses)
            self._bus.publish(LlmUsageEvent(**response.usage))

            if not response.tool_uses:
                # 无工具调用 → LLM 认为任务完成
                self._bus.publish(StepFinishedEvent(step_number=step, tool_call_count=0))
                return LoopResult(status="completed", steps=step, output=response.text)

            # act: 执行所有工具调用
            results = []
            for tu in response.tool_uses:
                self._bus.publish(ToolCallStartedEvent(tool_name=tu.name, params=tu.input))
                result = await self._invoke_tool(tu)
                results.append(result)

            # observe: 将所有结果打包到同一条 user 消息
            self._ctx.add_tool_results(results)
            self._bus.publish(StepFinishedEvent(step_number=step, tool_call_count=len(results)))

        # max_steps 用尽
        return LoopResult(status="max_steps", steps=max_steps, output="")

    # 执行单个工具调用：查 registry → invoke → 发事件 → 返回 tool_result block
    async def _invoke_tool(self, tool_use: ToolUseBlock) -> dict:
        tool = self._registry.get(tool_use.name)
        try:
            output = await tool.invoke(tool_use.input)
            self._bus.publish(ToolCallFinishedEvent(
                tool_name=tool_use.name, output=output[:500]))
            return {"type": "tool_result", "tool_use_id": tool_use.id, "content": output}
        except Exception as e:
            self._bus.publish(ToolCallFailedEvent(
                tool_name=tool_use.name, error=str(e)))
            return {"type": "tool_result", "tool_use_id": tool_use.id,
                    "content": str(e), "is_error": True}
```

**终止条件：**
- LLM 返回纯文本（`tool_uses` 为空）→ `status="completed"`
- 步数达到 `max_steps` → `status="max_steps"`

---

## 6. LLM Provider

```python
# 文件: src/hcode_claude/core/llm/provider.py
# 功能: LLM Provider 抽象 + Anthropic 实现——封装 API 流式调用、prompt caching 与重试

class BaseProvider(ABC):
    """LLM Provider 抽象——AgentLoop 只依赖此接口，不直接接触 SDK"""

    # 发送消息到 LLM，返回文本 + 工具调用列表 + 用量
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system: str,
    ) -> ChatResult: ...


class AnthropicProvider(BaseProvider):
    """Anthropic 实现——流式调用 + prompt caching + 网络重试"""

    # 流式调用 Anthropic API，收集 text + tool_uses，返回 ChatResult
    async def chat(self, messages, tools, system) -> ChatResult:
        # 1. system prompt 最后 2 段加 cache_control: ephemeral
        # 2. tools 列表最后一条加 cache_control: ephemeral
        # 3. client.messages.create(model=..., stream=True)
        # 4. 遍历 stream events:
        #    - text_delta → 拼 text
        #    - content_block_start(tool_use) → 收集 tool_use 块
        #    - content_block_delta → 拼 tool_use.input
        # 5. 网络异常重试最多 3 次（退避 1s/2s/4s）
        # 6. 返回 ChatResult(text=..., tool_uses=[...], usage={...})
```

```python
# 文件: src/hcode_claude/core/llm/types.py
# 功能: LLM 模块类型定义——ChatResult、ToolUseBlock

class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]

class LoopResult:
    status: Literal["completed", "max_steps"]
    steps: int
    output: str

class ChatResult:
    text: str
    tool_uses: list[ToolUseBlock]
    usage: dict[str, int]   # input_tokens / output_tokens
```

---

## 7. 事件系统

```python
# 文件: src/hcode_claude/core/events/bus.py
# 功能: 进程内事件总线——发布/订阅，AgentLoop 发布事件，Writer/Printer 订阅消费

class EventBus:
    """进程内 pub/sub，handler 签名 async (BaseModel) -> None"""

    # 订阅事件：按事件类型注册异步 handler
    def subscribe(self, event_type: type, handler: Callable) -> None: ...

    # 发布事件：通知所有匹配类型的订阅者
    async def publish(self, event: BaseModel) -> None: ...
```

```python
# 文件: src/hcode_claude/core/events/writer.py
# 功能: 订阅 EventBus，将事件异步追加写入 events.jsonl

class EventWriter:
    """订阅 EventBus，每条事件写一行 NDJSON 到 events.jsonl"""

    # 打开文件句柄并订阅所有事件类型
    async def start(self, bus: EventBus, path: Path) -> None: ...
```

```python
# 文件: src/hcode_claude/core/events/printer.py
# 功能: 订阅 EventBus，将关键事件格式化打印到 daemon stdout

class StdoutPrinter:
    """订阅 EventBus，格式化打印 token/工具调用/步数到 stdout"""

    # 订阅感兴趣的事件类型，打印人类可读的进度
    async def start(self, bus: EventBus) -> None: ...
```

**数据流：**

```
AgentLoop._invoke_tool()
  │ bus.publish(ToolCallStartedEvent(...))
  ▼
EventBus
  ├──→ EventWriter: 追一行到 events.jsonl
  └──→ StdoutPrinter: 打 "[1/??] bash: pytest tests/"
```

**关键设计：**
- EventBus 只做进程内 dispatch，不做 TCP 广播（S2 加 IpcBroadcaster）
- EventWriter 一个事件一行 NDJSON
- StdoutPrinter 输出目标是 daemon 的 stdout

---

## 8. 工具系统

```python
# 文件: src/hcode_claude/core/tools/base.py
# 功能: 工具基类——定义 name、description、input_schema、invoke 接口

class BaseTool(ABC):
    """所有工具的抽象基类"""
    name: str
    description: str
    input_schema: dict[str, Any]    # JSON Schema，传给 Anthropic API

    # 执行工具：接收 LLM 传来的参数，返回执行结果文本
    async def invoke(self, params: dict[str, Any]) -> str: ...


# 文件: src/hcode_claude/core/tools/registry.py
# 功能: 工具注册表——管理所有工具实例，提供注册、查找、导出 Anthropic tool schema

class ToolRegistry:
    """持有所有已注册工具"""

    # 注册一个工具实例
    def register(self, tool: BaseTool) -> None: ...

    # 按名称查找工具，找不到抛 KeyError
    def get(self, name: str) -> BaseTool: ...

    # 输出 Anthropic API 兼容的 tools 列表
    def as_anthropic_tools(self) -> list[dict]: ...
```

**S1 四个内建工具：**

| 工具 | 参数 | 核心逻辑 | 安全约束（S1 最小） |
|------|------|----------|---------------------|
| `read_file` | `path: str` | `Path.read_text()` | 限制在当前工作目录内 |
| `write_file` | `path: str, content: str` | `Path.write_text()` | 限制在当前工作目录内，父目录不存在则自动创建 |
| `bash` | `command: str` | `subprocess.run()` | cwd 限制，超时 60s，stdout/stderr 截断 |
| `list_dir` | `path: str` | `Path.iterdir()` | 限制在当前工作目录内 |

---

## 9. AgentRunner

```python
# 文件: src/hcode_claude/core/runner.py
# 功能: 组装 AgentLoop 所有依赖，管理事件管线，写入 events.jsonl，返回 RunResult

class AgentRunner:
    """整条 Agent 执行链路的起点——组装所有模块并启动循环"""

    # 运行一次 Agent 执行：初始化 → 启动事件管线 → 循环 → 返回结果
    async def run(self, goal: str, run_dir: Path) -> RunResult:
        # 1. 加载配置（API key）
        cfg = load_config()
        # 2. 创建 ExecutionContext
        ctx = ExecutionContext()
        # 3. 创建 AnthropicProvider
        provider = AnthropicProvider(api_key=cfg.anthropic_api_key)
        # 4. 创建 ToolRegistry + 注册 4 个内建工具
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(WriteFileTool())
        registry.register(BashTool())
        registry.register(ListDirTool())
        # 5. 创建 EventBus + 挂 Writer + Printer
        bus = EventBus()
        writer = EventWriter()
        printer = StdoutPrinter()
        await writer.start(bus, run_dir / "events.jsonl")
        await printer.start(bus)
        # 6. 创建 AgentLoop + 运行
        loop = AgentLoop(ctx, provider, registry, bus)
        bus.publish(RunStartedEvent(run_id=str(run_dir.name), goal=goal))
        result = await loop.run(goal, max_steps=cfg.max_steps)
        bus.publish(RunFinishedEvent(run_id=str(run_dir.name),
                     status=result.status, steps=result.steps))
        # 7. 返回
        return RunResult(run_id=str(run_dir.name),
                        status=result.status, steps=result.steps, output=result.output)
```

---

## 10. 协议扩展

```python
# 文件: src/hcode_claude/core/protocol/commands.py（修改）
# 新增: RunCommand + RunResult

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
```

```python
# 文件: src/hcode_claude/core/protocol/events.py（修改）
# 新增: 9 个 S1 事件

RunStartedEvent          # run 开始：run_id, goal
RunFinishedEvent         # run 结束：run_id, status, steps

StepStartedEvent         # 每步开始：step_number
StepFinishedEvent        # 每步结束：step_number, tool_call_count

ToolCallStartedEvent     # 工具开始：tool_name, params
ToolCallFinishedEvent    # 工具成功：tool_name, output_summary
ToolCallFailedEvent      # 工具失败：tool_name, error

LlmTokenEvent            # 流式 token：text（S1 先写文件，S2 推客户端）
LlmUsageEvent            # 用量统计：input_tokens, output_tokens
LlmModelSelectedEvent    # 实际模型：model_id
```

S1 这些事件只走 EventBus，不通过 TCP 推送（S2 加 IPC 广播时事件类型不变）。

---

## 11. CLI 扩展

```python
# 文件: src/hcode_claude/cli/main.py（修改）
# 新增: hcode run 子命令

# 发送 agent.run 请求到 daemon，等待完成并打印结果
async def _run(host: str, port: int, max_steps: int) -> None:
    goal = _parse_arg("--goal", "")
    if not goal:
        print("Error: --goal is required", file=sys.stderr)
        sys.exit(1)

    # 连接 daemon → 发 Request(method="agent.run",
    #   params={"goal": goal, "max_steps": max_steps})
    # 等待响应（可能很久） → 打印 RunResult
```

**用法：**

```bash
# 终端 1: 启动 daemon
PYTHONPATH=src uv run hcode-core

# 终端 2: 触发 run
PYTHONPATH=src uv run hcode run --goal "在 src/utils 下创建一个 logger.py"
```

---

## 12. 配置扩展

S1 在 `_VALID_KEYS` 中新增：

| Key | 默认值 | 环境变量 | 说明 |
|-----|--------|----------|------|
| `anthropic_api_key` | `""` | `HCODE_ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `anthropic_model` | `"claude-sonnet-4-6"` | `HCODE_ANTHROPIC_MODEL` | 默认模型 ID |
| `max_steps` | `20` | `HCODE_MAX_STEPS` | Agent 最大步数 |
| `tool_timeout` | `60` | `HCODE_TOOL_TIMEOUT` | Bash 工具超时秒数 |

---

## 13. 测试策略

| 测试文件 | 覆盖内容 | 类型 |
|----------|----------|------|
| `test_context.py` | system prompt 拼接、消息追加、token 估算 | 单元 |
| `test_loop.py` | 纯文本终止、max_steps 终止、工具调用循环（mock provider） | 单元 |
| `test_runner.py` | 组装验证、events.jsonl 写入验证 | 单元 |
| `test_bus.py` | publish/subscribe、多订阅者、异常隔离 | 单元 |
| `test_writer.py` | NDJSON 写入、事件序列化 | 单元 |
| `test_printer.py` | 格式化输出 | 单元 |
| `test_provider.py` | ChatResult 解析、cache_control 注入、重试逻辑 | 单元 |
| `test_types.py` | ToolUseBlock/ChatResult 序列化 | 单元 |
| `test_registry.py` | 注册/查找/导出 Anthropic tools schema | 单元 |
| `test_builtin_tools.py` | 4 个工具的 invoke 行为 | 单元 |
| `test_app.py` | 端到端：启动 daemon → hcode run → 校验结果 | 集成 |
| `test_main.py` | CLI --goal 必需、参数解析 | 单元 |

---

## 14. 不纳入 S1 的内容

- 权限审批（S5）
- 上下文压缩 / tool_result 截断（S6）
- Skills / Subagent / MCP（S7）
- SessionManager / 多轮对话（S4）
- IPC 事件流广播 / 客户端事件订阅（S2）
- TUI（S2）
- Token 用量硬限制（S6）
