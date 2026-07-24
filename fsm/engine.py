"""引擎主循环：识别当前界面 → 处理 → 自愈，直到目标态。"""

from __future__ import annotations

import logging
import time

from fsm.state import State, Done, Goto, Back, Stay

logger = logging.getLogger(__name__)

# Goto 等待：快速重试 N 次后切换为慢速，不降级为全量识别
GOTO_FAST_RETRIES = 10     # 快速重试次数（间隔 unknown_wait）
GOTO_SLOW_INTERVAL = 2.0   # 慢速重试间隔（秒），用于长过渡（如传送加载）
GOTO_MAX_RETRIES = 60      # 总重试上限，超过则真正超时


class Engine:
    """驱动状态机运行的主循环。"""

    def __init__(self, registry, ctx, *, max_steps: int = 200,
                 max_unknown: int = 5, on_unknown=None,
                 unknown_wait: float = 0.5,
                 debug_interval: int = 5) -> None:
        self.registry = registry
        self.ctx = ctx
        self.max_steps = max_steps
        self.max_unknown = max_unknown
        self._on_unknown = on_unknown or _default_on_unknown
        self._unknown_wait = unknown_wait    # 未知态轮询间隔（秒）
        self._debug_interval = debug_interval  # 每 N 次未知态才保存一张截图

    def run_until(self, goal: type[State] | None = None, *,
                  max_steps: int | None = None,
                  max_unknown: int | None = None) -> bool:
        """循环直到收到 Done 信号（或抵达 goal 界面）。返回是否成功。

        尊重 Goto 信号：handle() 返回 Goto(X) 后，下一轮优先匹配 X（+ 弹框），
        X 不匹配时等待重试（过渡动画），超时后降级为全量识别。

        goal=None 时只靠 handler 返回 Done() 终止，不绑定特定界面。
        """
        max_steps = max_steps if max_steps is not None else self.max_steps
        max_unknown = max_unknown if max_unknown is not None else self.max_unknown

        # 每轮开始重置流程状态（切换云机后尤为重要）
        if self.registry.reset_flow:
            self.registry.reset_flow()

        unknown = 0
        last_debug_at = -self._debug_interval
        _expected: type[State] | None = None
        _goto_retries = 0
        self.ctx.registry = self.registry  # 让 State 能访问注册表

        for _ in range(max_steps):
            self.ctx.check_state()
            self.ctx.refresh_screenshot()
            if not self.ctx.calibrator.is_valid():
                self.ctx.calibrator.calibrate()

            # 识别：弹框始终优先，其次看 _expected
            state = self.registry.identify(self.ctx, expected=_expected)
            if state is None:
                if _expected is not None:
                    # Goto 等待：目标状态还未出现（过渡动画 / 加载中）
                    _goto_retries += 1
                    if _goto_retries > GOTO_MAX_RETRIES:
                        logger.error("Goto 等待超时（%d 次），目标状态 %s 未出现",
                                    _goto_retries, _expected.__name__)
                        return False
                    elif _goto_retries == GOTO_FAST_RETRIES:
                        logger.info("Goto 慢速等待 %s（传送/加载中...）",
                                   _expected.__name__)
                    wait = (self._unknown_wait if _goto_retries < GOTO_FAST_RETRIES
                            else GOTO_SLOW_INTERVAL)
                    time.sleep(wait)
                    continue

                unknown += 1
                logger.warning("未识别当前界面（连续 %d 次）", unknown)
                if unknown > max_unknown:
                    logger.error("连续未知态超过 %d 次，中止", max_unknown)
                    return False
                if unknown - last_debug_at >= self._debug_interval:
                    self._on_unknown(self.ctx)
                    last_debug_at = unknown
                time.sleep(self._unknown_wait)
                continue

            unknown = 0
            last_debug_at = -self._debug_interval
            if goal is not None and isinstance(state, goal):
                logger.info("已抵达目标界面: %s", state.name or type(state).__name__)
                return True

            logger.info("当前界面: %s → 处理", state.name or type(state).__name__)
            sig = state.handle(self.ctx)

            if isinstance(sig, Done):
                logger.info("收到 Done，结束")
                return True
            elif isinstance(sig, Goto):
                logger.info("→ Goto %s", sig.target.__name__)
                _expected = sig.target
                _goto_retries = 0
            elif isinstance(sig, (Back, Stay)):
                _expected = None
                _goto_retries = 0
                if isinstance(sig, Stay):
                    logger.info("→ Stay（全量识别）")

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
