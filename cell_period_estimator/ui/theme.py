"""GLAS UI theme — a soft warm light theme.

Single source of truth for the design tokens.  ``TOKENS`` is consumed by
both the QSS stylesheet (standard widgets) and the custom-painted widgets
(spectrum, badges, overlays) so colors never drift apart.

Notes / Qt-QSS limitations:
* QSS has no ``text-transform`` or ``letter-spacing``.  Section / group
  titles are therefore upper-cased in code; the accent color, 10px size
  and weight 700 come from QSS.
"""

from __future__ import annotations

from string import Template

# --------------------------------------------------------------------------- #
# Design tokens (hex, verbatim from the GLAS spec)
# --------------------------------------------------------------------------- #
TOKENS = {
    # backgrounds (low -> high elevation)
    "bg_page": "#f7f4ef",
    "bg_panel": "#faf7f3",
    "bg_surface": "#fff8f2",
    "bg_elevated": "#fff4e8",
    "bg_input": "#ffffff",
    "side_panel": "#fff7ee",
    "toolbar": "#f2ece4",
    "statusbar": "#f0e9e0",
    # borders
    "border_default": "#e8d8c8",
    "border_input": "#c8b8a8",
    "border_hover": "#8a7060",
    "border_focus": "#f29f4b",
    # text
    "text_primary": "#3f3428",
    "text_secondary": "#7a6a5a",
    "text_hint": "#8a7660",
    "text_disabled": "#b0a090",
    # accent (orange)
    "accent": "#f29f4b",
    "accent_hover": "#f6b56b",
    "accent_active": "#d97d1e",
    "accent_bg": "#fff4e6",
    "accent_border": "#efd8b8",
    # selection / hover
    "selection": "#f6c38c",
    "hover_warm": "#f6efe6",
    "hover_warm_strong": "#fff4e8",
    "focus_bg": "#fffef9",
    # semantic
    "success": "#7abf9a",
    "success_bg": "#ebf7f0",
    "success_border": "#9ec9ad",
    "success_text": "#3e7f5d",
    "danger": "#cc7b6c",
    "danger_bg": "#feeee8",
    "warning": "#d9a24f",
    "min_accent": "#d8894f",
    "min_accent_bg": "#fff8f0",
    "min_accent_border": "#f0c8a8",
    "min_accent_text": "#9a5a2a",
    "max_accent": "#6ea8cf",
    "max_accent_bg": "#f0f7fc",
    "max_accent_border": "#a8c8e0",
    "max_accent_text": "#3a6a8a",
    # tooltip (inverted)
    "tooltip_bg": "#3f3428",
    "tooltip_text": "#faf7f3",
    "tooltip_border": "#2c2418",
    # lists / scrollbars / disabled
    "list_bg": "#f2ece4",
    "row_alt": "#faf5ee",
    "scroll_track": "#faf5ee",
    "scroll_thumb": "#d8c8b6",
    "scroll_thumb_hover": "#b8a898",
    "disabled_bg": "#faf6f0",
    "disabled_text": "#c8b89e",
    "tab_inactive": "#efe8de",
    # section header tiers
    "tier1_bg": "#fff4e8",
    "tier1_text": "#c97028",
    # typography
    "font_stack": ("'Segoe UI','PingFang TC','Microsoft JhengHei',"
                   "'Helvetica Neue',Arial,sans-serif"),
    "mono_stack": "'Consolas','Courier New',monospace",
}


