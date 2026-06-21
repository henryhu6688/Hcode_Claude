"""内建工具测试"""

from pathlib import Path

import pytest

from hcode_claude.core.tools.bash import BashTool
from hcode_claude.core.tools.list_dir import ListDirTool
from hcode_claude.core.tools.read_file import ReadFileTool
from hcode_claude.core.tools.write_file import WriteFileTool


# 功能：验证 read_file 读取文件内容
# 设计：临时目录创建文件，读取后断言内容一致
@pytest.mark.asyncio
async def test_read_file(tmp_path: Path):
    file = tmp_path / "test.txt"
    file.write_text("hello world")
    tool = ReadFileTool(cwd=tmp_path)
    result = await tool.invoke({"path": str(file)})
    assert "hello world" in result


# 功能：验证 read_file 拒绝工作目录外的路径
# 设计：传 /etc/passwd 应被拒绝
@pytest.mark.asyncio
async def test_read_file_rejects_outside_cwd(tmp_path: Path):
    tool = ReadFileTool(cwd=tmp_path)
    result = await tool.invoke({"path": "/etc/passwd"})
    assert "outside" in result.lower() or "denied" in result.lower()


# 功能：验证 write_file 写入内容到文件
# 设计：写入后读回校验，父目录不存在时自动创建
@pytest.mark.asyncio
async def test_write_file(tmp_path: Path):
    tool = WriteFileTool(cwd=tmp_path)
    file = tmp_path / "subdir" / "out.txt"
    result = await tool.invoke({"path": str(file), "content": "new content"})
    # 成功时至少不包含 Error 前缀
    assert result != ""
    assert file.read_text() == "new content"


# 功能：验证 bash 执行 shell 命令
# 设计：执行 echo 命令，断言 stdout 包含预期输出
@pytest.mark.asyncio
async def test_bash_echo(tmp_path: Path):
    tool = BashTool(cwd=tmp_path)
    result = await tool.invoke({"command": "echo hello_from_bash"})
    assert "hello_from_bash" in result


# 功能：验证 bash 命令超时报错
# 设计：sleep 10 超过默认 2s 超时，应报 timeout
@pytest.mark.asyncio
async def test_bash_timeout(tmp_path: Path):
    tool = BashTool(cwd=tmp_path, timeout=2)
    result = await tool.invoke({"command": "sleep 10"})
    assert "timed out" in result.lower()


# 功能：验证 list_dir 列出目录内容
# 设计：临时目录创建文件和子目录，断言输出包含
@pytest.mark.asyncio
async def test_list_dir(tmp_path: Path):
    (tmp_path / "a.txt").touch()
    (tmp_path / "sub").mkdir()
    tool = ListDirTool(cwd=tmp_path)
    result = await tool.invoke({"path": str(tmp_path)})
    assert "a.txt" in result
    assert "sub" in result


# 功能：验证 list_dir 拒绝非目录路径
# 设计：传文件路径应报错
@pytest.mark.asyncio
async def test_list_dir_rejects_file(tmp_path: Path):
    file = tmp_path / "f.txt"
    file.touch()
    tool = ListDirTool(cwd=tmp_path)
    result = await tool.invoke({"path": str(file)})
    assert "not a directory" in result.lower() or "error" in result.lower()
