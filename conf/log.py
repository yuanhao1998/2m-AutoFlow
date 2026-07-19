"""统一日志配置。

用法:
    from conf.log import add_log
    add_log()  # 从 conf/config.yaml 读取级别，同时输出终端和文件

    import logging
    logging.info("root 日志")
    logger = logging.getLogger(__name__)
    logger.info("模块日志")
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ruamel.yaml import YAML

_CONFIG_DIR = Path(__file__).parent
_DEFAULT_CONFIG = _CONFIG_DIR / "config.yaml"
_LOG_DIR = _CONFIG_DIR.parent / "logs"
_FLOWS_DIR = _CONFIG_DIR.parent / "flows"


def add_log(config_path: str | None = None, log_file: str | None = None) -> None:
    """配置 root logger：终端 + 文件双输出。

    多次调用安全：已有 handler 时跳过。

    Args:
        config_path: 配置文件路径，默认 conf/config.yaml。
        log_file: 日志文件名，默认 logs/app.log（自动轮转 5MB×3）。
    """
    if logging.getLogger().handlers:
        return

    cfg_path = Path(config_path) if config_path else _DEFAULT_CONFIG
    level = _read_level(cfg_path)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    # 终端输出
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logging.getLogger().addHandler(console)

    # 文件输出
    _LOG_DIR.mkdir(exist_ok=True)
    file_path = _LOG_DIR / (log_file or "app.log")
    file_handler = RotatingFileHandler(
        str(file_path), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logging.getLogger().addHandler(file_handler)

    logging.getLogger().setLevel(level)


def _read_level(config_path: Path) -> int:
    if not config_path.exists():
        return logging.INFO

    yaml = YAML(typ="safe")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.load(f)

    level_name = (cfg or {}).get("logging", {}).get("level", "INFO")
    return getattr(logging, level_name.upper(), logging.INFO)


def setup_flow_logger(flow_name: str) -> logging.Logger:
    """为流程创建独立 logger，双输出：终端 + logs/<flow_name>.log。

    Args:
        flow_name: 流程名，用于日志文件名和 logger 层级名。

    Returns:
        logging.Logger 实例，可被子 logger 继承。
    """
    logger = logging.getLogger(f"flow.{flow_name}")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    # 终端输出
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 流程独立日志文件
    _LOG_DIR.mkdir(exist_ok=True)
    file_path = _LOG_DIR / f"{flow_name}.log"
    file_handler = RotatingFileHandler(
        str(file_path), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def _discover_flow_loggers() -> None:
    """扫描 flows/ 目录下所有 .py 文件（排除 __init__.py），自动注册同名 logger。"""
    if not _FLOWS_DIR.is_dir():
        return
    for f in sorted(_FLOWS_DIR.iterdir()):
        if f.suffix == ".py" and f.stem != "__init__":
            setup_flow_logger(f.stem)


def register_log():
    add_log()
    _discover_flow_loggers()