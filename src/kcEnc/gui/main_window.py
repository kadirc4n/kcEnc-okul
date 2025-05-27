import sys
import os # path işlemleri için
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QStackedWidget, QMessageBox,
    QFileDialog, QLabel, QToolBar # QToolBar eklendi
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer # QTimer importu eksikti
from PyQt6.QtGui import QAction, QIcon # QAction ve QIcon eklendi

# Yerel modülleri import et
from .widgets.vault_list_widget import VaultListWidget
from .widgets.unlocked_vault_widget import UnlockedVaultWidget
from .dialogs.login_dialog import LoginDialog
from .dialogs.create_vault_dialog import CreateVaultDialog
from ..core import vault_manager
from ..utils.file_utils import ensure_vaults_dir_exists

class MainWindow(QMainWindow):
    # Kasa kilidi açıldığında veya kilitlendiğinde sinyal gönderebiliriz
    vault_state_changed = pyqtSignal(bool, str) # is_unlocked, vault_name

    def __init__(self):
        super().__init__()
        self.setWindowTitle("kcEnc - Kasa Yöneticisi")
        self.setGeometry(100, 100, 850, 650) # Boyutu biraz büyütelim

        self._active_vault_name: str | None = None
        self._vault_key: bytes | None = None

        # Eylemleri (Actions) oluştur
        self._create_actions()
        # Araç çubuğunu oluştur
        self._create_toolbars()

        # Ana widget ve layout
        self.central_widget = QWidget()
        self.main_layout = QVBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        # Farklı görünümler için Stacked Widget
        self.view_stack = QStackedWidget()
        self.main_layout.addWidget(self.view_stack)

        # Görünümleri oluştur
        self.vault_list_view = VaultListWidget()
        self.unlocked_vault_view = UnlockedVaultWidget()

        # Görünümleri stack'e ekle
        self.view_stack.addWidget(self.vault_list_view)       # index 0
        self.view_stack.addWidget(self.unlocked_vault_view)   # index 1

        # Başlangıçta kasa listesini göster
        self.show_vault_list_view()

        # Sinyal bağlantıları
        self.vault_list_view.request_unlock.connect(self.prompt_unlock_vault)
        self.vault_list_view.request_create.connect(self.prompt_create_vault)
        self.unlocked_vault_view.request_lock.connect(self.lock_vault)
        # Dosya işlemleri için ana penceredeki metodları bağlıyoruz
        self.unlocked_vault_view.request_add_file.connect(self.add_file)
        self.unlocked_vault_view.request_view_file.connect(self.view_file)
        self.unlocked_vault_view.request_save_as.connect(self.save_file_as)
        self.unlocked_vault_view.request_delete_file.connect(self.delete_file)
        # Kasa durumu değiştikçe araç çubuğu eylemlerini güncelle
        self.vault_state_changed.connect(self.update_actions_state)

        # Uygulama destek dizinini kontrol et/oluştur
        try:
            ensure_vaults_dir_exists()
        except Exception as e:
            self.show_error_message("Kritik Hata", f"Uygulama destek dizini oluşturulamadı:\n{e}")
            QTimer.singleShot(0, QApplication.instance().quit) # Hata sonrası çık

    def _create_actions(self):
        # Standart ikonları kullan
        style = QApplication.style()

        self.add_file_action = QAction(style.standardIcon(style.StandardPixmap.SP_FileIcon), "&Dosya Ekle...", self)
        self.add_file_action.setShortcut("Ctrl+O")
        self.add_file_action.triggered.connect(self.add_file)

        self.lock_vault_action = QAction(style.standardIcon(style.StandardPixmap.SP_DialogResetButton), "Kasayı &Kilitle", self)
        self.lock_vault_action.setShortcut("Ctrl+L")
        self.lock_vault_action.triggered.connect(self.lock_vault)

        self.exit_action = QAction(style.standardIcon(style.StandardPixmap.SP_DialogCloseButton), "&Çıkış", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close) # closeEvent tetiklenir

    def _create_toolbars(self):
        self.fileToolBar = self.addToolBar("Dosya")
        self.fileToolBar.addAction(self.add_file_action)
        self.fileToolBar.addAction(self.lock_vault_action)
        # self.fileToolBar.addAction(self.exit_action) # Çıkış genellikle menüde olur

        # Başlangıçta durumlarını ayarla
        self.update_actions_state(False, "")

    def update_actions_state(self, is_unlocked: bool, vault_name: str):
        """Kasa durumuna göre eylemlerin etkinliğini ayarlar."""
        self.add_file_action.setEnabled(is_unlocked)
        self.lock_vault_action.setEnabled(is_unlocked)

    def show_vault_list_view(self):
        self._clear_sensitive_data() # Anahtarı temizle
        self._active_vault_name = None
        self.setWindowTitle("kcEnc - Kasa Seçimi")
        self.vault_list_view.refresh_vault_list() # Listeyi yenile
        self.view_stack.setCurrentIndex(0)
        self.vault_state_changed.emit(False, "")

    def show_unlocked_vault_view(self, vault_name: str):
        self._active_vault_name = vault_name
        self.setWindowTitle(f"kcEnc - Kasa: {vault_name}")
        self.unlocked_vault_view.load_files(vault_name)
        self.view_stack.setCurrentIndex(1)
        self.vault_state_changed.emit(True, vault_name)

    def prompt_unlock_vault(self, vault_name: str):
        dialog = LoginDialog(vault_name, self)
        if dialog.exec():
            password = dialog.get_password()
            # Anahtarı hemen burada değil, unlock_vault içinde alacağız
            self.unlock_vault(vault_name, password)

    def unlock_vault(self, vault_name: str, password: str):
        # Kilit açma işlemi biraz sürebilir, belki ileride thread kullanılabilir
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            key = vault_manager.unlock_vault(vault_name, password)
            QApplication.restoreOverrideCursor()
            if key:
                self._vault_key = key
                self.show_unlocked_vault_view(vault_name)
            else:
                self.show_error_message("Kilit Açma Hatası", "Geçersiz parola veya kasa yapılandırma hatası.")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.show_error_message("Kilit Açma Hatası", f"Beklenmedik bir hata oluştu:\n{e}")

    def prompt_create_vault(self):
        dialog = CreateVaultDialog(self)
        if dialog.exec():
            vault_name, password = dialog.get_details()
            self.create_vault(vault_name, password)

    def create_vault(self, vault_name: str, password: str):
        # İsim geçerliliğini kontrol et (örn. /, \ içermemeli)
        if not vault_name or '/' in vault_name or '\\' in vault_name:
             self.show_error_message("Geçersiz Kasa Adı", "Kasa adı boş olamaz ve / veya \\ karakterlerini içeremez.")
             return

        if not password:
            self.show_error_message("Giriş Hatası", "Parola boş olamaz.")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            success = vault_manager.create_vault(vault_name, password)
            QApplication.restoreOverrideCursor()
            if success:
                 QMessageBox.information(self, "Başarılı", f"'{vault_name}' kasası başarıyla oluşturuldu.")
                 # Kasa listesini yenilemek için tekrar vault list view'e dön
                 self.show_vault_list_view()
            else:
                 # Hata mesajını biraz daha bilgilendirici yapalım
                 error_msg = f"'{vault_name}' kasası oluşturulamadı.\nNedenler:\n- Bu isimde bir kasa zaten var olabilir.\n- Yazma izinleriyle ilgili bir sorun olabilir.\n- Beklenmedik bir hata oluşmuş olabilir.\n\nDetaylar için konsol loglarını kontrol edin."
                 self.show_error_message("Oluşturma Hatası", error_msg)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.show_error_message("Oluşturma Hatası", f"Beklenmedik bir hata oluştu:\n{e}")

    def lock_vault(self):
        print("Kasa kilitleniyor...")
        self.show_vault_list_view()

    def _clear_sensitive_data(self):
        if self._vault_key:
            try:
                # ctypes ile daha güvenli silme denenebilir ama şimdilik bu
                key_len = len(self._vault_key)
                self._vault_key = os.urandom(key_len) # Rastgele veri yaz
            except Exception:
                pass # Hata olsa bile None yap
            finally:
                 self._vault_key = None
        self._active_vault_name = None
        # Açık kasa görünümündeki önizlemeyi de temizle
        self.unlocked_vault_view.clear_preview()

    def closeEvent(self, event):
        self._clear_sensitive_data()
        # UnlockedVaultWidget'taki geçici dosyayı da silmek için
        # onun close metodu çağrılmalı, QMainWindow kapanınca child widgetlar da kapanır
        event.accept()

    # --- Dosya İşlemleri --- #
    def add_file(self):
        if not self._active_vault_name or not self._vault_key:
            # Bu durum normalde oluşmamalı çünkü action devre dışı kalır
            # Ama yine de kontrol edelim
            # self.show_error_message("Hata", "Dosya eklemek için önce bir kasa açmalısınız.")
            return

        file_dialog = QFileDialog(self, "Kasaya Eklenecek Dosyaları Seçin")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                added_count = 0
                error_files = []
                for file_path_str in selected_files:
                    file_path = Path(file_path_str)
                    try:
                        file_id = vault_manager.add_file_to_vault(self._active_vault_name, self._vault_key, file_path)
                        if file_id:
                            added_count += 1
                        else:
                            error_files.append(file_path.name)
                    except Exception as e:
                        print(f"HATA: Dosya eklenirken beklenmedik hata ({file_path.name}): {e}")
                        error_files.append(f"{file_path.name} (hata: {e})")
                QApplication.restoreOverrideCursor()

                if added_count > 0:
                    msg = f"{added_count} dosya başarıyla eklendi."
                    if error_files:
                        msg += f"\n\nAşağıdaki dosyalar eklenemedi:\n- {'\n- '.join(error_files)}"
                        QMessageBox.warning(self, "Ekleme Sonucu", msg)
                    else:
                        QMessageBox.information(self, "Ekleme Sonucu", msg)
                    self.unlocked_vault_view.refresh_file_list()
                elif error_files:
                     QMessageBox.critical(self, "Ekleme Hatası", f"Seçilen dosyalar eklenemedi:\n- {'\n- '.join(error_files)}")

    def delete_file(self, file_id: str):
        if not self._active_vault_name:
             self.show_error_message("Hata", "Aktif bir kasa yok.")
             return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # Dosya adını mesajda göstermek için meta veriyi alalım
            item_text = "Bilinmeyen Dosya"
            metadata = vault_manager.database_manager.get_file_metadata(self._active_vault_name, file_id)
            if metadata:
                item_text = metadata.get('original_filename', item_text)
            QApplication.restoreOverrideCursor() # Soru sormadan önce imleci düzelt

            reply = QMessageBox.question(self, "Dosyayı Sil",
                                         f"'{item_text}' dosyasını kalıcı olarak silmek istediğinizden emin misiniz?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                success = vault_manager.remove_file_from_vault(self._active_vault_name, file_id)
                QApplication.restoreOverrideCursor()
                if success:
                    QMessageBox.information(self, "Başarılı", "Dosya başarıyla silindi.")
                    self.unlocked_vault_view.refresh_file_list()
                    self.unlocked_vault_view.clear_preview()
                else:
                    self.show_error_message("Silme Hatası", "Dosya silinemedi. Veritabanı veya dosya sistemi hatası olabilir.")
            # else: Kullanıcı hayır dedi, bir şey yapma

        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.show_error_message("Silme Hatası", f"Dosya silinirken beklenmedik bir hata oluştu:\n{e}")

    def view_file(self, file_id: str):
        if not self._active_vault_name or not self._vault_key:
             self.show_error_message("Hata", "Aktif bir kasa ve anahtar yok.")
             return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            decrypted_data = vault_manager.get_decrypted_file_data(self._active_vault_name, self._vault_key, file_id)
            QApplication.restoreOverrideCursor()
            if decrypted_data is not None: # None gelmesi hata demek
                self.unlocked_vault_view.show_preview(file_id, decrypted_data)
            else:
                 # get_decrypted_file_data içinde hata mesajı basılmış olmalı
                 self.show_error_message("Görüntüleme Hatası", "Dosya verisi alınamadı veya şifresi çözülemedi.")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.show_error_message("Görüntüleme Hatası", f"Dosya görüntülenirken beklenmedik bir hata oluştu:\n{e}")

    def save_file_as(self, file_id: str):
        if not self._active_vault_name or not self._vault_key:
             self.show_error_message("Hata", "Aktif bir kasa ve anahtar yok.")
             return

        # Önce meta veriyi alıp orijinal dosya adını önerelim
        metadata = vault_manager.database_manager.get_file_metadata(self._active_vault_name, file_id)
        original_filename = metadata.get('original_filename', 'encrypted_file') if metadata else 'encrypted_file'

        file_dialog = QFileDialog(self, "Dosyayı Farklı Kaydet")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.selectFile(original_filename) # Öneri

        if file_dialog.exec():
            target_path_str = file_dialog.selectedFiles()[0]
            if target_path_str:
                target_path = Path(target_path_str)
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    decrypted_data = vault_manager.get_decrypted_file_data(self._active_vault_name, self._vault_key, file_id)
                    if decrypted_data is not None:
                         target_path.write_bytes(decrypted_data)
                         QApplication.restoreOverrideCursor()
                         QMessageBox.information(self, "Başarılı", f"Dosya başarıyla kaydedildi:\n{target_path}")
                    else:
                         QApplication.restoreOverrideCursor()
                         self.show_error_message("Kaydetme Hatası", "Dosya verisi alınamadı veya şifresi çözülemedi.")
                except OSError as e:
                    QApplication.restoreOverrideCursor()
                    self.show_error_message("Kaydetme Hatası", f"Dosya kaydedilirken hata oluştu:\n{e}")
                except Exception as e:
                    QApplication.restoreOverrideCursor()
                    self.show_error_message("Kaydetme Hatası", f"Dosya kaydedilirken beklenmedik bir hata oluştu:\n{e}")

    def show_error_message(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

# main.py'den çağrılacak
if __name__ == '__main__':
    # Geçici çalıştırma için (normalde main.py'den çalıştırılır)
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec()) 