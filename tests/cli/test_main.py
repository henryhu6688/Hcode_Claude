"""CLI 入口测试"""

import os
import subprocess
import sys

# 确保 src/ 在 PYTHONPATH 中——uv sync 不做 editable install，子进程需要显式路径
_TESTS_ENV = os.environ.copy()
_TESTS_ENV["PYTHONPATH"] = "src"


# 功能：验证 hcode --version 输出 "hcode v0.0.1"
# 设计：用 subprocess 调用 python -m hcode_claude.cli.main --version，PYTHONPATH=src
def test_cli_version():
    result = subprocess.run(
        [sys.executable, "-m", "hcode_claude.cli.main", "--version"],
        capture_output=True,
        text=True,
        env=_TESTS_ENV,
    )
    assert result.returncode == 0
    assert "hcode v0.0.1" in result.stdout.strip()


# 功能：验证 hcode --help 输出使用说明
# 设计：无参数调用默认显示 help，PYTHONPATH=src
def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "hcode_claude.cli.main", "--help"],
        capture_output=True,
        text=True,
        env=_TESTS_ENV,
    )
    assert result.returncode == 0
    assert "hcode ping" in result.stdout


# 功能：验证 hcode ping 不带 daemon 运行时输出错误
# 设计：daemon 未启动，应报连接失败并 exit 1
def test_ping_without_daemon_fails():
    result = subprocess.run(
        [
            sys.executable, "-m", "hcode_claude.cli.main",
            "ping", "--port", "1",
            "--host", "127.0.0.1",
        ],
        capture_output=True,
        text=True,
        env=_TESTS_ENV,
    )
    assert result.returncode != 0
