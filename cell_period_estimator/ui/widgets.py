"""Custom Qt widgets, drawn with QPainter to avoid extra dependencies."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import TOKENS


# --------------------------------------------------------------------------- #
# numpy <-> Qt conversion
# --------------------------------------------------------------------------- #
def numpy_to_qimage(array: np.ndarray) -> QImage:
    """Convert a grey (H,W) or RGB (H,W,3) uint8 array to a QImage."""
    arr = np.ascontiguousarray(array)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        h, w = arr.shape
        return QImage(arr.data, w, h, w, QImage.Format_Grayscale8).copy()
    h, w, ch = arr.shape
    if ch == 3:
        return QImage(arr.data, w, h, 3 * w, QImage.Format_RGB888).copy()
    if ch == 4:
        return QImage(arr.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
    raise ValueError(f"unsupported channel count: {ch}")


def numpy_to_qpixmap(array: np.ndarray) -> QPixmap:
    """Convert an array to a QPixmap."""
    return QPixmap.fromImage(numpy_to_qimage(array))


def qimage_to_gray(image: QImage) -> Optional[np.ndarray]:
    """Convert a QImage (e.g. from the clipboard) to a grey (H,W) uint8 array.

    Returns ``None`` for a null image.  Used by the paste / drag-drop paths so
    a pasted screenshot is treated like any loaded scan.
    """
    if image.isNull():
        return None
    img = image.convertToFormat(QImage.Format_Grayscale8)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    buf = bytes(img.constBits())[: bpl * h]
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, bpl)[:, :w]
    return np.ascontiguousarray(arr)


# --------------------------------------------------------------------------- #
# image view with ROI + period overlay
# --------------------------------------------------------------------------- #
class ImageView(QGraphicsView):
    """Displays an image with wheel-zoom, rubber-band ROI and a grid overlay.

    Emits ``cropChanged(x, y, w, h)`` in image coordinates whenever a new
    ROI rectangle is dragged.
    """

    cropChanged = Signal(int, int, int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self._image_size: Tuple[int, int] = (0, 0)  # (w, h)
        self._roi: Optional[Tuple[int, int, int, int]] = None
        self._crop_mode = False
        self._rubber_origin: Optional[QPointF] = None
        self._rubber_rect: Optional[QRectF] = None

        # period grid overlay
        self._grid_px: Optional[int] = None
        self._grid_py: Optional[int] = None
        self._grid_origin: Tuple[int, int] = (0, 0)
        self._show_grid = False

    # -- public API ----------------------------------------------------- #
    def set_image(self, array: np.ndarray) -> None:
        pix = numpy_to_qpixmap(array)
        self._pixmap_item.setPixmap(pix)
        self._image_size = (pix.width(), pix.height())
        self._scene.setSceneRect(QRectF(pix.rect()))
        self.fit()

    def fit(self) -> None:
        if self._image_size[0]:
            self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)

    def set_crop_mode(self, enabled: bool) -> None:
        self._crop_mode = enabled
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)

    def clear_roi(self) -> None:
        self._roi = None
        self._rubber_rect = None
        self.viewport().update()

    def roi(self) -> Optional[Tuple[int, int, int, int]]:
        return self._roi

    def set_grid(self, px: Optional[int], py: Optional[int],
                 origin: Tuple[int, int] = (0, 0)) -> None:
        self._grid_px, self._grid_py, self._grid_origin = px, py, origin
        self.viewport().update()

    def show_grid(self, enabled: bool) -> None:
        self._show_grid = enabled
        self.viewport().update()

    # -- interaction ---------------------------------------------------- #
    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if self._crop_mode and event.button() == Qt.LeftButton:
            self._rubber_origin = self.mapToScene(event.pos())
            self._rubber_rect = QRectF(self._rubber_origin, self._rubber_origin)
            self.viewport().update()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._crop_mode and self._rubber_origin is not None:
            current = self.mapToScene(event.pos())
            self._rubber_rect = QRectF(self._rubber_origin, current).normalized()
            self.viewport().update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._crop_mode and self._rubber_origin is not None:
            current = self.mapToScene(event.pos())
            rect = QRectF(self._rubber_origin, current).normalized()
            self._rubber_origin = None
            w_img, h_img = self._image_size
            x = int(max(0, min(rect.left(), w_img)))
            y = int(max(0, min(rect.top(), h_img)))
            w = int(max(0, min(rect.width(), w_img - x)))
            h = int(max(0, min(rect.height(), h_img - y)))
            if w >= 4 and h >= 4:
                self._roi = (x, y, w, h)
                self._rubber_rect = QRectF(x, y, w, h)
                self.cropChanged.emit(x, y, w, h)
            self.viewport().update()
            return
        super().mouseReleaseEvent(event)

    # -- overlay drawing ------------------------------------------------ #
    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        if self._show_grid:
            self._draw_grid(painter)
        if self._rubber_rect is not None:
            sel = QColor(TOKENS["selection"])
            sel.setAlpha(60)
            pen = QPen(QColor(TOKENS["accent"]), 0, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(sel)
            painter.drawRect(self._rubber_rect)

    def _draw_grid(self, painter: QPainter) -> None:
        w_img, h_img = self._image_size
        if not w_img:
            return
        ox, oy = self._grid_origin

        # Collect the line geometry once, then stroke it twice: a dark halo
        # underneath for contrast on bright cells, the accent line on top for
        # contrast on dark cells.  Cosmetic pens keep the width constant at any
        # zoom so the grid never disappears or turns into fat bars.
        xs = (list(range(ox, w_img + 1, self._grid_px))
              if self._grid_px and self._grid_px > 1 else [])
        ys = (list(range(oy, h_img + 1, self._grid_py))
              if self._grid_py and self._grid_py > 1 else [])

        def stroke(color: QColor, width: float) -> None:
            pen = QPen(color, width)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for x in xs:
                painter.drawLine(QPointF(x, 0), QPointF(x, h_img))
            for y in ys:
                painter.drawLine(QPointF(0, y), QPointF(w_img, y))

        halo = QColor(TOKENS["text_primary"])
        halo.setAlpha(140)
        stroke(halo, 3.0)
        accent = QColor(TOKENS["accent"])
        accent.setAlpha(235)
        stroke(accent, 1.2)

        # Mark the lattice origin so the phase of the grid is unambiguous.
        marker = QColor(TOKENS["accent_active"])
        pen = QPen(marker, 2.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        r = 5.0
        painter.drawLine(QPointF(ox - r, oy), QPointF(ox + r, oy))
        painter.drawLine(QPointF(ox, oy - r), QPointF(ox, oy + r))


# --------------------------------------------------------------------------- #
# headline stat readout card
# --------------------------------------------------------------------------- #
class StatCard(QFrame):
    """A compact "headline number" card: small title, big value, sub-caption.

    Styling lives in the QSS (object names ``statCard`` / ``statTitle`` /
    ``statValue`` / ``statSub``) so colors stay in the single token source.
    The ``accent`` dynamic property promotes one card to the primary hue.
    """

    def __init__(self, title: str, accent: bool = False,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setProperty("accent", "true" if accent else "false")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(1)

        self._title = QLabel(title.upper())
        self._title.setObjectName("statTitle")
        self._value = QLabel("–")
        self._value.setObjectName("statValue")
        self._value.setProperty("accent", "true" if accent else "false")
        self._sub = QLabel("")
        self._sub.setObjectName("statSub")

        lay.addWidget(self._title)
        lay.addWidget(self._value)
        lay.addWidget(self._sub)

    def set_value(self, value: str, sub: str = "") -> None:
        self._value.setText(value)
        self._sub.setText(sub)
        self._sub.setVisible(bool(sub))


# --------------------------------------------------------------------------- #
# axis-mode badge
# --------------------------------------------------------------------------- #
class AxisBadge(QLabel):
    """Soft semantic chip reflecting the detected axis mode."""

    # (background, text, border, label) — low-saturation semantic chips.
    _STYLES = {
        "XY": (TOKENS["success_bg"], TOKENS["success_text"],
               TOKENS["success_border"], "XY periodic"),
        "X": (TOKENS["min_accent_bg"], TOKENS["min_accent_text"],
              TOKENS["min_accent_border"], "X only"),
        "Y": (TOKENS["min_accent_bg"], TOKENS["min_accent_text"],
              TOKENS["min_accent_border"], "Y only"),
        "NONE": (TOKENS["danger_bg"], TOKENS["danger"],
                 TOKENS["danger"], "no period"),
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(110)
        self.setMinimumHeight(34)
        self.set_mode("NONE")

    def set_mode(self, mode: str) -> None:
        bg, fg, border, text = self._STYLES.get(mode, self._STYLES["NONE"])
        self.setText(f"{mode}  •  {text}")
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; border:1px solid {border};"
            "border-radius:8px; padding:6px 12px; font-weight:700; font-size:13px;"
        )


# --------------------------------------------------------------------------- #
# FFT spectrum plot
# --------------------------------------------------------------------------- #
class SpectrumPlot(QWidget):
    """Self-drawn X/Y FFT spectra (normalized magnitude vs period)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._x = None  # (periods, norm_mag, peak)
        self._y = None

    def set_spectra(self, spec_x, spec_y) -> None:
        self._x = self._prep(spec_x)
        self._y = self._prep(spec_y)
        self.update()

    @staticmethod
    def _prep(spec):
        if spec is None or spec.periods.size == 0:
            return None
        return (spec.periods, spec.normalized_magnitude(), spec.peak_period)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(TOKENS["bg_panel"]))
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        mid = h // 2
        # X uses the single accent; Y uses the cool semantic marker so the
        # two series stay distinguishable without a second accent hue.
        self._plot_axis(painter, self._x, 0, mid, QColor(TOKENS["accent"]), "X")
        self._plot_axis(painter, self._y, mid, h, QColor(TOKENS["max_accent"]), "Y")
        painter.setPen(QPen(QColor(TOKENS["border_default"]), 1))
        painter.drawLine(0, mid, w, mid)

    def _plot_axis(self, painter, data, top, bottom, color, label):
        painter.setPen(QPen(QColor(TOKENS["text_secondary"]), 1))
        painter.drawText(6, top + 14, f"{label} spectrum")
        if data is None:
            painter.setPen(QPen(QColor(TOKENS["text_disabled"]), 1))
            painter.drawText(60, (top + bottom) // 2, "(no period)")
            return
        periods, mag, peak = data
        w = self.width()
        plot_h = (bottom - top) - 22
        base = bottom - 6
        n = periods.size
        pen = QPen(color, 1)
        painter.setPen(pen)
        pmin, pmax = float(periods.min()), float(periods.max())
        span = max(pmax - pmin, 1e-6)
        prev = None
        for i in range(n):
            xpix = int((periods[i] - pmin) / span * (w - 12)) + 6
            ypix = int(base - mag[i] * plot_h)
            if prev is not None:
                painter.drawLine(prev[0], prev[1], xpix, ypix)
            prev = (xpix, ypix)
        if peak:
            xpix = int((peak - pmin) / span * (w - 12)) + 6
            painter.setPen(QPen(QColor(TOKENS["accent_active"]), 1, Qt.DashLine))
            painter.drawLine(xpix, top + 18, xpix, base)
            painter.drawText(min(xpix + 3, w - 40), top + 28, f"p={peak:.0f}")


# --------------------------------------------------------------------------- #
# candidate thumbnail grid
# --------------------------------------------------------------------------- #
class CandidateGrid(QWidget):
    """Grid of candidate stacks with relative sharpness; click to choose."""

    candidateChosen = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(6)
        self._cells: List[QWidget] = []

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            wdg = item.widget()
            if wdg is not None:
                wdg.deleteLater()
        self._cells = []

    def set_candidates(self, items: List[dict]) -> None:
        """``items``: list of dicts with keys ``px, py, image, sharpness, best``."""
        self.clear()
        if not items:
            return
        best_idx = max(range(len(items)), key=lambda i: items[i].get("sharpness", 0))
        cols = min(4, len(items))
        for i, it in enumerate(items):
            cell = _CandidateCell(
                it["px"], it["py"], it["image"], it.get("sharpness", 0.0),
                highlight=(i == best_idx),
            )
            cell.chosen.connect(self.candidateChosen)
            self._layout.addWidget(cell, i // cols, i % cols)
            self._cells.append(cell)


class _CandidateCell(QWidget):
    chosen = Signal(int, int)

    def __init__(self, px, py, image: np.ndarray, sharpness: float,
                 highlight: bool = False, parent=None):
        super().__init__(parent)
        self._px, self._py = px, py
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        thumb = QLabel()
        pix = numpy_to_qpixmap(image).scaled(
            96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumb.setPixmap(pix)
        thumb.setAlignment(Qt.AlignCenter)
        caption = QLabel(f"{px}×{py}\n{sharpness:.0f}%")
        caption.setAlignment(Qt.AlignCenter)
        caption.setStyleSheet(
            f"color:{TOKENS['text_secondary']}; font-size:11px; border:0;")
        layout.addWidget(thumb)
        layout.addWidget(caption)

        # Best candidate gets the accent border; others a default thin border.
        border = TOKENS["accent"] if highlight else TOKENS["border_default"]
        width = 2 if highlight else 1
        bg = TOKENS["accent_bg"] if highlight else TOKENS["bg_surface"]
        self.setStyleSheet(
            f"background:{bg}; border:{width}px solid {border}; border-radius:6px;")

    def mousePressEvent(self, event):
        self.chosen.emit(int(self._px), int(self._py))
