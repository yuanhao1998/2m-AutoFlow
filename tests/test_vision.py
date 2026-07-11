import numpy as np
import cv2

from core.vision import Match, match_template


def _patch(size):
    """构造有方差的图案块（左白右黑），避免 TM_CCOEFF_NORMED 除零。"""
    p = np.zeros((size, size, 3), dtype=np.uint8)
    p[:, : size // 2] = 255
    return p


def test_match_center_property():
    m = Match(matched=True, confidence=0.9, box=(10, 20, 30, 40), scale=1.0)
    assert m.center == (20, 30)


def test_match_same_scale():
    screen = np.zeros((100, 120, 3), dtype=np.uint8)
    patch = _patch(20)
    screen[40:60, 30:50] = patch
    m = match_template(screen, patch, scales=[1.0], threshold=0.9)
    assert m.matched
    assert m.box == (30, 40, 50, 60)
    assert m.center == (40, 50)
    assert m.scale == 1.0


def test_match_multiscale_finds_2x():
    screen = np.zeros((200, 200, 3), dtype=np.uint8)
    patch = _patch(20)
    big = cv2.resize(patch, (40, 40))
    screen[60:100, 80:120] = big
    m = match_template(screen, patch, scales=[0.5, 1.0, 2.0], threshold=0.9)
    assert m.matched
    assert m.scale == 2.0
    assert m.center == (100, 80)


def test_region_offsets_back_to_screen_coords():
    screen = np.zeros((100, 100, 3), dtype=np.uint8)
    patch = _patch(10)
    screen[70:80, 60:70] = patch
    m = match_template(screen, patch, region=(50, 50, 100, 100),
                       scales=[1.0], threshold=0.9)
    assert m.matched
    assert m.box == (60, 70, 70, 80)


def test_no_match_below_threshold():
    screen = np.zeros((50, 50, 3), dtype=np.uint8)
    patch = _patch(10)  # screen 全黑，patch 半白 → 低相关
    m = match_template(screen, patch, scales=[1.0], threshold=0.9)
    assert not m.matched