_QSS = Template(r"""
* {
    font-family: $font_stack;
    font-size: 13px;
    color: $text_primary;
}

QMainWindow, QWidget, QDialog { background: $bg_page; color: $text_primary; }

/* -- toolbar ---------------------------------------------------------- */
QToolBar {
    background: $toolbar;
    border: 0;
    border-bottom: 1px solid $border_default;
    spacing: 6px;
    padding: 4px 6px;
}
QToolBar QToolButton {
    background: transparent;
    color: $text_secondary;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
}
QToolBar QToolButton:hover { background: $hover_warm; color: $text_primary; }
QToolBar QToolButton:pressed { background: $hover_warm_strong; }
QToolBar QToolButton:checked {
    background: $accent_bg; color: $accent_active; border: 1px solid $accent_border;
}
QToolBar QToolButton#primary {
    background: $accent; color: #ffffff; border: 1px solid $accent_active;
    padding: 6px 18px; font-weight: 700;
}
QToolBar QToolButton#primary:hover { background: $accent_hover; }
QToolBar QToolButton#primary:pressed { background: $accent_active; }
QToolBar QToolButton#primary:disabled { background: $disabled_bg; color: $disabled_text;
    border: 1px solid $border_default; }
QToolBar::separator { background: $border_default; width: 1px; margin: 5px 6px; }

/* -- status bar ------------------------------------------------------- */
QStatusBar { background: $statusbar; color: $text_secondary;
             border-top: 1px solid $border_default; }
QStatusBar::item { border: 0; }

/* -- scroll area (right results column) ------------------------------- */
QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QWidget#resultsPanel { background: transparent; }

/* -- stat readout cards ----------------------------------------------- */
QFrame#statCard {
    background: $bg_elevated;
    border: 1px solid $border_default;
    border-radius: 9px;
}
QFrame#statCard[accent="true"] {
    background: $accent_bg;
    border: 1px solid $accent_border;
}
QLabel#statTitle {
    color: $text_secondary; font-size: 10px; font-weight: 700; background: transparent;
}
QLabel#statValue {
    color: $text_primary; font-size: 23px; font-weight: 700; background: transparent;
}
QLabel#statValue[accent="true"] { color: $accent_active; }
QLabel#statSub { color: $text_hint; font-size: 11px; background: transparent; }

/* -- golden cell preview surface -------------------------------------- */
QLabel#gcPreview {
    background: $bg_panel; color: $text_hint;
    border: 1px solid $border_default; border-radius: 8px;
}

/* -- group boxes (section cards) -------------------------------------- */
QGroupBox {
    background: $bg_surface;
    border: 1px solid $border_default;
    border-radius: 9px;
    margin-top: 16px;
    padding: 12px 10px 10px 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    top: 2px;
    padding: 2px 8px;
    background: $tier1_bg;
    border: 1px solid $accent_border;
    border-radius: 5px;
    color: $tier1_text;
    font-size: 10px;
    font-weight: 700;
}

/* -- push buttons ----------------------------------------------------- */
QPushButton {
    background: $bg_input;
    color: $text_primary;
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 18px;
    font-weight: 600;
}
QPushButton:hover { border-color: $border_hover; background: $hover_warm; }
QPushButton:focus { border: 1.5px solid $border_focus; }
QPushButton:disabled { background: $disabled_bg; color: $disabled_text;
                       border-color: $border_default; }
QPushButton[variant="primary"] {
    background: $accent; color: #ffffff; border: 1px solid $accent_active;
}
QPushButton[variant="primary"]:hover { background: $accent_hover; }
QPushButton[variant="primary"]:pressed { background: $accent_active; }
QPushButton[variant="secondary"] {
    background: $bg_input; color: $accent_active; border: 1px solid $accent;
}
QPushButton[variant="secondary"]:hover { background: $accent_bg; }
QPushButton[variant="ghost"] {
    background: transparent; color: $text_secondary; border: 1px solid transparent;
}
QPushButton[variant="ghost"]:hover { background: $hover_warm; }
QPushButton[variant="success"] {
    background: $success_bg; color: $success_text; border: 1px solid $success_border;
}

/* -- inputs ----------------------------------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: $bg_input;
    color: $text_primary;
    border: 1.5px solid $border_input;
    border-radius: 5px;
    padding: 2px 6px;
    min-height: 24px;
    selection-background-color: $selection;
    selection-color: $text_primary;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border-color: $border_hover;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1.5px solid $border_focus; background: $focus_bg;
}
QComboBox::drop-down { border: 0; width: 18px; }
QComboBox QAbstractItemView {
    background: $bg_input; border: 1px solid $border_default;
    selection-background-color: $selection; selection-color: $text_primary;
    outline: 0;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 16px; background: $bg_elevated; border-left: 1px solid $border_default;
}

/* -- labels ----------------------------------------------------------- */
QLabel { background: transparent; color: $text_primary; }
QLabel:disabled { color: $text_disabled; }

/* -- views / lists ---------------------------------------------------- */
QGraphicsView {
    background: $bg_panel; border: 1px solid $border_default; border-radius: 7px;
}
QAbstractItemView {
    background: $list_bg; alternate-background-color: $row_alt;
    border: 1px solid $border_default; border-radius: 6px;
    selection-background-color: $selection; selection-color: $text_primary;
    outline: 0;
}
QHeaderView::section {
    background: $list_bg; color: $accent_active; border: 0;
    border-bottom: 1px solid $border_default; padding: 4px 8px; font-weight: 700;
}

/* -- splitter --------------------------------------------------------- */
QSplitter::handle { background: $border_default; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }

/* -- scrollbars ------------------------------------------------------- */
QScrollBar:vertical { background: $scroll_track; width: 11px; margin: 0; border: 0; }
QScrollBar::handle:vertical { background: $scroll_thumb; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $scroll_thumb_hover; }
QScrollBar:horizontal { background: $scroll_track; height: 11px; margin: 0; border: 0; }
QScrollBar::handle:horizontal { background: $scroll_thumb; border-radius: 5px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: $scroll_thumb_hover; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* -- progress bar ----------------------------------------------------- */
QProgressBar {
    background: $bg_elevated; border: 1px solid $border_default;
    border-radius: 5px; text-align: center; min-height: 14px; color: $text_secondary;
}
QProgressBar::chunk { background: $accent; border-radius: 5px; }

/* -- menus / tooltips ------------------------------------------------- */
QMenu { background: $bg_surface; border: 1px solid $border_default; padding: 4px; }
QMenu::item { padding: 4px 18px; border-radius: 4px; }
QMenu::item:selected { background: $selection; color: $text_primary; }
QToolTip {
    background: $tooltip_bg; color: $tooltip_text; border: 1px solid $tooltip_border;
    padding: 4px 6px;
}
""")


def build_stylesheet() -> str:
    """Return the full QSS string with tokens substituted in."""
    return _QSS.substitute(TOKENS)


def apply_theme(app) -> None:
    """Apply the GLAS theme (palette + stylesheet) to a QApplication."""
    from PySide6.QtGui import QColor, QFont, QPalette

    app.setStyle("Fusion")  # consistent base for QSS across platforms

    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(TOKENS["bg_page"]))
    pal.setColor(QPalette.Base, QColor(TOKENS["bg_input"]))
    pal.setColor(QPalette.AlternateBase, QColor(TOKENS["row_alt"]))
    pal.setColor(QPalette.Text, QColor(TOKENS["text_primary"]))
    pal.setColor(QPalette.WindowText, QColor(TOKENS["text_primary"]))
    pal.setColor(QPalette.ButtonText, QColor(TOKENS["text_primary"]))
    pal.setColor(QPalette.Highlight, QColor(TOKENS["selection"]))
    pal.setColor(QPalette.HighlightedText, QColor(TOKENS["text_primary"]))
    pal.setColor(QPalette.ToolTipBase, QColor(TOKENS["tooltip_bg"]))
    pal.setColor(QPalette.ToolTipText, QColor(TOKENS["tooltip_text"]))
    app.setPalette(pal)

    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    app.setStyleSheet(build_stylesheet())
