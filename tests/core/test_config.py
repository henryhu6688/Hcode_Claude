"""配置系统测试——四级优先级 + 校验"""

import pytest

from hcode_claude.core.config import Config, load_config


# 功能：验证只使用内建默认值时返回正确的 Config
# 设计：不设任何外部配置源，断言 load_config 返回内建默认值
def test_default_config_values():
    cfg = load_config()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 47201
    assert cfg.log_level == "INFO"
    assert cfg.log_file == ""
    assert cfg.log_format == "console"


# 功能：验证环境变量 HCODE_PORT 覆盖默认端口
# 设计：设置环境变量后调用 load_config，断言 port 被覆盖
def test_env_var_overrides_port(monkeypatch):
    monkeypatch.setenv("HCODE_PORT", "9999")
    cfg = load_config()
    assert cfg.port == 9999


# 功能：验证环境变量 HCODE_HOST 覆盖默认 host
# 设计：覆盖 host 为 0.0.0.0
def test_env_var_overrides_host(monkeypatch):
    monkeypatch.setenv("HCODE_HOST", "0.0.0.0")
    cfg = load_config()
    assert cfg.host == "0.0.0.0"


# 功能：验证环境变量 HCODE_LOG_LEVEL 覆盖默认级别
# 设计：设置 DEBUG 后断言生效
def test_env_var_overrides_log_level(monkeypatch):
    monkeypatch.setenv("HCODE_LOG_LEVEL", "DEBUG")
    cfg = load_config()
    assert cfg.log_level == "DEBUG"


# 功能：验证环境变量 HCODE_LOG_FILE 覆盖日志文件路径
# 设计：设为非空路径断言生效
def test_env_var_overrides_log_file(monkeypatch):
    monkeypatch.setenv("HCODE_LOG_FILE", "/tmp/hcode.log")
    cfg = load_config()
    assert cfg.log_file == "/tmp/hcode.log"


# 功能：验证环境变量 HCODE_LOG_FORMAT 覆盖日志格式
# 设计：设为 json 断言生效
def test_env_var_overrides_log_format(monkeypatch):
    monkeypatch.setenv("HCODE_LOG_FORMAT", "json")
    cfg = load_config()
    assert cfg.log_format == "json"


# 功能：验证 .env 文件被加载并覆盖默认值
# 设计：临时目录创建 .env 文件，chdir 后验证覆盖
def test_dotenv_file_overrides_default(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HCODE_PORT=8888\n")
    monkeypatch.chdir(tmp_path)
    # 清除可能存在的环境变量干扰
    monkeypatch.delenv("HCODE_PORT", raising=False)
    cfg = load_config()
    assert cfg.port == 8888


# 功能：验证用户 config.toml 被加载并覆盖默认值
# 设计：创建 ~/.hcode/config.toml，设置 HCODE_HOME 指向 tmp_path
def test_user_config_toml_overrides_default(monkeypatch, tmp_path):
    hcode_dir = tmp_path / ".hcode"
    hcode_dir.mkdir()
    config_file = hcode_dir / "config.toml"
    config_file.write_text('port = 7777\nhost = "10.0.0.1"\n')
    monkeypatch.setenv("HCODE_HOME", str(tmp_path))
    monkeypatch.delenv("HCODE_PORT", raising=False)
    monkeypatch.delenv("HCODE_HOST", raising=False)
    cfg = load_config()
    assert cfg.port == 7777
    assert cfg.host == "10.0.0.1"


# 功能：验证环境变量优先级高于 .env 和 config.toml
# 设计：三层同时设置 port，断言环境变量胜出
def test_env_var_wins_over_all(monkeypatch, tmp_path):
    hcode_dir = tmp_path / ".hcode"
    hcode_dir.mkdir()
    (hcode_dir / "config.toml").write_text('port = 1111\n')
    (tmp_path / ".env").write_text('HCODE_PORT=2222\n')
    monkeypatch.setenv("HCODE_HOME", str(tmp_path))
    monkeypatch.setenv("HCODE_PORT", "3333")
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.port == 3333


# 功能：验证未知配置 key 触发 SystemExit
# 设计：config.toml 写入未定义 key，load_config 应调用 sys.exit(1)
def test_unknown_config_key_causes_hard_exit(monkeypatch, tmp_path):
    hcode_dir = tmp_path / ".hcode"
    hcode_dir.mkdir()
    (hcode_dir / "config.toml").write_text('unknown_key = "value"\n')
    monkeypatch.setenv("HCODE_HOME", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        load_config()
    assert exc_info.value.code == 1


# 功能：验证 Config 是 frozen dataclass，不可修改
# 设计：尝试修改属性触发 FrozenInstanceError
def test_config_is_frozen():
    cfg = Config(host="127.0.0.1", port=47201, log_level="INFO", log_file="", log_format="console")
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        cfg.port = 9999  # type: ignore[misc]
