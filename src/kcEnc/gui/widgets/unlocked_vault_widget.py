import sys
import os
import tempfile
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QAbstractItemView,
    QTableWidgetItem, QLabel, QTextEdit, QSplitter, QStackedWidget, QMessageBox,
    QFileDialog, QApplication, QHeaderView, QScrollArea, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QMovie, QPalette
from PyQt6.QtCore import Qt, pyqtSignal, QByteArray, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget

from ...core import vault_manager
from ...core import database_manager # file metadata almak için

class UnlockedVaultWidget(QWidget):
    request_lock = pyqtSignal()
    # Dosya işlemleri için sinyaller MainWindow'a gönderilecek
    # (Doğrudan vault_manager çağırmak yerine)
    request_add_file = pyqtSignal()
    request_view_file = pyqtSignal(str) # file_id
    request_save_as = pyqtSignal(str) # file_id
    request_delete_file = pyqtSignal(str) # file_id

    # Desteklenen dosya türleri (önizleme için)
    TEXT_EXTENSIONS = [".txt", ".md", ".log", ".py", ".json", ".xml", ".ini", ".yaml", ".csv"]
    IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"]
    VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".wmv"] # Sistem codec'lerine bağlı

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_vault_name: str | None = None
        self._media_player = None
        self._temp_file_path: Path | None = None # Video için geçici dosya

        self.main_layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

        # --- Sol Taraf: Dosya Listesi ve Butonlar --- #
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels(["Dosya Adı", "Tür", "Boyut (bytes)", "Değiştirilme Tarihi"])
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_table.itemSelectionChanged.connect(self.on_file_selection_changed)
        self.file_table.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.left_layout.addWidget(self.file_table)

        self.button_layout = QHBoxLayout()
        self.add_button = QPushButton("Dosya Ekle")
        self.view_button = QPushButton("Görüntüle")
        self.save_as_button = QPushButton("Farklı Kaydet")
        self.delete_button = QPushButton("Sil")
        self.lock_button = QPushButton("Kasayı Kilitle")

        self.add_button.clicked.connect(self.request_add_file.emit)
        self.view_button.clicked.connect(self.on_view_clicked)
        self.save_as_button.clicked.connect(self.on_save_as_clicked)
        self.delete_button.clicked.connect(self.on_delete_clicked)
        self.lock_button.clicked.connect(self.request_lock.emit)

        self.button_layout.addWidget(self.add_button)
        self.button_layout.addWidget(self.view_button)
        self.button_layout.addWidget(self.save_as_button)
        self.button_layout.addWidget(self.delete_button)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.lock_button)
        self.left_layout.addLayout(self.button_layout)

        # --- Sağ Taraf: Önizleme Alanı --- #
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)
        self.preview_stack = QStackedWidget()
        self.right_layout.addWidget(self.preview_stack)

        # Önizleme widget'ları
        self.placeholder_label = QLabel("Önizlemek için bir dosya seçin.")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)

        # --- Resim Önizleme için QScrollArea ---
        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setBackgroundRole(QPalette.ColorRole.Window) # Arkaplanı ayarla
        self.image_scroll_area.setWidgetResizable(True) # İçindeki widget'ın boyutlanmasını sağla
        self.image_scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter) # İçeriği ortala

        self.image_preview_label = QLabel()
        self.image_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # setScaledContents kaldırıldı, QScrollArea yönetecek
        self.image_scroll_area.setWidget(self.image_preview_label) # QLabel'i ScrollArea'ya ekle
        # --- Resim Önizleme Sonu ---

        self.video_preview_widget = QVideoWidget()
        self.unsupported_label = QLabel("Bu dosya türü için uygulama içi önizleme desteklenmiyor.\n'Farklı Kaydet' seçeneğini kullanabilirsiniz.")
        self.unsupported_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unsupported_label.setWordWrap(True)
        self.loading_label = QLabel("Önizleme yükleniyor...") # Görüntüleme/Çözme sırasında
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_stack.addWidget(self.placeholder_label) # index 0
        self.preview_stack.addWidget(self.text_preview)      # index 1
        self.preview_stack.addWidget(self.image_scroll_area) # index 2
        self.preview_stack.addWidget(self.video_preview_widget)# index 3
        self.preview_stack.addWidget(self.unsupported_label) # index 4
        self.preview_stack.addWidget(self.loading_label)     # index 5

        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.right_widget)
        self.splitter.setSizes([400, 400]) # Başlangıç boyutları

        # Medya oynatıcıyı başlat
        self._init_media_player()

        # Başlangıçta butonları devre dışı bırak
        self.update_button_states()

    def _init_media_player(self):
        self._media_player = QMediaPlayer()
        self._media_player.setVideoOutput(self.video_preview_widget)
        self._media_player.errorOccurred.connect(self.handle_media_error)

    def load_files(self, vault_name: str):
        self._current_vault_name = vault_name
        self.refresh_file_list()
        self.preview_stack.setCurrentIndex(0) # Placeholder göster

    def refresh_file_list(self):
        if not self._current_vault_name:
            return
        self.file_table.setRowCount(0) # Listeyi temizle
        self.file_table.clearContents()
        try:
            files = vault_manager.list_files_in_vault(self._current_vault_name)
            self.file_table.setRowCount(len(files))
            for row, file_info in enumerate(files):
                file_id = file_info['id']
                item_name = QTableWidgetItem(file_info['original_filename'])
                item_name.setData(Qt.ItemDataRole.UserRole, file_id) # ID'yi sakla

                item_type = QTableWidgetItem(file_info.get('file_type', 'Bilinmiyor'))
                item_size = QTableWidgetItem(str(file_info.get('size_bytes', '')))
                # Tarihi daha okunabilir formatta gösterelim
                mod_time = file_info.get('modified_at')
                mod_time_str = mod_time.strftime("%Y-%m-%d %H:%M:%S") if mod_time else ""
                item_modified = QTableWidgetItem(mod_time_str)

                self.file_table.setItem(row, 0, item_name)
                self.file_table.setItem(row, 1, item_type)
                self.file_table.setItem(row, 2, item_size)
                self.file_table.setItem(row, 3, item_modified)
        except Exception as e:
             print(f"HATA: Dosya listesi yüklenemedi ({self._current_vault_name}): {e}")
             # Kullanıcıya hata mesajı gösterilebilir
             QMessageBox.warning(self, "Liste Hatası", f"Dosya listesi yüklenirken bir hata oluştu:\n{e}")
        self.update_button_states()

    def get_selected_file_id(self) -> Optional[str]:
        selected_items = self.file_table.selectedItems()
        if selected_items:
            # İlk sütundaki item'ın UserRole'undan ID'yi al
            return selected_items[0].data(Qt.ItemDataRole.UserRole)
        return None

    def on_file_selection_changed(self):
        self.update_button_states()
        # Seçim değiştiğinde önizlemeyi temizle veya yenile?
        # Şimdilik temizleyelim, sadece view butonuna basınca yüklensin.
        self.clear_preview()

    def update_button_states(self):
        has_selection = self.get_selected_file_id() is not None
        self.view_button.setEnabled(has_selection)
        self.save_as_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def clear_preview(self):
        # Medya oynatıcıyı durdur ve kaynağı temizle
        if self._media_player:
            self._media_player.stop()
            self._media_player.setSource(QUrl())
        # Geçici dosyayı sil
        self._delete_temp_file()
        # Önizleme alanlarını temizle
        self.text_preview.clear()
        self.image_preview_label.clear()
        self.preview_stack.setCurrentIndex(0) # Placeholder

    def on_view_clicked(self):
        file_id = self.get_selected_file_id()
        if file_id:
            self.request_view_file.emit(file_id)

    def on_save_as_clicked(self):
        file_id = self.get_selected_file_id()
        if file_id:
            self.request_save_as.emit(file_id)

    def on_delete_clicked(self):
        file_id = self.get_selected_file_id()
        if file_id:
            reply = QMessageBox.question(self,
                                         "Dosyayı Sil",
                                         f"'{self.file_table.selectedItems()[0].text()}' dosyasını kalıcı olarak silmek istediğinizden emin misiniz?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.request_delete_file.emit(file_id)

    def on_item_double_clicked(self, item: QTableWidgetItem):
         # Satırın ilk hücresindeki item'dan ID almamız lazım
         id_item = self.file_table.item(item.row(), 0)
         if id_item:
             file_id = id_item.data(Qt.ItemDataRole.UserRole)
             if file_id:
                 self.request_view_file.emit(file_id)

    def show_preview(self, file_id: str, decrypted_data: bytes):
        """MainWindow'dan gelen çözülmüş veri ile önizlemeyi gösterir."""
        self.preview_stack.setCurrentIndex(5) # Loading göster
        QApplication.processEvents() # Arayüzün güncellenmesini sağla

        metadata = database_manager.get_file_metadata(self._current_vault_name, file_id)
        if not metadata:
            self.preview_stack.setCurrentIndex(4) # Unsupported (hata durumu)
            return

        file_type = metadata.get('file_type', '').lower()

        # Medya oynatıcıyı durdur ve önceki geçici dosyayı sil
        if self._media_player: self._media_player.stop()
        self._delete_temp_file()

        try:
            if file_type in self.TEXT_EXTENSIONS:
                # Kodlamayı tahmin etmeye çalış (basitçe utf-8 dene)
                try:
                    text = decrypted_data.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                       # Windows varsayılanı
                       text = decrypted_data.decode('cp1254') # Türkçe için
                    except UnicodeDecodeError:
                       text = decrypted_data.decode('latin-1', errors='replace') # Son çare
                self.text_preview.setPlainText(text)
                self.preview_stack.setCurrentIndex(1)
            elif file_type in self.IMAGE_EXTENSIONS:
                pixmap = QPixmap()
                if pixmap.loadFromData(decrypted_data):
                    # ---- Ölçekleme Mantığı ----
                    # ScrollArea'nın viewport boyutunu al
                    viewport_size = self.image_scroll_area.viewport().size()
                    # Pixmap'i viewport'a sığacak şekilde ölçekle (en/boy oranını koru)
                    scaled_pixmap = pixmap.scaled(viewport_size,
                                                  Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)
                    # Ölçeklenmiş pixmap'i QLabel'e yükle
                    self.image_preview_label.setPixmap(scaled_pixmap)
                    # ---- Ölçekleme Sonu ----
                    self.preview_stack.setCurrentIndex(2)
                else:
                    print("HATA: Resim verisi QPixmap ile yüklenemedi.")
                    self.preview_stack.setCurrentIndex(4) # Unsupported
            elif file_type in self.VIDEO_EXTENSIONS:
                # Geçici dosyaya yaz
                fd, temp_path_str = tempfile.mkstemp(suffix=file_type)
                self._temp_file_path = Path(temp_path_str)
                os.write(fd, decrypted_data)
                os.close(fd)
                print(f"Video geçici dosyaya yazıldı: {self._temp_file_path}")

                self._media_player.setSource(QUrl.fromLocalFile(str(self._temp_file_path)))
                self.preview_stack.setCurrentIndex(3) # Video widget
                self._media_player.play()
            else:
                self.preview_stack.setCurrentIndex(4) # Unsupported

        except Exception as e:
            print(f"HATA: Önizleme oluşturulurken hata oluştu ({file_type}): {e}")
            self.preview_stack.setCurrentIndex(4) # Unsupported
            # Kullanıcıya hata göster
            QMessageBox.warning(self, "Önizleme Hatası", f"Dosya önizlemesi oluşturulurken bir hata oluştu:\n{e}")

    def handle_media_error(self, error, error_string):
        print(f"Medya Hatası: {error} - {error_string}")
        QMessageBox.warning(self, "Video Oynatma Hatası",
                          f"Video oynatılamadı:\n{error_string}\nSisteminizde gerekli codec'lerin kurulu olduğundan emin olun.")
        self.preview_stack.setCurrentIndex(4) # Unsupported göster
        self._delete_temp_file() # Hata durumunda geçici dosyayı sil

    def _delete_temp_file(self):
        """Varsa geçici video dosyasını siler."""
        if self._temp_file_path and self._temp_file_path.exists():
            try:
                self._temp_file_path.unlink()
                print(f"Geçici dosya silindi: {self._temp_file_path}")
                self._temp_file_path = None
            except OSError as e:
                print(f"HATA: Geçici dosya silinemedi: {self._temp_file_path}\n{e}")

    def closeEvent(self, event):
        """Widget kapanırken geçici dosyayı sil."""
        self._delete_temp_file()
        super().closeEvent(event) 