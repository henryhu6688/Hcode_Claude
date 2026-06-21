"""Event 判别联合测试"""

import json

import pytest
from pydantic import ValidationError

from hcode_claude.core.protocol.events import (
    CoreStartedEvent,
    LlmModelSelectedEvent,
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
    obj = json.loads(raw)
    assert obj["type"] == "core.started"
    assert obj["host"] == "0.0.0.0"
    assert obj["port"] == 9999
    assert obj["version"] == "1.2.3"


# 功能：验证 CoreStartedEvent port 不接受非数字类型
# 设计：pydantic v2 默认强制 string→int，但 list→int 不可强转，应触发 ValidationError
def test_core_started_event_port_rejects_list():
    with pytest.raises(ValidationError):
        CoreStartedEvent(type="core.started", host="127.0.0.1", port=[1, 2, 3], version="0.0.1")  # type: ignore[arg-type]


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
