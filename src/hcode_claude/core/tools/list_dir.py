"""列出目录工具——列出指定目录下的文件和子目录"""

from pathlib import Path
from typing import Any

from hcode_claude.core.tools.base import BaseTool


class ListDirTool(BaseTool):
    """列出目录内容，返回文件名列表"""

    name = "list_dir"
    description = "列出目录中的文件和子目录。参数 path: 目录路径"

    # 绑定工作目录，限制访问范围
    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要列出的目录路径"},
            },
            "required": ["path"],
        }

    # 列出目录：校验路径 → iterdir → 按类型标记 → 排序返回
    async def invoke(self, params: dict[str, Any]) -> str:
        target = Path(params["path"])
        if not target.is_absolute():
            target = self._cwd / target
        target = target.resolve()
        if not str(target).startswith(str(self._cwd.resolve())):
            return f"Error: access denied — path outside working directory: {target}"
        if not target.is_dir():
            return f"Error: not a directory: {target}"
        try:
            lines = []
            for entry in sorted(target.iterdir()):
                prefix = "[DIR] " if entry.is_dir() else "[FILE]"
                lines.append(f"{prefix} {entry.name}")
            return "\n".join(lines) if lines else "(empty directory)"
        except Exception as e:
            return f"Error: {e}"
