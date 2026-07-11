import numpy as np

from anchors.anchors import Anchor, ImageRef
from core.vision import Match
from calib.calibrator import Calibrator


def _dummy_anchor():
    return Anchor(ref=ImageRef("images/calib/anchor.png"), threshold=0.8)


def test_calibrate_computes_scale_and_origin():
    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        return Match(matched=True, confidence=0.99, box=(100, 140, 150, 170), scale=0.5)

    c = Calibrator(
        anchor=_dummy_anchor(),
        authoring_topleft=(50, 60),
        coarse_scales=[0.5],
        matcher=fake_matcher,
        loader=lambda p: np.zeros((10, 10, 3), dtype=np.uint8),
        capture=lambda: np.zeros((300, 300, 3), dtype=np.uint8),
    )
    assert c.calibrate() is True
    assert c.scale == 0.5
    # origin = 命中左上角 - 作图左上角 × scale = (100-25, 140-30)
    assert c.origin == (75, 110)
    assert c.is_valid()


def test_to_screen_transform():
    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        return Match(matched=True, confidence=0.99, box=(100, 140, 150, 170), scale=0.5)

    c = Calibrator(_dummy_anchor(), (50, 60), coarse_scales=[0.5],
                   matcher=fake_matcher,
                   loader=lambda p: np.zeros((10, 10, 3), dtype=np.uint8),
                   capture=lambda: np.zeros((300, 300, 3), dtype=np.uint8))
    c.calibrate()
    assert c.to_screen(0, 0) == (75, 110)
    assert c.to_screen(50, 60) == (100, 140)      # 应回到命中左上角
    assert c.to_screen_region((0, 0, 50, 60)) == (75, 110, 100, 140)


def test_calibrate_fail_returns_false():
    def fail_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        return Match(matched=False, confidence=0.1, box=(0, 0, 0, 0), scale=1.0)

    c = Calibrator(_dummy_anchor(), (0, 0), coarse_scales=[1.0],
                   matcher=fail_matcher,
                   loader=lambda p: np.zeros((10, 10, 3), dtype=np.uint8),
                   capture=lambda: np.zeros((50, 50, 3), dtype=np.uint8))
    assert c.calibrate() is False
    assert not c.is_valid()


def test_invalidate():
    def fake_matcher(screen, template, *, region=None, threshold=0.85, scales=None):
        return Match(matched=True, confidence=0.99, box=(0, 0, 10, 10), scale=1.0)

    c = Calibrator(_dummy_anchor(), (0, 0), coarse_scales=[1.0],
                   matcher=fake_matcher,
                   loader=lambda p: np.zeros((5, 5, 3), dtype=np.uint8),
                   capture=lambda: np.zeros((50, 50, 3), dtype=np.uint8))
    c.calibrate()
    assert c.is_valid()
    c.invalidate()
    assert not c.is_valid()
