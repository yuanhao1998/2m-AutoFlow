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


def test_manual_mode_skips_calibration():
    """手动模式下 is_valid() 始终为 True，calibrate() 直接返回 True。"""
    c = Calibrator(_dummy_anchor(), (0, 0),
                   manual_scale=1.0, manual_origin=(0, 0))
    assert c.is_valid()
    assert c.scale == 1.0
    assert c.origin == (0, 0)
    # calibrate() 不应尝试匹配
    assert c.calibrate() is True


def test_manual_mode_to_screen():
    """手动模式下的坐标换算。"""
    c = Calibrator(_dummy_anchor(), (0, 0),
                   manual_scale=2.0, manual_origin=(100, 200))
    assert c.to_screen(10, 20) == (120, 240)   # 100+10*2, 200+20*2
    assert c.to_screen_region((0, 0, 50, 60)) == (100, 200, 200, 320)


def test_manual_mode_partial_is_auto():
    """只设 manual_scale 不设 manual_origin 时仍走自动标定。"""
    c = Calibrator(_dummy_anchor(), (0, 0),
                   manual_scale=1.0, manual_origin=None)
    assert not c.is_valid()  # 未标定
