from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QPushButton
)

class LoginDialog(QDialog):
    def __init__(self, vault_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Kasa Kilidini Aç: {vault_name}")

        self.layout = QVBoxLayout(self)

        self.label = QLabel(f"Lütfen '{vault_name}' kasasının parolasını girin:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.password_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.button_box)

        # OK butonu başlangıçta devre dışı, parola girilince aktifleşir
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(False)
        self.password_input.textChanged.connect(lambda text: ok_button.setEnabled(bool(text)))

    def get_password(self) -> str:
        return self.password_input.text() 