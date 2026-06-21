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
