import numpy as np
import pytest

from anchors.anchors import Anchor, ImageRef
from core.vision import Match
from target.target import Target
from fsm.context import Ctx, RunState, StopFlow


class FakeCal:
    scale = 0.5

    def to_screen(self, x, y):
        return (x + 10, y + 20)

    def to_screen_region(self, region):
        return (region[0] + 10, region[1] + 20, region[2] + 10, region[3] + 20)


def test_find_anchor_scales_region_and_uses_calibrated_scale():
    seen = {}

    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        seen["region"] = region
        seen["scales"] = scales
        seen["threshold"] = threshold
        return Match(True, 0.9, (0, 0, 2, 2), 0.5)

    ctx = Ctx(FakeCal(), RunState(),
              capture=lambda: np.zeros((100, 100, 3), dtype=np.uint8))
    ctx.screen_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    ctx._matcher = fake_matcher
    ctx._loader = lambda p: np.zeros((4, 4, 3), dtype=np.uint8)

    a = Anchor(ref=ImageRef("x.png"), region=(0, 0, 30, 40), threshold=0.7)
    m = ctx.find_anchor(a)
    assert m.matched
    assert seen["region"] == (10, 20, 40, 60)   # 经 to_screen_region 换算
    assert seen["scales"] == [0.5]
    assert seen["threshold"] == 0.7


def test_find_anchor_dispatches_to_text_match():
    """当 anchor.text 非空时走 OCR 路径而非模板匹配。"""
    called = {}

    def fake_match_text(anchor):
        called["text"] = anchor.text
        called["region"] = anchor.region
        return Match(True, 0.99, (100, 200, 130, 220), 1.0)

    ctx = Ctx(FakeCal(), RunState(),
              capture=lambda: np.zeros((100, 100, 3), dtype=np.uint8))
    ctx.screen_bgr = np.zeros((200, 200, 3), dtype=np.uint8)
    ctx._match_text = fake_match_text

    a = Anchor(text="확인", region=(10, 20, 50, 60))
    m = ctx.find_anchor(a)
    assert m.matched is True
    assert m.confidence == 0.99
    assert called["text"] == "확인"
    assert called["region"] == (10, 20, 50, 60)


def test_find_anchor_still_uses_image_when_text_is_none():
    """text 为 None 时仍走图像模板匹配路径。"""
    seen = {}

    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        seen["path"] = "image"
        return Match(True, 0.88, (0, 0, 2, 2), 0.5)

    ctx = Ctx(FakeCal(), RunState(),
              capture=lambda: np.zeros((50, 50, 3), dtype=np.uint8))
    ctx.screen_bgr = np.zeros((50, 50, 3), dtype=np.uint8)
    ctx._matcher = fake_matcher
    ctx._loader = lambda p: np.zeros((4, 4, 3), dtype=np.uint8)

    m = ctx.find_anchor(Anchor(ref=ImageRef("x.png")))
    assert m.matched is True
    assert seen["path"] == "image"


def test_click_returns_false_when_unresolved():
    clicked = []
    ctx = Ctx(FakeCal(), RunState(), clicker=lambda x, y: clicked.append((x, y)))
    ctx.screen_bgr = np.zeros((10, 10, 3), dtype=np.uint8)
    ctx._matcher = lambda *a, **k: Match(False, 0.0, (0, 0, 0, 0), 1.0)
    ctx._loader = lambda p: np.zeros((2, 2, 3), dtype=np.uint8)
    ok = ctx.click(Target.image(Anchor(ref=ImageRef("x.png"))))
    assert ok is False
    assert clicked == []


def test_click_uses_calibrator_for_at_target():
    clicked = []
    ctx = Ctx(FakeCal(), RunState(), clicker=lambda x, y: clicked.append((x, y)))
    assert ctx.click(Target.at(1, 2)) is True
    assert clicked == [(11, 22)]


def test_check_state_stop_raises():
    rs = RunState()
    rs.stopped = True
    ctx = Ctx(FakeCal(), rs)
    with pytest.raises(StopFlow):
        ctx.check_state()
