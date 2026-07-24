"""全局仿射标定：一次匹配标定锚点，建立作图坐标↔屏幕坐标映射。

关系: 屏幕px = origin + 作图px × scale （同布局仅等比缩放场景）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np

from anchors.anchors import Anchor
from core.vision import Match, match_template, load_bgr

logger = logging.getLogger(__name__)


class Calibrator:
    """标定器：求 scale 与 origin，并做坐标换算。

    支持手动模式：传入 manual_scale 和 manual_origin（均非 None）时
    跳过自动标定，直接使用手动值，is_valid() 始终返回 True。
    """

    def __init__(self, anchor: Anchor, authoring_topleft: tuple[int, int], *,
                 coarse_scales: list[float] | None = None,
                 threshold: float = 0.80,
                 matcher: Callable = match_template,
                 loader: Callable = load_bgr,
                 capture: Callable | None = None,
                 manual_scale: float | None = None,
                 manual_origin: tuple[int, int] | None = None) -> None:
        self._anchor = anchor
        self._authoring_topleft = authoring_topleft
        self._coarse_scales = coarse_scales or _default_scales()
        self._threshold = threshold
        self._matcher = matcher
        self._loader = loader
        self._capture = capture
        self._manual = (manual_scale is not None and manual_origin is not None)
        if self._manual:
            self.scale = manual_scale
            self.origin = manual_origin
            self._valid = True
            logger.info("手动标定：scale=%.4f origin=%s", self.scale, self.origin)
        else:
            self.scale: float = 1.0
            self.origin: tuple[int, int] = (0, 0)
            self._valid = False

    def calibrate(self, screen_bgr: np.ndarray | None = None) -> bool:
        """匹配标定锚点，计算 scale/origin。成功返回 True。

        手动模式下直接返回 True，不执行匹配。
        """
        if self._manual:
            return True
        if screen_bgr is None:
            screen_bgr = self._grab()
        template = self._loader(self._anchor.ref.path)
        m: Match = self._matcher(screen_bgr, template,
                                 threshold=self._threshold,
                                 scales=self._coarse_scales)
        if not m.matched:
            logger.error("标定失败：未匹配到标定锚点（置信度 %.3f）", m.confidence)
            self._valid = False
            return False
        self.scale = m.scale
        ax, ay = self._authoring_topleft
        self.origin = (round(m.box[0] - ax * m.scale),
                       round(m.box[1] - ay * m.scale))
        self._valid = True
        logger.info("标定成功：scale=%.4f origin=%s (置信度 %.3f)",
                    self.scale, self.origin, m.confidence)
        return True

    def to_screen(self, x: int, y: int) -> tuple[int, int]:
        """作图坐标 → 屏幕像素。"""
        ox, oy = self.origin
        return round(ox + x * self.scale), round(oy + y * self.scale)

    def to_screen_region(self, region: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """作图区域 → 屏幕像素区域。"""
        left, top = self.to_screen(region[0], region[1])
        right, bottom = self.to_screen(region[2], region[3])
        return left, top, right, bottom

    def is_valid(self) -> bool:
        return self._valid

    def invalidate(self) -> None:
        self._valid = False

    def _grab(self) -> np.ndarray:
        if self._capture is not None:
            return self._capture()
        from core.capture import fullscreen_screenshot
        from core.vision import to_bgr
        return to_bgr(fullscreen_screenshot())


def _default_scales() -> list[float]:
    """从 config.yaml 读取粗扫尺度范围，失败则用内置默认。"""
    lo, hi, step = 0.40, 1.20, 0.02
    try:
        from pathlib import Path
        from ruamel.yaml import YAML
        cfg_path = Path("conf/config.yaml")
        if cfg_path.exists():
            yaml = YAML(typ="safe")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = (yaml.load(f) or {}).get("calib", {})
            lo = float(cfg.get("coarse_scales_min", lo))
            hi = float(cfg.get("coarse_scales_max", hi))
            step = float(cfg.get("coarse_scales_step", step))
    except Exception:
        pass
    n = int(round((hi - lo) / step)) + 1
    return [round(lo + i * step, 4) for i in range(max(1, n))]
