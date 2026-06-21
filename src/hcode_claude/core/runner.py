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
        try:
            loop = AgentLoop(ctx, provider, registry, bus)
            result = await loop.run(goal, max_steps=cfg.max_steps)
        except Exception as e:
            finished = RunFinishedEvent(
                type="run.finished", run_id=run_id, status="error", steps=0,
            )
            await bus.publish(finished)
            return RunResult(
                type="run.result",
                run_id=run_id,
                status="error",
                steps=0,
                output=str(e),
            )

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
