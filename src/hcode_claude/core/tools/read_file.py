"""读取文件工具——读取指定路径的文件内容"""

from pathlib import Path
from typing import Any

from hcode_claude.core.tools.base import BaseTool


class ReadFileTool(BaseTool):
    """读取指定文件的内容"""

    name = "read_file"
    description = "读取文件内容。参数 path: 文件路径（相对于工作目录或绝对路径）"

    # 绑定工作目录，限制文件访问范围
    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要读取的文件路径"},
            },
            "required": ["path"],
        }

    # 读取文件：校验路径在 cwd 内 → Path.read_text
    async def invoke(self, params: dict[str, Any]) -> str:
        target = Path(params["path"])
        if not target.is_absolute():
            target = self._cwd / target
        target = target.resolve()
        # 安全校验：禁止读取 cwd 外的文件
        if not str(target).startswith(str(self._cwd.resolve())):
            return f"Error: access denied — path outside working directory: {target}"
        if not target.is_file():
            return f"Error: not a file: {target}"
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error: {e}"
