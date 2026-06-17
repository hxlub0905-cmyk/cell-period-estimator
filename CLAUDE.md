# CLAUDE.md

Guidance for Claude Code (and human contributors) working in this repository.

## What this project is

**Cell Period Estimator** is a PySide6 desktop tool that estimates the
repeating cell period (`px`, `py` — the "Golden Cell" pitch) of semiconductor
EBeam scan images and supports cell-to-cell defect-detection workflows. The
estimation core is pure NumPy/OpenCV; the UI is a thin PySide6 layer on top.

Entry point: `python -m cell_period_estimator` (console script:
`cell-period-estimator`).

## Repository map

```
cell_period_estimator/
  __init__.py        # __version__ = "0.1.0" (keep in sync with pyproject)
  __main__.py        # main(): apply_theme(app) -> MainWindow -> app.exec()
  core/              # ── Qt-FREE. Never import PySide6 here. ──
    __init__.py      # re-exports the public core API
    period_core.py   # estimate_period + PeriodResult/AxisSpectrum + choose_origin
    stacking.py      # tile_coords, stack_cells, ghosting_score, refine_period,
                     #   candidate_periods
  ui/
    theme.py         # GLAS design tokens (TOKENS) + QSS + apply_theme()
    widgets.py       # numpy<->Qt, ImageView, AxisBadge, SpectrumPlot, CandidateGrid
    main_window.py   # MainWindow: toolbar, panels, QThread estimation, exports
tests/
  test_synthetic.py  # synthetic-image validation, run as a plain script
.github/workflows/ci.yml   # runs the synthetic test on 3.9/3.11/3.12
```

## Hard rules / conventions

