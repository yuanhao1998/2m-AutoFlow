#!/usr/bin/env python3
"""实时状态探针：持续截图并打印当前命中哪个 State。

用法:
    python -m tools.whereami

操作:
    Ctrl+C 退出
"""

import time


def _load_registry():
    """懒加载烟雾测试的状态注册表（需先完成 flows/smoke.py）。"""
    from flows.smoke import build_registry
    return build_registry()


def main():
    from fsm.registry import StateRegistry
    from fsm.context import Ctx, RunState
    from core.capture import fullscreen_screenshot
    from core.vision import to_bgr

    registry = _load_registry()

    # 简易标定器：作画坐标 == 屏幕坐标（1:1）
    class _DummyCal:
        scale = 1.0
        origin = (0, 0)

        def to_screen_region(self, region):
            return region

        def is_valid(self):
            return True

        def invalidate(self):
            pass

    ctx = Ctx(calibrator=_DummyCal(), run_state=RunState())

    print("状态探针启动 — 每秒刷新 (Ctrl+C 退出)")
    try:
        while True:
            ctx.refresh_screenshot()
            st = registry.identify(ctx)
            name = st.name if st else "未知"
            print(f"[{time.strftime('%H:%M:%S')}] {name}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止")


if __name__ == "__main__":
    main()
