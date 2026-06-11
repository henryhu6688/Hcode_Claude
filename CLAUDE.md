# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.## 项目目标

从零实现一个本地 AI Agent 系统（mini 版 Claude Code）。最终形态：

- `hcode-core`：常驻守护进程，负责 Agent 循环、工具调用、权限审批、上下文管理
- `hcode-tui`：终端 UI，实时展示执行过程、流式 token、工具调用、权限审批卡片
- `hcode` CLI：轻量命令行客户端，用于快速测试和调试

核心运行链路：**用户目标 → Agent Loop → LLM 思考 → 工具调用 → 权限审批 → 结果回填 → 事件展示 → 会话续航**。

## 技术栈决策（新建项目时确定）

| 决策 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12 | 上手快，Agent 原理不绑定语言 |
| 包管理 | uv + pyproject.toml (PEP 621) | 现代 Python 工具链，快 |
| 构建后端 | Hatchling | PEP 517 标准，轻量 |
| IPC 协议 | JSON-RPC 2.0 over NDJSON (TCP) | 类型化、可扩展、多客户端复用 |
| 数据校验 | Pydantic v2 + discriminated union | 协议层类型安全，按 `type` 字段路由 |
| LLM SDK | Anthropic (流式 + prompt caching) | 目标平台 |
| TUI 框架 | Textual | 终端原生，支持丰富交互 |
| Lint | Ruff + mypy strict | 代码质量 |
| 测试 | pytest + pytest-asyncio | 异步测试支持 |

## 分阶段路线图（S0 → S7）

不是一次性堆功能，每个阶段解决一个真实的 Agent 工程问题。每阶段结束都能运行、能验证、能留下文件证据。

---

### S0 — 骨架与协议契约

**要解决的问题：** 在写任何 Agent 逻辑之前，先把系统边界立住——CLI 和 daemon 通过真实的 IPC 完成一次 ping/pong。

**要构建的内容：**

1. **项目骨架：** `pyproject.toml`（依赖 + 三个入口：`hcode`、`hcode-core`、`hcode-tui`），`src/hcode_claude/` 目录结构
2. **协议层（`core/bus/`）：**
   - `envelope.py` — JSON-RPC 2.0 信封（request / success / error），错误码常量
   - `commands.py` — `Command` 判别联合，S0 仅有 `PingCommand` → `PongResult`
   - `events.py` — `Event` 判别联合，S0 仅有 `CoreStartedEvent`
3. **传输层（`core/transport/socket_server.py`）：**
   - TCP server（`asyncio.start_server`），逐行读取 NDJSON
   - 分发到已注册的 handler（`server.register("method", fn)`）
   - 启动时先探测端口——若已被占用则报错退出
   - JSON-RPC 错误处理：parse error / invalid request / method not found / internal error
4. **配置（`core/config.py`）：**
   - 四级优先级：内建默认值 → `~/.hcode/config.toml` → `.env` → 环境变量
   - S0 key：`host`、`port`、`log_level`、`log_file`、`log_format`
   - 未知 key 硬退出（防止拼写错误悄无声息）
5. **守护进程入口（`core/app.py`）：**
   - `CoreApp.run()`：加载配置 → 日志 → SocketServer → 注册 `core.ping` handler → 等待 SIGINT/SIGTERM
6. **CLI 入口（`cli/main.py`）：**
   - `hcode ping` — 连接 daemon，发 `core.ping`，打印响应
   - `hcode --version`
7. **协议文档自动生成（`scripts/gen_protocol_doc.py`）：**
   - 从 pydantic 模型提取 JSON Schema，生成 `WIRE_PROTOCOL.md`
   - 支持 `--check` 模式（CI 用）
8. **测试：**
   - 单元：envelope 编解码、config 优先级
   - 集成：`conftest.py` 的 `free_port` fixture——找空闲端口 → 释放 → 传 `HCODE_PORT` 启动 daemon 子进程 → 轮询直到连接成功

**为什么 S0 这么重：** 这一步看起来比普通脚手架更重，但它换来的是后面所有能力都不用推倒重来——TUI 复用同一套 IPC，事件订阅复用同一套通道，权限审批通过事件推到前端，trace 记录完整请求和响应。

---

### S1 — Agent 最小闭环

**要解决的问题：** 一次 `hcode run --goal "..."` 从用户目标到 LLM、工具调用、事件文件完整跑通。

**要构建的内容：**

1. **ExecutionContext（`core/context.py`）：**
   - 管理 messages 列表（Anthropic API 格式）
   - `system_prompt(base)`：base → global context → project context → session notes 四层拼接
   - `add_assistant_message()` / `add_tool_result()`：同一步多个 tool_result 合并到同一 user 消息
2. **AgentLoop（`core/loop.py`）：**
   - plan→act→observe 循环：
     - plan：调 LLM（传入 messages + tools + system prompt）
     - observe：assistant 内容块追加到 context
     - act：调 `invoke_tool()`，tool_result 追加到 context
     - 终止：`end_turn` → 成功 | `max_steps` → 失败
3. **AgentRunner（`core/runner.py`）：**
   - 组装依赖（provider、registry、event bus、context）
   - 写 `events.jsonl`
