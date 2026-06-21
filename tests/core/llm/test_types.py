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
