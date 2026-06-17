"""Synthetic-image validation for the estimation core.

Run directly::

    python tests/test_synthetic.py

Prints PASS / FAIL per check and exits non-zero on any failure.
"""

from __future__ import annotations

import os
import sys

# Make the project root importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from cell_period_estimator.core import (  # noqa: E402
    estimate_period,
    ghosting_score,
    refine_period,
    stack_cells,
)


# --------------------------------------------------------------------------- #
# synthetic image generators
# --------------------------------------------------------------------------- #
def make_xy_pattern(h=300, w=400, px=40, py=30, seed=0):
    """A 2-D periodic field with a sharp feature in each cell."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w), 40.0)
    # One bright square + one bright bar per cell, off-centre so the cell
    # content is asymmetric (well-defined alignment target).
    cell = np.full((py, px), 40.0)
    cell[5:11, 6:12] = 230.0          # square
    cell[py - 8:py - 4, 4:px - 4] = 180.0  # horizontal bar
    for y in range(0, h - py + 1, py):
        for x in range(0, w - px + 1, px):
            img[y:y + py, x:x + px] = cell
    img += rng.normal(0, 3.0, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def make_line_space(h=240, w=240, pitch=20, seed=0):
    """50% duty vertical line/space pattern (periodic in X only)."""
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w), dtype=np.float64)
    half = pitch // 2
    for x in range(0, w, pitch):
        img[:, x:x + half] = 220.0
    img += rng.normal(0, 2.0, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- #
# test harness
# --------------------------------------------------------------------------- #
class Results:
    def __init__(self):
        self.failures = 0

    def check(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail:
            line += f"  ({detail})"
        print(line)
        if not ok:
            self.failures += 1


def test_xy_detection(r: Results):
    px_true, py_true = 40, 30
    img = make_xy_pattern(px=px_true, py=py_true)
    res = estimate_period(img)
    r.check("xy: axis_mode == XY", res.axis_mode == "XY",
            f"mode={res.axis_mode}")
    r.check("xy: px correct", res.px == px_true, f"px={res.px} want {px_true}")
    r.check("xy: py correct", res.py == py_true, f"py={res.py} want {py_true}")


def test_stacking_sharpness(r: Results):
    px_true, py_true = 40, 30
    img = make_xy_pattern(px=px_true, py=py_true)
    good = stack_cells(img, px_true, py_true, method="mean")
    bad = stack_cells(img, px_true + 5, py_true + 4, method="mean")
    _, lv_good, _ = ghosting_score(good)
    _, lv_bad, _ = ghosting_score(bad)
    r.check("stack: correct period sharper than wrong",
            lv_good > lv_bad, f"lap_var good={lv_good:.1f} bad={lv_bad:.1f}")


def test_refine_converges(r: Results):
    px_true, py_true = 40, 30
    img = make_xy_pattern(px=px_true, py=py_true)
    seed_px, seed_py = px_true + 2, py_true - 1
    bpx, bpy, score = refine_period(img, seed_px, seed_py, search=6)
    r.check("refine: recovers true px", bpx == px_true,
            f"px={bpx} want {px_true}")
    r.check("refine: recovers true py", bpy == py_true,
            f"py={bpy} want {py_true}")


def test_line_space(r: Results):
    pitch = 20
    img = make_line_space(pitch=pitch)
    res = estimate_period(img)
    r.check("line/space: axis_mode == X", res.axis_mode == "X",
            f"mode={res.axis_mode}")
    r.check("line/space: py is None", res.py is None, f"py={res.py}")
    r.check("line/space: px ~= pitch",
            res.px is not None and abs(res.px - pitch) <= 1,
            f"px={res.px} want ~{pitch}")


def main():
    r = Results()
    test_xy_detection(r)
    test_stacking_sharpness(r)
    test_refine_converges(r)
    test_line_space(r)
    print("-" * 48)
    if r.failures:
        print(f"{r.failures} check(s) FAILED")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
