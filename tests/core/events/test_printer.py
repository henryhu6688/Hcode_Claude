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
