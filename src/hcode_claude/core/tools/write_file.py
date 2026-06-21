"""写入文件工具——写入内容到指定路径的文件"""

from pathlib import Path
from typing import Any

from hcode_claude.core.tools.base import BaseTool


class WriteFileTool(BaseTool):
    """写入内容到指定文件，父目录不存在时自动创建"""

    name = "write_file"
    description = "写入内容到文件。参数 path: 文件路径, content: 要写入的内容"

    # 绑定工作目录，限制文件写入范围
    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "要写入的内容"},
            },
            "required": ["path", "content"],
        }

    # 写入文件：校验路径在 cwd 内 → 创建父目录 → Path.write_text
    async def invoke(self, params: dict[str, Any]) -> str:
        target = Path(params["path"])
        if not target.is_absolute():
            target = self._cwd / target
        target = target.resolve()
        if not str(target).startswith(str(self._cwd.resolve())):
            return f"Error: access denied — path outside working directory: {target}"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(params["content"], encoding="utf-8")
            return f"Wrote {target.stat().st_size} bytes to {target}"
        except Exception as e:
            return f"Error: {e}"
