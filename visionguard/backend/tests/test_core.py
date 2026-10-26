import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import KINDS, compare, corrupt, iou

D = lambda l, c, b: {"label": l, "conf": c, "box": b}


def test_corruptions_repeatable_and_shaped():
    img = np.random.default_rng(0).integers(0, 255, (96, 128, 3), dtype=np.uint8)
    for k in KINDS:
        a, _ = corrupt(img, k, 0.6, seed=1)
        b, _ = corrupt(img, k, 0.6, seed=1)
        assert a.shape == img.shape and np.array_equal(a, b)


def test_iou():
    assert iou([0, 0, 1, 1], [0, 0, 1, 1]) == 1 and iou([0, 0, .4, .4], [.6, .6, 1, 1]) == 0


def test_compare_lost_changed_spurious():
    base = [D("dog", .9, [0, 0, .4, .4]), D("cat", .8, [.5, .5, .9, .9]), D("car", .7, [.1, .6, .3, .9])]
    alt = [D("dog", .6, [0, 0, .4, .4]), D("dog", .5, [.5, .5, .9, .9]), D("bird", .4, [.7, 0, 1, .2])]
    r = compare(base, alt)
    assert abs(r["retention"] - 1 / 3) < 1e-9
    assert (r["lost"], r["class_changes"], r["spurious"]) == (1, 1, 1)
    assert abs(r["conf_change"] + .3) < 1e-9
