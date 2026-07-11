"""FlowRunner：全局热键监听 + 多轮账户循环。"""

from __future__ import annotations

import logging
import time

from pynput import keyboard

from fsm.context import RunState, StopFlow

logger = logging.getLogger(__name__)

DEFAULT_HOTKEYS = {"start": "f5", "pause": "f6", "stop": "f7", "exit": "esc"}


class FlowRunner:
    """管理热键与循环，驱动一轮轮业务执行。"""

    def __init__(self, run_state: RunState, *, repeat: int = 1,
                 hotkeys: dict | None = None, switch=None) -> None:
        self._state = run_state
        self._repeat = repeat
        self._hotkeys = {**DEFAULT_HOTKEYS, **(hotkeys or {})}
        self._switch = switch
        self._listener: keyboard.Listener | None = None

    def run(self, target) -> None:
        """启动热键，等待 start 后循环执行 target()（一轮业务）。"""
        hk = self._hotkeys

        def on_press(key) -> None:
            k = _key_name(key)
            if k == hk["start"]:
                self._state.running = True
                self._state.paused = False
                logger.info("▶ 开始")
            elif k == hk["pause"]:
                self._state.paused = not self._state.paused
                logger.info("⏸ 暂停" if self._state.paused else "▶ 继续")
            elif k == hk["stop"]:
                self._state.stopped = True
                self._state.paused = False
                logger.info("⏹ 停止")
            elif k == hk["exit"]:
                self._state.stopped = True
                if self._listener:
                    self._listener.stop()

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

        logger.info("等待按 %s 开始...", hk["start"].upper())
        while not self._state.running and not self._state.stopped:
            time.sleep(0.1)
        if self._state.stopped:
            return

        try:
            for i in range(self._repeat):
                if self._state.stopped:
                    break
                logger.info("===== 第 %d/%d 轮 =====", i + 1, self._repeat)
                target()
                if i < self._repeat - 1 and not self._state.stopped and self._switch:
                    logger.info("切换账户...")
                    self._switch()
        except StopFlow:
            logger.info("流程已停止")
        except Exception:
            logger.exception("流程执行异常")

        if self._listener and self._listener.is_alive():
            self._listener.stop()


def _key_name(key) -> str:
    """pynput key → 小写字符串。"""
    if key is None:
        return ""
    if hasattr(key, "char") and key.char:
        return key.char.lower()
    return str(key).replace("Key.", "").lower()