4. **LLM Provider（`core/llm/provider.py`）：**
   - `AnthropicProvider.chat()`：流式调用，逐 token 发布事件
   - system prompt + 最后一个 tool 启用 `cache_control: ephemeral`
   - 网络中断重试（最多 3 次，退避 1s/2s/4s）
5. **工具系统基础（`core/tools/`）：**
   - `BaseTool` 抽象类：name、description、input_schema、invoke()
   - `ToolRegistry`：注册/查找/输出 Anthropic tool schema
   - 首批内建工具：`read_file`、`write_file`、`bash`、`list_dir`
6. **事件（`core/bus/events.py`）：**
   - `RunStartedEvent`、`RunFinishedEvent`、`StepStartedEvent`、`StepFinishedEvent`
   - `ToolCallStartedEvent`、`ToolCallFinishedEvent`、`ToolCallFailedEvent`
   - `LlmTokenEvent`、`LlmUsageEvent`、`LlmModelSelectedEvent`
7. **CLI：** `hcode run --goal "..."` 命令
8. **测试：** AgentRunner 单元测试、LLM provider 单元测试、端到端 run 集成测试

---

### S2 — 事件流外化

**要解决的问题：** AgentRunner 搬进 daemon，CLI/TUI 通过 IPC 订阅同一份事件流。TUI 崩了 Agent 不跟着死。

**要构建的内容：**

1. **EventBus（`core/events/bus.py`）：**
   - 内存发布/订阅，handler 签名 `async (BaseModel) -> None`
2. **EventWriter（`core/events/writer.py`）：**
   - 订阅 EventBus，异步写入 `.jsonl` 文件
3. **IPC Broadcaster（`core/transport/ipc_broadcaster.py`）：**
   - 订阅 EventBus，将事件广播到所有已订阅的客户端连接
4. **SocketClient（`core/transport/socket_client.py`）：**
   - 客户端连接库，CLI 和 TUI 共用
5. **`event.subscribe` IPC 命令：**
   - 客户端可订阅带 fnmatch 模式的事件流（如 `["step.*", "tool.*"]`）
   - 可选 `replay_from_run`——先从 `events.jsonl` 回放历史再接实时流
6. **TUI 骨架（`tui/app.py`）：**
   - 基于 Textual，连接 daemon → 订阅事件 → 实时渲染
   - 首次展示流式 token、工具调用块、运行状态
7. **将 `agent.run` 注册到 daemon handler**

---

### S3 — 自主规划与 TUI

**要解决的问题：** Agent 能用任务工具拆解复杂目标，TUI 展示完整执行过程。

**要构建的内容：**

1. **TaskManager + 任务工具：**
   - `task_create`、`task_update`、`task_list`、`task_get`
   - 任务持久化到 `.tasks` 目录（JSON 文件）
2. **TUI 增强：**
   - `ToolCallBlock` 可折叠（点击展开 params + output）
   - 流式 Markdown 渲染
   - 上下文水位进度条
   - 工具调用嵌套缩进
3. **Trace 系统（`core/trace/`）：**
   - 三层 trace：ipc（客户端↔核心）、event（EventBus）、llm（LLM 请求/响应）
   - `TracingProvider` 装饰 LLM provider
   - CLI `hcode trace [run_id] --layer ipc|event|llm --follow`

---

### S4 — 会话与记忆

**要解决的问题：** 多轮 run 进入同一个 session，thread 和 notes 接住上下文。Agent 变成"会话伙伴"而非一次性工具。

**要构建的内容：**

1. **SessionManager（`core/session/manager.py`）：**
   - `create(mode: "chat"|"one_shot")` → 创建 session
   - `send_message(sid, content)` → 启动 AgentRunner，chat 模式完事后 `waiting_for_input`
   - 并发保护：每个 session 一个 `asyncio.Lock`
2. **SessionStore（`core/session/store.py`）：**
   - `sessions/<id>/meta.json` + `thread.jsonl` + `notes.jsonl`
   - `sessions/<id>/runs/<run_id>/events.jsonl`
3. **Memory：**
   - `note_save` 工具 → 写入 notes.jsonl + 注入 system prompt
   - `~/.hcode/context.md`（全局）+ `.hcode/context.md`（项目）→ 注入 system prompt
4. **IPC 命令：** `session.create`、`session.send_message`、`session.get_history`、`session.close`
5. **TUI：** 输入框 + 多轮对话历史 + `/` skill 自动补全

---

### S5 — 工具安全

**要解决的问题：** 工具调用不是直接裸跑——有参数校验、权限审批、失败分类和重试。

**要构建的内容：**

1. **PermissionManager（`core/permissions/manager.py`）：**
   - 6 层评估：
     1. deny_patterns（bash only，正则黑名单，不可绕过）
     2. OUTSIDE_CWD 检测（强制 ASK）
     3. session always 缓存（重启丢失）
     4. persistent always 缓存（持久化 `~/.hcode/policy.toml`）
     5. allow_patterns（bash only，正则白名单）
     6. tool default（ALLOW / DENY / ASK）
   - ASK 路径：创建 `asyncio.Future` → 发 `permission.requested` 事件 → 等待客户端 `permission.respond` → 超时自动 deny
