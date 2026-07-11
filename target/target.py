"""点击目标抽象：锚点相对定位为主，作图坐标兜底。"""

from __future__ import annotations

from anchors.anchors import Anchor


class Target:
    """一个待点击目标，resolve(ctx) 得到屏幕像素点。"""

    _IMAGE = "image"
    _REL = "rel"
    _AT = "at"

    def __init__(self, kind: str, *, anchor: Anchor | None = None,
                 offset: tuple[int, int] = (0, 0),
                 point: tuple[int, int] | None = None) -> None:
        self._kind = kind
        self._anchor = anchor
        self._offset = offset
        self._point = point

    @staticmethod
    def image(anchor: Anchor, *, offset: tuple[int, int] = (0, 0)) -> "Target":
        """匹配 anchor → 点击其中心 + offset×scale。"""
        return Target(Target._IMAGE, anchor=anchor, offset=offset)

    @staticmethod
    def rel(anchor: Anchor, dx: int, dy: int) -> "Target":
        """匹配 anchor → 点击 中心 + (dx,dy)×scale。"""
        return Target(Target._REL, anchor=anchor, offset=(dx, dy))

    @staticmethod
    def at(x: int, y: int) -> "Target":
        """作图坐标 → 经标定变换为屏幕坐标。"""
        return Target(Target._AT, point=(x, y))

    def resolve(self, ctx) -> tuple[int, int] | None:
        """返回屏幕像素点击点；匹配失败返回 None。"""
        if self._kind == Target._AT:
            return ctx.calibrator.to_screen(*self._point)

        m = ctx.find_anchor(self._anchor)
        if not m.matched:
            return None
        cx, cy = m.center
        dx, dy = self._offset
        return (cx + round(dx * m.scale), cy + round(dy * m.scale))
