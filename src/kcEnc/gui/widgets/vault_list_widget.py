from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, 
    QListWidgetItem, QLabel, QAbstractItemView
)
from PyQt6.QtCore import pyqtSignal, Qt

from ...core import vault_manager

class VaultListWidget(QWidget):
    request_unlock = pyqtSignal(str) # vault_name
    request_create = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        self.label = QLabel("Mevcut Kasalar:")
        self.layout.addWidget(self.label)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        # Çift tıklama ile açma
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.layout.addWidget(self.list_widget)

        self.button_layout = QHBoxLayout()
        self.unlock_button = QPushButton("Seçili Kasayı Aç")
        self.unlock_button.clicked.connect(self.on_unlock_clicked)
        self.create_button = QPushButton("Yeni Kasa Oluştur")
        self.create_button.clicked.connect(self.request_create.emit)

        self.button_layout.addWidget(self.unlock_button)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.create_button)
        self.layout.addLayout(self.button_layout)

        self.refresh_vault_list()

    def refresh_vault_list(self):
        self.list_widget.clear()
        try:
            vaults = vault_manager.list_vaults()
            if vaults:
                for vault_name in vaults:
                    item = QListWidgetItem(vault_name)
                    self.list_widget.addItem(item)
                self.list_widget.setCurrentRow(0) # İlk öğeyi seçili yap
                self.unlock_button.setEnabled(True)
            else:
                self.list_widget.addItem("Henüz kasa oluşturulmadı.")
                self.unlock_button.setEnabled(False)
        except Exception as e:
            # Ana pencereye hata bildirmek daha iyi olabilir
            print(f"HATA: Kasa listesi alınamadı: {e}")
            self.list_widget.addItem("Kasa listesi alınırken hata oluştu.")
            self.unlock_button.setEnabled(False)

    def on_unlock_clicked(self):
        selected_item = self.list_widget.currentItem()
        if selected_item:
            # Ensure the item text is a valid vault name (not the placeholder message)
            vault_name = selected_item.text()
            if vault_name != "Henüz kasa oluşturulmadı." and vault_name != "Kasa listesi alınırken hata oluştu.":
                 self.request_unlock.emit(vault_name)

    def on_item_double_clicked(self, item: QListWidgetItem):
         vault_name = item.text()
         if vault_name != "Henüz kasa oluşturulmadı." and vault_name != "Kasa listesi alınırken hata oluştu.":
             self.request_unlock.emit(vault_name) 