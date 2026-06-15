"""集成测试：启动 daemon → core.ping → 校验 pong"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


# 功能：验证完整的 ping/pong 流程——daemon 启动 → 发 ping → 收 pong
# 设计：用 free_port 启动子进程 daemon，轮询 TCP 直到可达，发请求并验证响应
@pytest.mark.asyncio
async def test_daemon_ping_pong(free_port: int, tmp_path: Path):
    # PYTHONPATH=src 使其能找到 hcode_claude
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["HCODE_PORT"] = str(free_port)
    env["HCODE_LOG_FILE"] = str(tmp_path / "hcode.log")
    env["HCODE_HOME"] = str(tmp_path)  # 避免读取真实的 ~/.hcode/config.toml

    # 启动 daemon 子进程
    proc = subprocess.Popen(
        [sys.executable, "-m", "hcode_claude.core.app"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # 轮询等待 daemon TCP 就绪（最多 5 秒）
        connected = False
        for _ in range(50):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", free_port),
                    timeout=0.3,
                )
                connected = True
                break
            except (TimeoutError, ConnectionRefusedError, OSError):
                if proc.poll() is not None:
                    # daemon 已经挂了
                    stdout, stderr = proc.communicate()
                    pytest.fail(
                        f"Daemon exited early (code={proc.returncode})\n"
                        f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
                    )
                await asyncio.sleep(0.1)

        assert connected, "Cannot connect to daemon after 5s"

        # 发送 core.ping
        nonce = "test-nonce-123"
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": nonce,
            "method": "core.ping",
            "params": {"nonce": nonce},
        }) + "\n"
        writer.write(request.encode())
        await writer.drain()

        # 读取响应
        line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        response = json.loads(line.decode())

        writer.close()

        # 校验响应
        assert "result" in response, f"Expected success, got: {response}"
        assert response["id"] == nonce
        assert response["result"]["type"] == "pong"
        assert response["result"]["nonce"] == nonce
        assert response["result"]["server_version"] == "0.0.1"

    finally:
        # 不管测试结果如何都要杀掉 daemon（跨平台 terminate）
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
