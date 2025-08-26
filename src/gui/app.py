import sys
from PySide6.QtWidgets import QApplication
from .main_window import MainWindow

def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1400, 800)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()