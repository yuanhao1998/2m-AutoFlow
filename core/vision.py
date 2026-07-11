"""多尺度模板匹配。vision 层只认屏幕像素坐标。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


@dataclass
class Match:
    """模板匹配结果。box 为屏幕像素 (left, top, right, bottom)。"""

    matched: bool
    confidence: float
    box: tuple[int, int, int, int]
    scale: float

    @property
    def center(self) -> tuple[int, int]:
        left, top, right, bottom = self.box
        return ((left + right) // 2, (top + bottom) // 2)


def to_bgr(image: Image.Image) -> np.ndarray:
    """PIL Image → OpenCV BGR numpy 数组。"""
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def load_bgr(path) -> np.ndarray:
    """从文件加载为 BGR numpy 数组。"""
    return to_bgr(Image.open(Path(path)))


def match_template(screen_bgr: np.ndarray, template_bgr: np.ndarray, *,
                   region: tuple[int, int, int, int] | None = None,
                   threshold: float = 0.85,
                   scales: list[float] | None = None) -> Match:
    """在 screen 内按一组 scales 缩放 template 匹配，取最高分。

    Args:
        screen_bgr: 屏幕截图（BGR）。
        template_bgr: 模板图（BGR，作图分辨率原尺寸）。
        region: 屏幕像素搜索区域 (l,t,r,b)，None=全图。
        threshold: 命中阈值。
        scales: 模板缩放比列表，None 默认 [1.0]。

    Returns:
        Match，box 已换算回屏幕像素。
    """
    scales = scales or [1.0]

    if region is not None:
        left = max(0, region[0])
        top = max(0, region[1])
        right = min(screen_bgr.shape[1], region[2])
        bottom = min(screen_bgr.shape[0], region[3])
        sub = screen_bgr[top:bottom, left:right]
        off_x, off_y = left, top
    else:
        sub = screen_bgr
        off_x, off_y = 0, 0

    best = Match(matched=False, confidence=-1.0, box=(0, 0, 0, 0), scale=1.0)
    for s in scales:
        tw = max(1, int(round(template_bgr.shape[1] * s)))
        th = max(1, int(round(template_bgr.shape[0] * s)))
        if th > sub.shape[0] or tw > sub.shape[1]:
            continue
        tmpl = template_bgr if s == 1.0 else cv2.resize(template_bgr, (tw, th))
        result = cv2.matchTemplate(sub, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > best.confidence:
            x, y = max_loc
            box = (x + off_x, y + off_y, x + off_x + tw, y + off_y + th)
            best = Match(matched=max_val >= threshold,
                         confidence=float(max_val), box=box, scale=float(s))
    return best