2. **`invoke_tool()` 增强：**
   - 参数 pydantic 校验
   - 权限检查（ask 模式挂起等待）
   - `asyncio.wait_for` 限时执行
   - 失败分类：`runtime_error`、`timeout`、`schema_error`、`permission_denied`、`rate_limited`
   - 指数退避重试（最大 2 次，仅 runtime_error 和 rate_limited 可重试）
3. **TUI 权限控件：**
   - `PermissionSelect` 内联控件（y/1=allow once, a/2=always, n/3=deny, d/4=always deny）
   - `PermissionBlock` 审批结果摘要
4. **IPC 命令：** `permission.respond`

---

### S6 — 上下文治理

**要解决的问题：** 长会话下上下文窗口有限——需要有水位检测、tool_result 截断和 compact 压缩。

**要构建的内容：**

1. **Compactor（`core/compact/compactor.py`）：**
   - 用 LLM 将消息历史压缩为 6 段结构化摘要：
     1. 原始目标
     2. 已完成步骤
     3. 关键约束与发现
     4. 当前文件状态
     5. 剩余 TODO
     6. 关键数据（ID、token、错误信息）
   - 摘要持久化到 `summary_<ts>.md`
2. **自动压缩：** AgentLoop 每步后检查 `context_pct >= auto_threshold`，触发就地压缩
3. **手动压缩：** `/compact` 斜杠命令（TUI）+ `session.compact` IPC
4. **tool_result 截断：** 超长结果只保留首尾（`tool_result_limit` / `tool_result_keep`）
5. **配置：** `CompactionConfig`（auto_threshold、tool_result_limit、tool_result_keep）

---

### S7 — 扩展边界

**要解决的问题：** Skills、Subagents、MCP 让 Agent 可组织、可派生、可接外部工具。

**要构建的内容：**

1. **Skills（`core/skills/loader.py`）：**
   - Markdown 格式，frontmatter（name、description、allowed_tools）+ body（system prompt）
   - 三级优先级：项目本地（`.hcode/skills/`）> 用户全局（`~/.hcode/skills/`）> 内建
   - `$ARGUMENTS` 占位符替换
   - 触发：用户输入 `/name` → 展开 prompt → system_prompt_override → tool_whitelist
2. **Subagents（`core/subagent/tool.py`）：**
   - `SpawnAgentTool`：冷启动子 agent，前台阻塞/后台并行
   - `AgentResultTool`：轮询后台任务结果
   - 最大嵌套深度 2 层
   - 子 agent 事件桥接到父 bus
   - `AgentProfileLoader`：按角色（planner/executor/reviewer）加载配置
3. **MCP 集成（`core/mcp/`）：**
   - `McpServerManager`：生命周期管理，支持 stdio 和 TCP
   - `McpClient`：MCP 协议客户端
   - 发现的工具注入每个 run 的 ToolRegistry
4. **TUI：** skill 自动补全弹窗、子 agent 嵌套进度展示

---

## 架构原则（贯穿全部阶段）

1. **双进程架构从 S0 第一天就建立**——不是先写脚本再重构。CLI/TUI 只是客户端，核心逻辑在 daemon。
2. **所有 IPC 消息走类型化协议**——JSON-RPC 2.0 + pydantic discriminated union，`WIRE_PROTOCOL.md` 自动生成。
3. **所有执行过程通过 EventBus 外化**——不是黑盒。事件可订阅、可持久化、可回放。
4. **配置四级优先级**——内建默认 → 用户全局 TOML → 项目本地 TOML → .env → 环境变量。
5. **每个阶段结束都能独立运行和验证**——不是堆到最后一刻才集成。

## 代码风格

所有函数必须在其 `def` 行上方有**一行中文注释**说明功能。不要写多行 docstring。

```python
# 发送 JSON-RPC 响应并刷新写缓冲区
async def _send(self, writer: asyncio.StreamWriter, msg: BaseModel) -> None:
    ...
```

**测试函数**需要上方**两行中文注释**：

```python
# 功能：验证 publish 后订阅者能收到事件对象
# 设计：用内联 handler 收集事件引用，断言 is 而非 ==，排除序列化中间步骤的干扰
async def test_publish_reaches_subscriber() -> None:
    ...
```

- `# 功能：` — 一句话说清"测什么"
- `# 设计：` — 为什么这样测：边界条件、fixture/stub 选择理由、断言方式的优势

两行注释缺一不可。

## 不做什么

- 不追求 1:1 复刻 Claude Code 的所有产品能力——只拆最核心的运行机制
- 不搞微服务、不引入消息队列、不引入数据库——文件系统 + 内存足够
- 不做 Web 前端——TUI 是主要界面，IPC 协议保证未来可以接入
- S0–S3 不引入权限审批——先让 Agent 跑起来，再加安全锁
- 上下文压缩默认关闭（auto_threshold=0.0）——让用户手动 `/compact`
 detailed S0 decisions and rationale
- `agent_functional_outline.md` — full feature catalogue
