import sys
from PyQt6.QtWidgets import QApplication

# Gerçek MainWindow import ediliyor
from src.kcEnc.gui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Uygulama stili ayarlanabilir (isteğe bağlı)
    # app.setStyle("Fusion") 

    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 