- **`core/` stays Qt-free.** Tests and batch use import the core without a
  display server. Importing `cell_period_estimator.core` must never pull in
  PySide6. (`__init__.py` is intentionally minimal so `import
  cell_period_estimator.core` doesn't drag in Qt.)
- **Single token source for theming.** All colours live in
  `ui/theme.py::TOKENS`. QSS *and* custom-painted widgets read from it. Do not
  hard-code hex values in widgets — import `TOKENS`.
- **One accent hue (orange `#f29f4b`).** Used only for the primary action,
  focus rings, selection, and section titles. Don't flood the UI with it.
- **Headless OpenCV in CI/tests.** `opencv-python-headless` is enough for the
  core; the full `opencv-python` is only listed in `requirements.txt` for the
  desktop app. Tests must not require PySide6.
- Match the surrounding code style: type hints, dataclasses for results,
  docstrings that explain *why*, 4-space indent.

## Algorithm reference (core/period_core.py)

`estimate_period(image, min_period=None, max_period=None,
strength_threshold=0.18) -> PeriodResult` runs per axis (X and Y
independently). For axis X the "intensity projection" is `gray.mean(axis=0)`
(varies along width); for Y it is `gray.mean(axis=1)`.

Pipeline per axis (`_analyze_axis`):

1. **Modulation gate** — if `projection.std() < 0.5` (`_MODULATION_STD_FLOOR`)
   the axis is flat ⇒ return no period. Prevents normalizing noise into a fake
   period (e.g. the Y axis of a vertical line/space pattern).
2. **High-pass detrend** (`_highpass`) — subtract an **edge-padded** moving
   average, window ≈ length/4 (odd-clamped). Edge padding avoids spurious ramps
   at the boundaries.
3. **rFFT** — strongest peak inside the adaptive band `[lo, hi]` gives a coarse
   candidate. The band: `lo = max(2, min_period or 4)`,
   `hi = min(max_period or length//2, length//2)` (`_search_band`).
4. **Autocorrelation decides the fundamental.** *Important:* the intensity FFT
   peak can land on a **harmonic** when cell content is rich (a feature inside
   every cell repeats at sub-cell frequency). So we pick the strongest **local
   maximum** of the normalized autocorrelation in the lag band — this skips
   both the monotonic high-correlation region near lag 0 and the harmonic dips
   — then refine to sub-pixel with a parabola (`_parabolic`). The FFT result is
   used as a fallback hint and for the displayed spectrum only.
5. **Harmonic correction** — `if ac(2p) > 1.15·ac(p): p = 2p`; `elif p even and
   ac(p/2) >= 0.9·ac(p): p = p/2`.
6. **Accept/reject** — reject if `period < lo` or `strength <
   strength_threshold`. `confidence = strength * 100`.

`axis_mode` ∈ {`X`, `Y`, `XY`, `NONE`} from which axes have a period.

### Data structures

- `AxisSpectrum(periods, magnitude, peak_period)` with
  `normalized_magnitude()` (peak scaled to 1.0) for plotting.
- `PeriodResult(px, py, confidence_x, confidence_y, axis_mode,
  peak_strength_x, peak_strength_y, spectrum_x, spectrum_y, candidates,
  warnings)`. `px/py` are `int` or `None`; strengths are 0–1; confidences
  0–100.
- `choose_origin(shape, px, py)` returns the lattice origin (default `(0, 0)`).

## Stacking reference (core/stacking.py)

- `tile_coords(shape, px, py, origin=(0,0))` — top-left `(x, y)` of every
  **complete** cell (skips partial border cells). Single source of truth for
  cell placement; used by both stacking and refinement.
- `stack_cells(image, px, py, method="mean", origin=(0,0), sample_n=None,
  seed=0) -> uint8 (py, px)`. `mean` (default) is phase-sensitive and exposes
  ghosting; `median` is defect-robust. `sample_n` randomly subsamples cells
  (seeded RNG).
- `ghosting_score(stacked) -> (score_0_100, laplacian_var, edge_contrast)`.
  `score` is a saturating display map; **`laplacian_var` is the raw value to
  rank by.**
- `refine_period(image, px, py, search=6, method="mean") -> (best_px, best_py,
  best_lap_var)`. Neighbourhood scan ranked by **raw** Laplacian variance (not
  the 0–100 score, which clips near the top and loses ordering).
- `candidate_periods(px, py, lo, hi)` — primary + per-axis/combined half/double
  harmonics, filtered to range and de-duplicated.

## UI reference (ui/)

- `apply_theme(app)` (in `theme.py`) sets the Fusion style, a warm `QPalette`,
  and the QSS built from `TOKENS`. Called once in `__main__.main()`.
- `widgets.py`
  - `numpy_to_qimage` / `numpy_to_qpixmap` — grey/RGB/RGBA uint8 conversion.
  - `ImageView(QGraphicsView)` — wheel zoom, rubber-band ROI
    (`cropChanged(x, y, w, h)` in image coords), period grid overlay.
  - `AxisBadge` — soft semantic chip (XY=success, X/Y=min-accent,
    NONE=danger).
  - `SpectrumPlot` — self-drawn X/Y FFT spectra; X=accent, Y=cool marker,
    peak=accent-active.
  - `CandidateGrid` — thumbnail grid, `candidateChosen(px, py)`; best candidate
    gets the accent border.
- `main_window.py::MainWindow`
  - Toolbar actions: Load Image, **Estimate Period** (the single primary
    action — its QToolButton is `objectName="primary"`), Crop ROI (checkable),
    Clear ROI, Export GC, Export JSON.
  - Estimation runs in a `QThread` via `_EstimateWorker` (`finished`/`failed`
    signals) so the UI stays responsive.
  - Crop limits analysis to the ROI (`_refresh_analysis_image`).
  - Export GC → PNG; Export JSON → `{px, py, roi, axis_mode, confidence,
    score}`.

### Qt-QSS limitations to remember

- QSS has no `text-transform` or `letter-spacing`. Section/group titles are
  upper-cased in code (e.g. `QGroupBox("PERIOD")`); the accent colour, 10px
  size and weight 700 come from QSS.
- Button variants use a dynamic property: `setProperty("variant",
  "primary"|"secondary"|"ghost"|"success")` matched by QSS attribute selectors.

## Running & testing

```bash
# install for development (headless OpenCV is fine for the core/tests)
pip install numpy opencv-python-headless        # core + tests
pip install PySide6                               # to run the desktop app

# run the app (needs a display, or QT_QPA_PLATFORM=offscreen for smoke tests)
python -m cell_period_estimator

# run the synthetic test suite (prints ALL CHECKS PASSED on success)
python tests/test_synthetic.py
```

Offscreen smoke test (no display, e.g. CI/containers):

```bash
QT_QPA_PLATFORM=offscreen python -m cell_period_estimator   # constructs + exits if scripted
```

Note: on minimal Linux images the Qt platform plugin needs system libs
(`libegl1`, `libgl1`, `libxkbcommon0`, `libdbus-1-3`). The core and the
synthetic tests need none of these.

## Common change recipes

- **Tune detection sensitivity** → `strength_threshold` (accept/reject) and
  `_MODULATION_STD_FLOOR` (flat-axis gate) in `period_core.py`.
- **Change the harmonic-correction thresholds** → the `1.15` / `0.9` constants
  in `_analyze_axis`.
- **Add/adjust theme colours** → edit `TOKENS` in `ui/theme.py`; both QSS and
  custom widgets pick it up. Don't hard-code hex elsewhere.
- **Add a new export field** → `MainWindow._on_export_json`.
- **Widen Auto-optimize** → `refine_period(search=...)` (and the `spin_opt`
  range in `main_window.py`).

## Gotchas

- Don't rank refinement/candidates by the 0–100 `score` — it saturates. Use
  `laplacian_var`.
- Keep `px/py` as `int` or `None`; UI spinboxes treat `0` as "unset".
- `estimate_period` accepts colour or grey; it converts internally
  (`_to_gray`). Colour is assumed BGR (OpenCV convention) / BGRA for 4ch.
- The detected period can legitimately be a half/double harmonic on tricky
  patterns; the candidate grid + Auto-optimize exist to recover the right one.

## Pointers

- User-facing usage, button reference, and "how to read the views" live in
  [`README.md`](README.md).
- Version lives in `cell_period_estimator/__init__.py` and `pyproject.toml` —
  bump both together.
