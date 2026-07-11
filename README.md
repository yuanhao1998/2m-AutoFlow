# game-auto

分辨率无关、可自愈的视觉自动化引擎。锚点相对定位 + 声明式状态机。

设计文档见 `docs/superpowers/specs/`，实现计划见 `docs/superpowers/plans/`。

## 环境（推荐 uv，勿装进系统 Python）

依赖以 `pyproject.toml` 为准，`uv.lock` 锁定精确版本。

    uv sync                 # 按 uv.lock 创建 .venv 并安装依赖（含 dev 的 pytest）
    uv run run.py           # 运行入口（按 F5 开始）
    uv run pytest           # 跑测试
    uv run tools/capture_anchor.py   # 采集锚点图
    uv run tools/whereami.py         # 界面探针

生产环境可 `uv sync --no-dev` 排除 pytest。

### 不用 uv 时（pip 回退）
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python run.py
    .venv/bin/python -m pytest
