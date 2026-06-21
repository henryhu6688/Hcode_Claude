"""工具基类——定义 name、description、input_schema、invoke 接口"""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """所有工具的抽象基类"""
    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """返回 JSON Schema dict，传给 LLM API"""
        ...

    @abstractmethod
    async def invoke(self, params: dict[str, Any]) -> str:
        """执行工具，返回结果文本"""
        ...
