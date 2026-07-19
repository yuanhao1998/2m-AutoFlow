"""执行上下文：把标定、匹配、截图、点击、运行状态串起来。"""

from __future__ import annotations

import logging
import time

import cv2
import numpy as np

from anchors.anchors import Anchor
from calib.calibrator import Calibrator
from core.vision import Match, match_template, load_bgr, to_bgr
from target.target import Target

logger = logging.getLogger(__name__)


class StopFlow(Exception):
    """请求立即终止流程。"""


class RunState:
    """运行状态标志，由热键线程写、执行线程读。"""

    def __init__(self) -> None:
        self.running = False
        self.paused = False
        self.stopped = False


class Ctx:
    """贯穿引擎的执行上下文。"""

    def __init__(self, calibrator, run_state: RunState, *,
                 capture=None, clicker=None, cache_templates: bool = True) -> None:
        self.calibrator: Calibrator = calibrator
        self.run_state = run_state
        self.screen_bgr: np.ndarray | None = None
        self.device_name = ""
        self.account = 0
        self._capture = capture
        self._clicker = clicker
        self._matcher = match_template
        self._loader = load_bgr
        self._cache: dict[str, np.ndarray] = {} if cache_templates else None

    # -- 截图 --
    def refresh_screenshot(self) -> None:
        if self._capture is not None:
            self.screen_bgr = self._capture()
        else:
            from core.capture import fullscreen_screenshot
            self.screen_bgr = to_bgr(fullscreen_screenshot())

    # -- 匹配 --
    def _template(self, anchor: Anchor) -> np.ndarray:
        key = str(anchor.ref.path)
        if self._cache is None:
            return self._loader(anchor.ref.path)
        if key not in self._cache:
            self._cache[key] = self._loader(anchor.ref.path)
        return self._cache[key]

    def find_anchor(self, anchor: Anchor) -> Match:
        """在当前截图中匹配锚点（图像模板匹配或 OCR 文字定位）。"""
        if anchor.text is not None:
            return self._match_text(anchor)
        return self._match_image(anchor)

    def _match_image(self, anchor: Anchor) -> Match:
        """cv2.matchTemplate 模板匹配。"""
        region = None
        if anchor.region is not None:
            region = self.calibrator.to_screen_region(anchor.region)
        return self._matcher(self.screen_bgr, self._template(anchor),
                             region=region, threshold=anchor.threshold,
                             scales=[self.calibrator.scale])

    def _match_text(self, anchor: Anchor) -> Match:
        """EasyOCR 文字定位：在 region 内搜索 anchor.text。"""
        from core.ocr import _get_reader
        region = None
        off_x, off_y = 0, 0
        if anchor.region is not None:
            r = self.calibrator.to_screen_region(anchor.region)
            left, top, right, bottom = r
            left, top = max(0, left), max(0, top)
            right = min(self.screen_bgr.shape[1], right)
            bottom = min(self.screen_bgr.shape[0], bottom)
            if right <= left or bottom <= top:
                return Match(False, 0.0, (0, 0, 0, 0), 1.0)
            sub = self.screen_bgr[top:bottom, left:right]
            off_x, off_y = left, top
        else:
            sub = self.screen_bgr

        reader = _get_reader()
        results = reader.readtext(sub, detail=1)
        query = anchor.text.replace(" ", "").lower()
        for bbox, detected, conf in results:
            if query in detected.replace(" ", "").lower():
                cx = int((bbox[0][0] + bbox[2][0]) / 2) + off_x
                cy = int((bbox[0][1] + bbox[2][1]) / 2) + off_y
                l = int(bbox[0][0]) + off_x
                t = int(bbox[0][1]) + off_y
                r = int(bbox[2][0]) + off_x
                b = int(bbox[2][1]) + off_y
                return Match(True, float(conf), (l, t, r, b), 1.0)
        return Match(False, 0.0, (0, 0, 0, 0), 1.0)

    # -- 亮度采样 --
    def brightness(self, region: tuple[int, int, int, int]) -> float:
        """采样指定区域的平均亮度（0=黑, 255=白），用于区分图标深浅态。

        Args:
            region: 屏幕像素区域 (left, top, right, bottom)。

        Returns:
            平均灰度值，暗→0，亮→255。
        """
        left, top, right, bottom = region
        h, w = self.screen_bgr.shape[:2]
        left = max(0, left)
        top = max(0, top)
        right = min(w, right)
        bottom = min(h, bottom)
        if right <= left or bottom <= top:
            return 0.0
        roi = self.screen_bgr[top:bottom, left:right]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        return float(gray.mean())

    # -- 文字提取 --
    def read_text(self, region: tuple[int, int, int, int]) -> str:
        """提取区域内所有文字（EasyOCR），返回空格分隔的字符串。

        Args:
            region: 屏幕像素区域 (left, top, right, bottom)。

        Returns:
            识别到的文字，空格分隔；无文字返回空字符串。
        """
        from core.ocr import _get_reader
        left, top, right, bottom = region
        h, w = self.screen_bgr.shape[:2]
        left, top = max(0, left), max(0, top)
        right, bottom = min(w, right), min(h, bottom)
        if right <= left or bottom <= top:
            return ""
        sub = self.screen_bgr[top:bottom, left:right]
        results = _get_reader().readtext(sub, detail=0)
        return " ".join(results)

    # -- 点击 --
    def click(self, target: Target) -> bool:
        pt = target.resolve(self)
        if pt is None:
            return False
        if self._clicker is not None:
            self._clicker(*pt)
        else:
            from core.input import click as real_click
            real_click(*pt)
        return True

    # -- 运行控制 --
    def check_state(self) -> None:
        while self.run_state.paused and not self.run_state.stopped:
            time.sleep(0.1)
        if self.run_state.stopped:
            raise StopFlow

    def wait(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check_state()
            time.sleep(min(0.1, max(0.01, end - time.monotonic())))
