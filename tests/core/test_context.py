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
