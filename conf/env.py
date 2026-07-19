"""从项目根目录的 .env 文件读取本地配置（不提交到 git）。"""

from pathlib import Path

_ENV_PATH = Path(__file__).parent.parent / ".env"


def get_env(key: str, default: str = "") -> str:
    """读取 .env 文件中的键值。

    .env 格式:
        KEY=VALUE
        KEY="VALUE"
        # 注释行

    Args:
        key: 键名。
        default: 未找到时的默认值。
    """
    if not _ENV_PATH.exists():
        return default
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return default
