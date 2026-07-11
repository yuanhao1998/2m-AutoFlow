from anchors.anchors import Anchor, ImageRef
from core.vision import Match
from target.target import Target


class FakeCal:
    def to_screen(self, x, y):
        return (x + 100, y + 200)


class FakeCtx:
    def __init__(self, match=None):
        self._match = match
        self.calibrator = FakeCal()

    def find_anchor(self, anchor):
        return self._match


A = Anchor(ref=ImageRef("images/x.png"))
HIT = Match(matched=True, confidence=0.9, box=(10, 20, 30, 40), scale=2.0)  # center (20,30)
MISS = Match(matched=False, confidence=0.1, box=(0, 0, 0, 0), scale=1.0)


def test_image_clicks_center_plus_scaled_offset():
    t = Target.image(A, offset=(5, -5))
    assert t.resolve(FakeCtx(match=HIT)) == (20 + 10, 30 - 10)  # offset×scale=±10


def test_image_returns_none_when_not_matched():
    assert Target.image(A).resolve(FakeCtx(match=MISS)) is None


def test_rel_offset_scaled():
    t = Target.rel(A, 10, 0)
    assert t.resolve(FakeCtx(match=HIT)) == (20 + 20, 30)  # 10×2.0


def test_at_uses_calibrator():
    t = Target.at(3, 4)
    assert t.resolve(FakeCtx()) == (103, 204)
