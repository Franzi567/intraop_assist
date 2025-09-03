import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from .main_window import MainWindow


def run():
    # High DPI / crisp rendering
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Intraoperative Assistenz – Harnblase")
    app.setOrganizationName("ISYS")

    win = MainWindow()
    win.resize(1400, 800)
    win.show()
    sys.excepthook = _exception_hook  # keep tracebacks visible on crash
    sys.exit(app.exec())


def _exception_hook(exc_type, exc_value, exc_traceback):
    # fall back to default printing; integrating with a logger is also fine
    import traceback, sys as _sys
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=_sys.stderr)


if __name__ == "__main__":
    run()
