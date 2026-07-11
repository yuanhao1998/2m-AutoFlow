# game-auto

分辨率无关、可自愈的视觉自动化引擎。锚点相对定位 + 声明式状态机。

设计文档见 `docs/superpowers/specs/`，实现计划见 `docs/superpowers/plans/`。

## 环境（务必用虚拟环境，勿装进系统 Python）
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

## 运行
    .venv/bin/python run.py

## 测试
    .venv/bin/python -m pytest

> 提示：可先 `source .venv/bin/activate` 后直接用 `python`/`pytest`。
> 采集锚点图与界面探针同理：`.venv/bin/python tools/capture_anchor.py`、`.venv/bin/python tools/whereami.py`。
