"""Main application window."""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core import (
    candidate_periods,
    choose_origin,
    estimate_period,
    ghosting_score,
    refine_period,
    stack_cells,
)
from .widgets import AxisBadge, CandidateGrid, ImageView, SpectrumPlot


# --------------------------------------------------------------------------- #
# background estimation worker
# --------------------------------------------------------------------------- #
class _EstimateWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, image: np.ndarray, min_period: Optional[int]):
        super().__init__()
        self._image = image
        self._min_period = min_period

    def run(self) -> None:
        try:
            result = estimate_period(self._image, min_period=self._min_period)
            self.finished.emit(result)
        except Exception as exc:  # surface to the UI thread
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Top-level window: image view on the left, results panel on the right."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cell Period Estimator")
        self.resize(1280, 820)

        self._image: Optional[np.ndarray] = None        # full image (grey)
        self._analysis_image: Optional[np.ndarray] = None  # ROI or full
        self._roi: Optional[Tuple[int, int, int, int]] = None
        self._result = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[_EstimateWorker] = None

        self._build_toolbar()
        self._build_layout()

    # -- construction --------------------------------------------------- #
    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Main")
        tb.setMovable(False)

        self.act_load = QAction("Load Image", self)
        self.act_estimate = QAction("Estimate Period", self)
        self.act_crop = QAction("Crop ROI", self, checkable=True)
        self.act_clear = QAction("Clear ROI", self)
        self.act_export_gc = QAction("Export GC", self)
        self.act_export_json = QAction("Export JSON", self)

        self.act_load.triggered.connect(self._on_load)
        self.act_estimate.triggered.connect(self._on_estimate)
        self.act_crop.toggled.connect(self._on_crop_toggle)
        self.act_clear.triggered.connect(self._on_clear_roi)
        self.act_export_gc.triggered.connect(self._on_export_gc)
        self.act_export_json.triggered.connect(self._on_export_json)

        for act in (self.act_load, self.act_estimate, self.act_crop,
                    self.act_clear, self.act_export_gc, self.act_export_json):
            tb.addAction(act)

    def _build_layout(self) -> None:
        splitter = QSplitter(Qt.Horizontal)

        self.view = ImageView()
        self.view.cropChanged.connect(self._on_crop_changed)
        splitter.addWidget(self.view)

        panel = QWidget()
        pl = QVBoxLayout(panel)

        # --- period results ------------------------------------------- #
        period_box = QGroupBox("Period")
        form = QFormLayout(period_box)
        self.badge = AxisBadge()
        self.spin_px = QSpinBox(); self.spin_px.setRange(0, 100000)
        self.spin_py = QSpinBox(); self.spin_py.setRange(0, 100000)
        self.lbl_conf = QLabel("–")
        self.spin_min = QSpinBox(); self.spin_min.setRange(0, 100000)
        self.spin_min.setValue(0); self.spin_min.setSpecialValueText("auto")
        self.spin_opt = QSpinBox(); self.spin_opt.setRange(0, 64)
        self.spin_opt.setValue(6)
        self.btn_optimize = QPushButton("Auto-optimize ±")
        self.btn_optimize.clicked.connect(self._on_optimize)

        form.addRow("Axis mode", self.badge)
        form.addRow("X period", self.spin_px)
        form.addRow("Y period", self.spin_py)
        form.addRow("Confidence", self.lbl_conf)
        form.addRow("Min period", self.spin_min)
        opt_row = QHBoxLayout()
        opt_row.addWidget(self.spin_opt)
        opt_row.addWidget(self.btn_optimize)
        opt_w = QWidget(); opt_w.setLayout(opt_row)
        form.addRow("Optimize range", opt_w)
        pl.addWidget(period_box)

        # --- golden cell preview -------------------------------------- #
        gc_box = QGroupBox("Golden Cell")
        gl = QVBoxLayout(gc_box)
        ctrl = QHBoxLayout()
        self.cmb_method = QComboBox(); self.cmb_method.addItems(["mean", "median"])
        self.cmb_method.currentTextChanged.connect(self._refresh_gc)
        self.cmb_samples = QComboBox()
        self.cmb_samples.addItems(["all", "16", "32", "64", "128"])
        self.cmb_samples.currentTextChanged.connect(self._refresh_gc)
        ctrl.addWidget(QLabel("method")); ctrl.addWidget(self.cmb_method)
        ctrl.addWidget(QLabel("samples")); ctrl.addWidget(self.cmb_samples)
        gl.addLayout(ctrl)
        self.lbl_gc = QLabel("Estimate a period to preview the Golden Cell.")
        self.lbl_gc.setAlignment(Qt.AlignCenter)
        self.lbl_gc.setMinimumHeight(160)
        self.lbl_gc.setStyleSheet("background:#101418; color:#9aa6ad;")
        gl.addWidget(self.lbl_gc)
        self.lbl_sharp = QLabel("sharpness: –")
        self.lbl_sharp.setAlignment(Qt.AlignCenter)
        gl.addWidget(self.lbl_sharp)
        pl.addWidget(gc_box)

        # --- spectrum ------------------------------------------------- #
        spec_box = QGroupBox("FFT Spectrum")
        sl = QVBoxLayout(spec_box)
        self.spectrum = SpectrumPlot()
        sl.addWidget(self.spectrum)
        pl.addWidget(spec_box)

        # --- candidates ----------------------------------------------- #
        cand_box = QGroupBox("Candidates")
        cl = QVBoxLayout(cand_box)
        self.candidates = CandidateGrid()
        self.candidates.candidateChosen.connect(self._on_candidate_chosen)
        cl.addWidget(self.candidates)
        pl.addWidget(cand_box)

        pl.addStretch(1)
        panel.setMinimumWidth(440)
        splitter.addWidget(panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Load an EBeam scan image to begin.")

    # -- helpers -------------------------------------------------------- #
    def _min_period(self) -> Optional[int]:
        v = self.spin_min.value()
        return v if v > 0 else None

    def _current_pxpy(self) -> Tuple[Optional[int], Optional[int]]:
        px = self.spin_px.value() or None
        py = self.spin_py.value() or None
        return px, py

    def _refresh_analysis_image(self) -> None:
        if self._image is None:
            return
        if self._roi is not None:
            x, y, w, h = self._roi
            self._analysis_image = self._image[y:y + h, x:x + w]
        else:
            self._analysis_image = self._image

    # -- actions -------------------------------------------------------- #
    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load image", "",
            "Images (*.png *.tif *.tiff *.jpg *.jpeg *.bmp)")
        if not path:
            return
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            QMessageBox.warning(self, "Load failed", f"Could not read:\n{path}")
            return
        self._image = img
        self._roi = None
        self._result = None
        self.view.set_image(img)
        self.view.show_grid(False)
        self.candidates.clear()
        self.statusBar().showMessage(
            f"Loaded {path}  ({img.shape[1]}×{img.shape[0]})")

    def _on_crop_toggle(self, checked: bool) -> None:
        self.view.set_crop_mode(checked)

    def _on_crop_changed(self, x, y, w, h) -> None:
        self._roi = (x, y, w, h)
        self.statusBar().showMessage(f"ROI = ({x}, {y}, {w}, {h})")

    def _on_clear_roi(self) -> None:
        self._roi = None
        self.view.clear_roi()
        self.statusBar().showMessage("ROI cleared.")

    def _on_estimate(self) -> None:
        if self._image is None:
            return
        self._refresh_analysis_image()
        self.act_estimate.setEnabled(False)
        self.statusBar().showMessage("Estimating period…")

        self._thread = QThread()
        self._worker = _EstimateWorker(self._analysis_image, self._min_period())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_estimate_done)
        self._worker.failed.connect(self._on_estimate_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_estimate_failed(self, message: str) -> None:
        self.act_estimate.setEnabled(True)
        QMessageBox.critical(self, "Estimation error", message)
        self.statusBar().showMessage("Estimation failed.")

    def _on_estimate_done(self, result) -> None:
        self.act_estimate.setEnabled(True)
        self._result = result
        self.badge.set_mode(result.axis_mode)
        self.spin_px.setValue(result.px or 0)
        self.spin_py.setValue(result.py or 0)
        self.lbl_conf.setText(
            f"X {result.confidence_x:.0f}%   Y {result.confidence_y:.0f}%")
        self.spectrum.set_spectra(result.spectrum_x, result.spectrum_y)
        self.view.set_grid(result.px, result.py)
        self.view.show_grid(result.axis_mode != "NONE")
        msg = f"Detected {result.axis_mode}: px={result.px}, py={result.py}"
        if result.warnings:
            msg += "  | " + "; ".join(result.warnings)
        self.statusBar().showMessage(msg)
        self._refresh_gc()
        self._refresh_candidates()

    def _on_optimize(self) -> None:
        if self._analysis_image is None:
            self._refresh_analysis_image()
        px, py = self._current_pxpy()
        if not px or not py or self._analysis_image is None:
            QMessageBox.information(
                self, "Optimize", "Need a 2-D (XY) period to optimize.")
            return
        search = self.spin_opt.value()
        method = self.cmb_method.currentText()
        bpx, bpy, score = refine_period(
            self._analysis_image, px, py, search=search, method=method)
        self.spin_px.setValue(bpx)
        self.spin_py.setValue(bpy)
        self.view.set_grid(bpx, bpy)
        self.statusBar().showMessage(
            f"Optimized to px={bpx}, py={bpy} (lap_var={score:.1f})")
        self._refresh_gc()

    # -- golden cell / candidates -------------------------------------- #
    def _samples(self) -> Optional[int]:
        txt = self.cmb_samples.currentText()
        return None if txt == "all" else int(txt)

    def _refresh_gc(self) -> None:
        px, py = self._current_pxpy()
        if not px or not py or self._analysis_image is None:
            return
        method = self.cmb_method.currentText()
        stacked = stack_cells(self._analysis_image, px, py, method=method,
                              origin=choose_origin(self._analysis_image.shape, px, py),
                              sample_n=self._samples())
        from .widgets import numpy_to_qpixmap
        pix = numpy_to_qpixmap(stacked).scaled(
            220, 220, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.lbl_gc.setPixmap(pix)
        score, lap_var, edge = ghosting_score(stacked)
        verdict = ("aligned" if score >= 60 else
                   "marginal" if score >= 30 else "ghosting")
        self.lbl_sharp.setText(
            f"sharpness: {score:.0f}%  ({verdict})  |  lap_var={lap_var:.1f}")

    def _refresh_candidates(self) -> None:
        px, py = self._current_pxpy()
        if not px or not py or self._analysis_image is None:
            self.candidates.clear()
            return
        h, w = self._analysis_image.shape[:2]
        lo = max(2, self._min_period() or 4)
        hi = min(w, h) // 2
        method = self.cmb_method.currentText()
        items: List[dict] = []
        for cpx, cpy in candidate_periods(px, py, lo, hi):
            stacked = stack_cells(self._analysis_image, cpx, cpy, method=method)
            _, lap_var, _ = ghosting_score(stacked)
            items.append({"px": cpx, "py": cpy, "image": stacked,
                          "lap_var": lap_var})
        if not items:
            self.candidates.clear()
            return
        best = max(it["lap_var"] for it in items) or 1.0
        for it in items:
            it["sharpness"] = 100.0 * it["lap_var"] / best
        self.candidates.set_candidates(items)

    def _on_candidate_chosen(self, px: int, py: int) -> None:
        self.spin_px.setValue(px)
        self.spin_py.setValue(py)
        self.view.set_grid(px, py)
        self.statusBar().showMessage(f"Selected candidate px={px}, py={py}")
        self._refresh_gc()

    # -- exports -------------------------------------------------------- #
    def _on_export_gc(self) -> None:
        px, py = self._current_pxpy()
        if not px or not py or self._analysis_image is None:
            QMessageBox.information(self, "Export GC", "No Golden Cell to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Golden Cell", "golden_cell.png", "PNG (*.png)")
        if not path:
            return
        stacked = stack_cells(self._analysis_image, px, py,
                              method=self.cmb_method.currentText(),
                              sample_n=self._samples())
        cv2.imwrite(path, stacked)
        self.statusBar().showMessage(f"Saved Golden Cell → {path}")

    def _on_export_json(self) -> None:
        if self._result is None and not any(self._current_pxpy()):
            QMessageBox.information(self, "Export JSON", "Nothing to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", "period.json", "JSON (*.json)")
        if not path:
            return
        px, py = self._current_pxpy()
        score = None
        if px and py and self._analysis_image is not None:
            stacked = stack_cells(self._analysis_image, px, py,
                                  method=self.cmb_method.currentText())
            score, _, _ = ghosting_score(stacked)
        data = {
            "px": px,
            "py": py,
            "roi": list(self._roi) if self._roi else None,
            "axis_mode": self._result.axis_mode if self._result else None,
            "confidence": {
                "x": self._result.confidence_x if self._result else None,
                "y": self._result.confidence_y if self._result else None,
            },
            "score": score,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        self.statusBar().showMessage(f"Saved metadata → {path}")
