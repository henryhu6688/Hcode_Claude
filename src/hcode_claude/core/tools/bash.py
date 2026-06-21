"""Bash 工具——执行 shell 命令并返回 stdout/stderr"""

import asyncio
from pathlib import Path
from typing import Any

from hcode_claude.core.tools.base import BaseTool


class BashTool(BaseTool):
    """执行 shell 命令，超时自动终止并返回输出"""

    name = "bash"
    description = "执行 shell 命令。参数 command: 要执行的命令"

    # 绑定工作目录和超时时间
    def __init__(self, cwd: Path, timeout: int = 60) -> None:
        self._cwd = cwd
        self._timeout = timeout

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 shell 命令"},
            },
            "required": ["command"],
        }

    # 执行命令：asyncio subprocess → stdout/stderr 截断 → 超时 kill
    async def invoke(self, params: dict[str, Any]) -> str:
        command = params["command"]
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._cwd),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            out = stdout.decode("utf-8", errors="replace")[:5000]
            err = stderr.decode("utf-8", errors="replace")[:5000]
            parts = []
            if out:
                parts.append(out)
            if err:
                parts.append(f"[stderr]\n{err}")
            return "\n".join(parts) if parts else f"(exit code {proc.returncode})"
        except TimeoutError:
            return "Error: command timed out"
        except Exception as e:
            return f"Error: {e}"
