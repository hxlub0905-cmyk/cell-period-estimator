# Cell Period Estimator

A PySide6 desktop tool that estimates the repeating **cell period** — the
"Golden Cell" pitch — of semiconductor **EBeam scan** images, and supports
**cell-to-cell** defect-detection workflows.

Given a scan of a regular array (memory cells, standard-cell rows, line/space
gratings, …) it finds the horizontal/vertical repeat `(px, py)`, builds a
stacked Golden Cell from every full cell in the field, and quantifies how well
the period aligns so you can trust it before running cell-to-cell comparisons.

> **The core idea:** if the period is right, every cell lines up and the stack
> is **sharp**; if it's wrong, the cells drift and the stack **ghosts (blurs)**.
> Sharpness is therefore used both to *verify* and to *refine* the period.

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
- **GLAS** soft warm-light UI theme (see [`docs`](#ui-theme)).

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

## Controls reference

### Toolbar

| Button | What it does |
|---|---|
| **Load Image** | Open a PNG/TIFF/JPG/BMP; read as greyscale. |
| **Estimate Period** *(primary, orange)* | Estimate the period of the full image (or ROI) on a background thread. |
| **Crop ROI** *(toggle)* | Drag a rubber-band rectangle to restrict analysis; emits image-space `(x, y, w, h)`. |
| **Clear ROI** | Drop the ROI and analyse the whole image again. |
| **Export GC** | Save the current Golden Cell stack as PNG. |
| **Export JSON** | Save metadata: `px/py, roi, axis_mode, confidence, score`. |

### Period panel

- **Axis mode badge** — detected periodic direction (see below).
- **X period / Y period** — measured `px / py`; editable spinboxes.
- **Confidence** — per-axis 0–100, derived from autocorrelation strength.
- **Min period** — lower bound on the search (`auto` ⇒ adaptive, floor 4 px);
  raises the floor to avoid locking onto tiny noise periods.
- **Optimize range (±N) + Auto-optimize ±** — scan a ±N neighbourhood around
  the current `px/py` and keep the sharpest stack (ranked by **raw** Laplacian
  variance, not the saturating 0–100 score).

### Golden Cell panel

- **method** — `mean` (default; sensitive to phase error, *deliberately*
  exposes ghosting) or `median` (robust to sparse defects).
- **samples** — stack all cells, or a random subset (16/32/64/128) for speed.
- **preview + sharpness** — the stacked cell plus a score and verdict
  (`aligned` / `marginal` / `ghosting`).

## Reading the views

> There is **no brightness histogram** in this tool. The chart that looks like
> one is the **FFT spectrum**.

### FFT spectrum

- **X axis = period (px)**, **Y axis = normalized magnitude (0–1)**.
- **Orange line = X axis** spectrum, **blue line = Y axis** spectrum (blue is a
  cool semantic marker, deliberately not a second accent hue).
- **White dashed line = detected peak period** (`p=…`).
- A sharp, prominent peak near your expected cell size ⇒ a clean period; a flat
  trace ⇒ that axis has no period.

### Golden Cell preview

- The mean/median of **every complete cell** stacked together.
- **Sharp & clear ⇒ period correct** (cells aligned; noise averaged out,
  features reinforced).
- **Blurred / doubled ⇒ period wrong** (cells misaligned ⇒ ghosting).
- The **sharpness score** quantifies this via Laplacian variance.

### Candidate grid

- Harmonic neighbours of the primary: `px/2, 2px, py/2, 2py, half, double`.
- Each is stacked and labelled with **relative sharpness %**; the sharpest is
  **highlighted with the accent border**. Click a candidate to adopt it — handy
  when the estimator locks onto a half/double harmonic.

### Axis-mode badge

| Badge | Colour | Meaning |
|---|---|---|
| **XY** | green | both axes periodic (typical 2-D cell array) |
| **X** / **Y** | warm orange | only one axis periodic (e.g. vertical line/space ⇒ X only) |
| **NONE** | red | no period detected |

## How it works

`estimate_period` processes the X and Y axes independently:

1. **Projection** — average brightness along the orthogonal axis → a 1-D
   signal (intensity projection).
2. **High-pass detrend** — subtract an edge-padded moving average (window ≈ ¼
   of the length) to remove illumination gradients / boundary artefacts.
3. **Modulation gate** — if the projection is nearly flat (std < 0.5) the axis
   is declared non-periodic. This is why the Y axis of a vertical line/space
   pattern returns `None`: every row is identical, so Y carries no variation,
   and noise can't be normalized into a fake period.
4. **FFT coarse estimate + autocorrelation refinement** — the rFFT peak in the
   `[lo, hi]` band is a coarse candidate, but for rich cell content the FFT
   peak often lands on a **harmonic** (e.g. true period 40 shows a strong peak
   at 20). The **fundamental is decided by autocorrelation**: pick the
   strongest *local maximum* in the lag band (which skips both the high-
   correlation region near lag 0 and the harmonic dips), then refine to
   sub-pixel with a parabolic fit.
5. **Harmonic correction** — if `ac(2p) > 1.15·ac(p)` take `2p` (we found a
   half); if `p` is even and `ac(p/2) ≥ 0.9·ac(p)` take `p/2` (we found a
   double).
6. **Confidence** = autocorrelation strength × 100.

Verification & refinement (`core/stacking.py`):

- `tile_coords` — top-left of every **complete** cell (the single source of
  truth for cell placement).
- `stack_cells` — average/median those cells into one Golden Cell.
- `ghosting_score` — Laplacian variance ⇒ high when aligned, low when ghosted.
- `refine_period` — neighbourhood scan keeping the highest **raw** Laplacian
  variance (this powers Auto-optimize).

In one line:

> **project → detrend → FFT coarse + autocorrelation fundamental → stack into a
> Golden Cell → use sharpness to verify / refine the period.**

## Project layout

```
cell_period_estimator/
  __init__.py        # __version__
  __main__.py        # entry point: apply theme, QApplication + MainWindow; main()
  core/              # Qt-free algorithms
    period_core.py   # estimate_period, PeriodResult, AxisSpectrum, choose_origin
    stacking.py      # tile_coords, stack_cells, ghosting_score, refine_period,
                     # candidate_periods
  ui/
    theme.py         # GLAS design tokens + QSS (apply_theme)
    widgets.py       # ImageView, AxisBadge, SpectrumPlot, CandidateGrid, ...
    main_window.py   # MainWindow
tests/
  test_synthetic.py  # synthetic-image validation
```

For a deeper architecture / algorithm reference (and contributor notes), see
[`CLAUDE.md`](CLAUDE.md).

## UI theme

The UI uses the **GLAS** soft warm-light theme. All design tokens live in
`cell_period_estimator/ui/theme.py` (`TOKENS`) and feed both the QSS
stylesheet and the custom-painted widgets, so colours never drift. Highlights:
cream elevation backgrounds (no pure white page, no pure black text), a single
caramel-orange accent (`#f29f4b`) used only for the primary action, focus rings
and selection, soft semantic chips, and an 11px rounded scrollbar.

## Tests

The core is validated on synthetic images (no display required):

```bash
python tests/test_synthetic.py
```

It checks that an XY pattern is detected as `XY` with the correct `px/py`, that
the correct period stacks sharper (higher Laplacian variance) than a wrong one,
that refinement converges from a slightly-off seed, and that a 50%-duty
vertical line/space pattern is detected as `X` only (`py = None`, `px ≈` pitch).
The run prints `ALL CHECKS PASSED` on success. CI runs this on Python
3.9 / 3.11 / 3.12.
