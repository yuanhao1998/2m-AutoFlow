"""实时探针：每隔 1 秒截图并打印当前命中的 State，用于调试状态机 signature。

用法:
    python tools/whereami.py
需先在下方 build_registry() 中注册要检测的 State（或 import 冒烟流程的注册表）。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from conf.log import add_log
from calib.calibrator import Calibrator
from anchors.anchors import Anchor, ImageRef
from fsm.context import Ctx, RunState
from fsm.registry import StateRegistry


def build_registry() -> StateRegistry:
    """在此注册要检测的 State。默认从冒烟流程导入。"""
    from flows.smoke import build_registry as smoke_registry
    return smoke_registry()


def build_calibrator() -> Calibrator:
    from ruamel.yaml import YAML
    cfg = YAML(typ="safe").load(open("conf/config.yaml", encoding="utf-8"))
    c = cfg["calib"]
    anchor = Anchor(ref=ImageRef(c["anchor"]), threshold=float(c["threshold"]))
    return Calibrator(anchor, tuple(c["anchor_authoring_topleft"]),
                      threshold=float(c["threshold"]))


def main() -> None:
    add_log()
    registry = build_registry()
    calibrator = build_calibrator()
    ctx = Ctx(calibrator, RunState())
    ctx.refresh_screenshot()
    if not calibrator.calibrate(ctx.screen_bgr):
        print("标定失败：请检查 conf/config.yaml 的 calib.anchor")
        return
    print("开始探测（Ctrl+C 退出）...")
    try:
        while True:
            ctx.refresh_screenshot()
            state = registry.identify(ctx)
            name = state.name if state else "未知界面"
            print(f"当前界面: {name}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("退出")


if __name__ == "__main__":
    main()
