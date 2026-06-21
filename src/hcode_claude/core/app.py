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
