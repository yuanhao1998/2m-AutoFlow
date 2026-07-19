"""引擎主循环：识别当前界面 → 处理 → 自愈，直到目标态。"""

from __future__ import annotations

import logging

from fsm.state import State, Done

logger = logging.getLogger(__name__)


class Engine:
    """驱动状态机运行的主循环。"""

    def __init__(self, registry, ctx, *, max_steps: int = 200,
                 max_unknown: int = 5, on_unknown=None) -> None:
        self.registry = registry
        self.ctx = ctx
        self.max_steps = max_steps
        self.max_unknown = max_unknown
        self._on_unknown = on_unknown or _default_on_unknown

    def run_until(self, goal: type[State] | None = None, *,
                  max_steps: int | None = None,
                  max_unknown: int | None = None) -> bool:
        """循环直到收到 Done 信号（或抵达 goal 界面）。返回是否成功。

        goal=None 时只靠 handler 返回 Done() 终止，不绑定特定界面——
        适合流程中途会经过相同界面多次的场景（如 Home→任务→Home→领奖→Home）。
        goal 非空时与旧行为一致：识别到 goal 界面或收到 Done 均终止。
        """
        max_steps = max_steps if max_steps is not None else self.max_steps
        max_unknown = max_unknown if max_unknown is not None else self.max_unknown
        unknown = 0

        for _ in range(max_steps):
            self.ctx.check_state()
            self.ctx.refresh_screenshot()
            if not self.ctx.calibrator.is_valid():
                self.ctx.calibrator.calibrate()

            state = self.registry.identify(self.ctx)
            if state is None:
                unknown += 1
                logger.warning("未识别当前界面（连续 %d 次）", unknown)
                if unknown > max_unknown:
                    logger.error("连续未知态超过 %d 次，中止", max_unknown)
                    return False
                self._on_unknown(self.ctx)
                continue

            unknown = 0
            if goal is not None and isinstance(state, goal):
                logger.info("已抵达目标界面: %s", state.name or type(state).__name__)
                return True

            logger.info("当前界面: %s → 处理", state.name or type(state).__name__)
            sig = state.handle(self.ctx)
            if isinstance(sig, Done):
                logger.info("收到 Done，结束")
                return True
            # Goto / Back / Stay / None → 下一轮重新识别

        logger.error("超过最大步数 %d，未结束", max_steps)
        return False


def _default_on_unknown(ctx) -> None:
    """未知态默认处理：保存调试截图。"""
    try:
        from pathlib import Path
        from datetime import datetime
        import cv2
        debug_dir = Path("data/debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        if ctx.screen_bgr is not None:
            cv2.imwrite(str(debug_dir / f"unknown_{ts}.png"), ctx.screen_bgr)
            logger.warning("未知态截图已保存 data/debug/unknown_%s.png", ts)
    except Exception:
        logger.exception("保存未知态截图失败")
