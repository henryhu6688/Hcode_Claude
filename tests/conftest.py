"""测试 fixtures——free_port 和 running_daemon"""

import socket

import pytest


# 返回空闲端口号：bind port 0 → getsockname → close → 返回端口号
@pytest.fixture
def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
