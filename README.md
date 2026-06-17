# Cell Period Estimator

A PySide6 desktop tool that estimates the repeating **cell period** — the
"Golden Cell" pitch — of semiconductor **EBeam scan** images, and supports
**cell-to-cell** defect-detection workflows.

Given a scan of a regular array (memory cells, standard-cell rows, line/space
gratings, …) it finds the horizontal/vertical repeat `(px, py)`, builds a
stacked Golden Cell from every full cell in the field, and quantifies how well
the period aligns so you can trust it before running cell-to-cell comparisons.

## Features

- **Robust period estimation** (pure NumPy/OpenCV core, no Qt dependency):
  intensity-projection FFT for a coarse period, cross-checked and refined by
  normalized autocorrelation with parabolic sub-pixel interpolation and
  harmonic correction. A modulation gate suppresses false periods on flat
  axes (e.g. the orthogonal axis of a line/space pattern).
- **Axis-mode detection**: `X`, `Y`, `XY`, or `NONE`, shown as a colour badge.
- **Golden Cell stacking**: `mean` (sensitive to phase error, exposes
  ghosting) or `median` (robust to defects), with optional random sampling.
- **Sharpness / ghosting score** to verify alignment (sharp stack → aligned,
  blurred stack → wrong period).
- **Auto-optimize** the period by scanning a neighbourhood for the sharpest
  stack.
- **FFT spectrum plot** and a **candidate comparison grid** (half/double
  harmonics) so you can pick the right fundamental at a glance.
- **Export** the Golden Cell as PNG and the metadata
  (`period / roi / axis_mode / confidence / score`) as JSON.

## Installation

```bash
pip install -r requirements.txt
# or, to install as a package (provides the console entry point):
pip install .
```

Requirements: `PySide6`, `opencv-python`, `numpy` (Python ≥ 3.9).

## Launching

```bash
python -m cell_period_estimator
```

If installed as a package, the console entry point is also available:

```bash
cell-period-estimator
```

## Workflow

1. **Load Image** — open an EBeam scan (PNG/TIFF/JPG/BMP, read as greyscale).
2. **Crop ROI** *(optional)* — toggle Crop ROI and drag a rectangle to limit
   analysis to a clean periodic region; **Clear ROI** to reset.
3. **Estimate Period** — runs in a background thread; the result fills the
   X/Y period spinboxes and confidence.
4. **Read the axis badge / FFT spectrum** — confirm the detected axis mode and
   that the spectrum peak sits on the expected period.
5. **Verify with the Golden Cell** — inspect the stacked cell and its
   sharpness/ghosting verdict; switch `mean`/`median` and sample count as
   needed. Use **Auto-optimize ±** to snap to the sharpest period.
6. **Compare candidates** — the candidate grid stacks half/double harmonics;
   the sharpest is highlighted. Click any candidate to adopt it.
7. **Export** — **Export GC** saves the Golden Cell PNG; **Export JSON** saves
   `period / roi / axis_mode / confidence / score`.

## Project layout

```
cell_period_estimator/
  __init__.py        # __version__
  __main__.py        # entry point: QApplication + MainWindow; main()
  core/              # Qt-free algorithms
    period_core.py   # estimate_period, PeriodResult, AxisSpectrum, choose_origin
    stacking.py      # tile_coords, stack_cells, ghosting_score, refine_period,
                     # candidate_periods
  ui/
    widgets.py       # ImageView, AxisBadge, SpectrumPlot, CandidateGrid, ...
    main_window.py   # MainWindow
tests/
  test_synthetic.py  # synthetic-image validation
```

## Tests

The core is validated on synthetic images (no display required):

```bash
python tests/test_synthetic.py
```

It checks that an XY pattern is detected as `XY` with the correct `px/py`, that
the correct period stacks sharper (higher Laplacian variance) than a wrong one,
that refinement converges from a slightly-off seed, and that a 50%-duty
vertical line/space pattern is detected as `X` only (`py = None`, `px ≈` pitch).
The run prints `ALL CHECKS PASSED` on success.
