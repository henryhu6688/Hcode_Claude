"""工具注册表——管理所有工具实例，提供注册、查找、导出 Anthropic tool schema"""

from hcode_claude.core.tools.base import BaseTool


class ToolRegistry:
    """持有所有已注册工具，提供 Anthropic API 兼容的 tool 定义列表"""

    # 初始化空注册表
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # 注册一个工具实例（同名覆盖）
    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    # 按名称查找工具，找不到抛出 KeyError
    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    # 导出 Anthropic API 兼容的 tools 列表
    def as_anthropic_tools(self) -> list[dict[str, object]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]
