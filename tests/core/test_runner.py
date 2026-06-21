"""AgentRunner 测试"""

from pathlib import Path

import pytest

from hcode_claude.core.runner import AgentRunner


# 功能：验证 AgentRunner 有 run 方法
# 设计：AgentRunner 是 daemon handler 的入口，必须有 run
def test_agent_runner_has_run_method():
    runner = AgentRunner()
    assert hasattr(runner, "run")
    assert callable(runner.run)


# 功能：验证 run 方法返回 RunResult 并写入 events.jsonl
# 设计：用 tmp_path 作为 run_dir，传入简单 goal 验证能跑通
@pytest.mark.asyncio
async def test_agent_runner_run_simple_goal(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HCODE_HOME", str(tmp_path))
    monkeypatch.setenv("HCODE_ANTHROPIC_API_KEY", "test-key")

    runner = AgentRunner()
    run_dir = tmp_path / "runs" / "test-run"
    run_dir.mkdir(parents=True)

    result = await runner.run(goal="echo hello", run_dir=run_dir)
    assert result.status in ("completed", "max_steps", "error")
    if result.status != "error":
        assert result.steps > 0
    assert result.run_id == "test-run"

    # 验证 events.jsonl 已写入
    events_file = run_dir / "events.jsonl"
    assert events_file.exists()
    lines = events_file.read_text().strip().split("\n")
    assert len(lines) >= 2  # 至少有 RunStarted + RunFinished
