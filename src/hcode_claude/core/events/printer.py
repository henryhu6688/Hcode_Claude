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
