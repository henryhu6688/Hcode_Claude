"""配置系统——四级优先级：内建默认 → ~/.hcode/config.toml → .env → 环境变量"""

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

# S0 合法配置键集合
_VALID_KEYS = {"host", "port", "log_level", "log_file", "log_format"}

# 内建默认值
_DEFAULTS: dict[str, object] = {
    "host": "127.0.0.1",
    "port": 47201,
    "log_level": "INFO",
    "log_file": "",
    "log_format": "console",
}

# env var → config key 映射
_ENV_MAP = {
    "HCODE_HOST": "host",
    "HCODE_PORT": "port",
    "HCODE_LOG_LEVEL": "log_level",
    "HCODE_LOG_FILE": "log_file",
    "HCODE_LOG_FORMAT": "log_format",
}


@dataclass(frozen=True)
class Config:
    """Hcode daemon 不可变配置"""

    host: str
    port: int
    log_level: str
    log_file: str
    log_format: str


# 加载用户级 ~/.hcode/config.toml，返回键值字典
def _load_user_toml() -> dict[str, object]:
    home = os.environ.get("HCODE_HOME", str(Path.home()))
    toml_path = Path(home) / ".hcode" / "config.toml"
    if not toml_path.is_file():
        return {}
    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)
    # 类型收窄：tomllib 返回 dict[str, Any]，所有值应为基础类型
    result: dict[str, object] = {}
    for k, v in raw.items():
        if k not in _VALID_KEYS:
            print(f"Unknown config key: {k}", file=sys.stderr)
            sys.exit(1)
        result[k] = v
    return result


# 加载当前目录的 .env 文件（如存在），提取 HCODE_ 前缀变量
def _load_dotenv_values() -> dict[str, object]:
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return {}
    try:
        from dotenv import dotenv_values
    except ImportError:
        return {}
    raw = dotenv_values(dotenv_path=str(dotenv_path))
    result: dict[str, object] = {}
    for env_key, config_key in _ENV_MAP.items():
        if env_key in raw:
            result[config_key] = raw[env_key]
    return result


# 从环境变量提取 HCODE_ 前缀配置
def _load_env_values() -> dict[str, object]:
    result: dict[str, object] = {}
    for env_key, config_key in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is not None:
            result[config_key] = val
    return result


# 类型转换：将字符串值转为目标字段类型
def _coerce(key: str, value: object) -> object:
    if key == "port":
        return int(value)
    return str(value)


# 加载配置：四级合并（内建默认 → ~/.hcode/config.toml → .env → 环境变量）
def load_config() -> Config:
    merged: dict[str, object] = dict(_DEFAULTS)

    # 第一层：用户 TOML
    for k, v in _load_user_toml().items():
        merged[k] = v

    # 第二层：.env
    for k, v in _load_dotenv_values().items():
        merged[k] = v

    # 第三层：环境变量（最高优先级）
    for k, v in _load_env_values().items():
        merged[k] = v

    # 类型转换
    return Config(
        host=_coerce("host", merged["host"]),
        port=_coerce("port", merged["port"]),
        log_level=_coerce("log_level", merged["log_level"]),
        log_file=_coerce("log_file", merged["log_file"]),
        log_format=_coerce("log_format", merged["log_format"]),
    )


# 根据 Config 初始化 structlog
def setup_logging(cfg: Config) -> None:
    import logging

    import structlog

    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level)

    renderer = (
        structlog.dev.ConsoleRenderer()
        if cfg.log_format == "console"
        else structlog.processors.JSONRenderer()
    )

    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,
        renderer,
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if cfg.log_file:
        file_handler = logging.FileHandler(cfg.log_file)
        logging.getLogger().addHandler(file_handler)
