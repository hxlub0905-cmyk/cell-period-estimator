"""Entry point: ``python -m cell_period_estimator``."""

from __future__ import annotations

import sys


def main() -> int:
    """Launch the Qt application and run the main window."""
    from PySide6.QtWidgets import QApplication

    from .ui import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
