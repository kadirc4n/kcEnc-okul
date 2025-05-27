from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QPushButton, QFormLayout
)
from PyQt6.QtCore import pyqtSignal

class CreateVaultDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Kasa Oluştur")

        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.error_label = QLabel("") # Parola uyuşmazlığı için
        self.error_label.setStyleSheet("color: red")

        self.form_layout.addRow("Kasa Adı:", self.name_input)
        self.form_layout.addRow("Parola:", self.password_input)
        self.form_layout.addRow("Parola Tekrar:", self.confirm_password_input)

        self.layout.addLayout(self.form_layout)
        self.layout.addWidget(self.error_label)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.button_box)

        # Girdileri doğrula ve OK butonunu yönet
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        self.name_input.textChanged.connect(self.validate_input)
        self.password_input.textChanged.connect(self.validate_input)
        self.confirm_password_input.textChanged.connect(self.validate_input)

    def validate_input(self):
        name = self.name_input.text().strip()
        pw = self.password_input.text()
        confirm_pw = self.confirm_password_input.text()

        passwords_match = (pw == confirm_pw)
        inputs_filled = bool(name and pw and confirm_pw)

        if pw and confirm_pw and not passwords_match:
            self.error_label.setText("Parolalar uyuşmuyor!")
        else:
            self.error_label.setText("")

        self.ok_button.setEnabled(passwords_match and inputs_filled)

    def on_accept(self):
        # Zaten validate_input ile kontrol edildi ama tekrar emin olalım
        if self.password_input.text() == self.confirm_password_input.text() and \
           self.name_input.text().strip() and self.password_input.text():
            self.accept()
        else:
            # Normalde bu durum oluşmamalı çünkü OK butonu devre dışı kalır
            self.error_label.setText("Lütfen tüm alanları doğru doldurun.")

    def get_details(self) -> tuple[str, str]:
        return self.name_input.text().strip(), self.password_input.text() 