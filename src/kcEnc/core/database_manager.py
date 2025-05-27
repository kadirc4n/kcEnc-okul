import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime
import uuid

from ..utils.file_utils import get_vault_path

METADATA_DB_FILE = "metadata.db"

def get_db_path(vault_name: str) -> Path:
    """Belirli bir kasanın metadata.db dosyasının yolunu döndürür."""
    return get_vault_path(vault_name) / METADATA_DB_FILE

def db_connect(vault_name: str) -> sqlite3.Connection:
    """Veritabanı bağlantısı kurar ve cursor döndürür."""
    db_path = get_db_path(vault_name)
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    # Sözlük olarak sonuçları almak için row_factory ayarla
    conn.row_factory = sqlite3.Row
    return conn


SQL_CREATE_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,          -- UUID for the encrypted file
    original_filename TEXT NOT NULL, -- Original name of the file
    encrypted_filename TEXT NOT NULL UNIQUE, -- Name of the file stored in `files/` (e.g., UUID.enc)
    iv BLOB NOT NULL,             -- Initialization Vector used for AES-GCM (12 bytes)
    file_type TEXT,               -- Original file extension (e.g., '.jpg', '.txt', '.mp4') for preview hint
    size_bytes INTEGER,           -- Original file size
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SQL_CREATE_TRIGGER_UPDATE_MODIFIED_AT = """
CREATE TRIGGER IF NOT EXISTS update_files_modified_at
AFTER UPDATE ON files
FOR EACH ROW
BEGIN
    UPDATE files SET modified_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
"""

def initialize_database(vault_name: str):
    """Veritabanını ve gerekli tabloları/trigger'ları oluşturur."""
    conn = None
    cursor = None # Cursor'ı başlat
    try:
        conn = db_connect(vault_name)
        cursor = conn.cursor()
        cursor.execute(SQL_CREATE_FILES_TABLE)
        cursor.execute(SQL_CREATE_TRIGGER_UPDATE_MODIFIED_AT)
        conn.commit()
        print(f"'{vault_name}' için veritabanı komutları çalıştırıldı ve commit edildi.")

        # ---- Doğrulama Adımı ----
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files';")
        if cursor.fetchone():
            print(f"DOĞRULAMA BAŞARILI: '{vault_name}' veritabanında 'files' tablosu bulundu.")
        else:
            print(f"DOĞRULAMA BAŞARISIZ: '{vault_name}' veritabanında 'files' tablosu commit sonrası BULUNAMADI!")
            # Hata fırlatarak işlemin başarısız olduğunu belirt
            raise sqlite3.OperationalError(f"'{vault_name}' DB commit sonrası tablo doğrulanamadı.")
        # ---- Doğrulama Sonu ----

    except sqlite3.Error as e:
        print(f"HATA: '{vault_name}' için veritabanı başlatılamadı: {e}")
        # Bu hatayı daha yukarıya iletmek gerekebilir
        raise
    finally:
        # Cursor'ı kapatmaya gerek yok, connection kapanınca kapanır.
        if conn:
            conn.close()

# --- Adım 4 ve 5 için Fonksiyonlar ---

def add_file_record(vault_name: str, file_info: Dict[str, Any]) -> Optional[str]:
    """Dosya meta verisini veritabanına ekler. Başarılı olursa ID döndürür."""
    file_id = str(uuid.uuid4())
    sql = """INSERT INTO files (id, original_filename, encrypted_filename, iv, file_type, size_bytes)
             VALUES (?, ?, ?, ?, ?, ?)"""
    try:
        conn = db_connect(vault_name)
        cursor = conn.cursor()
        cursor.execute(sql, (
            file_id,
            file_info['original_filename'],
            file_info['encrypted_filename'],
            file_info['iv'],
            file_info.get('file_type'), # None olabilir
            file_info.get('size_bytes') # None olabilir
        ))
        conn.commit()
        print(f"Dosya kaydı eklendi: {file_info['original_filename']} (ID: {file_id})")
        return file_id
    except sqlite3.Error as e:
        print(f"HATA: '{vault_name}' veritabanına dosya kaydı eklenemedi: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_all_files(vault_name: str) -> List[Dict[str, Any]]:
    """Bir kasadaki tüm dosyaların meta verilerini listeler."""
    sql = "SELECT id, original_filename, file_type, size_bytes, created_at, modified_at FROM files ORDER BY original_filename COLLATE NOCASE" 
    files = []
    try:
        conn = db_connect(vault_name)
        cursor = conn.cursor()
        cursor.execute(sql)
        files = [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"HATA: '{vault_name}' veritabanından dosya listesi alınamadı: {e}")
    finally:
        if conn:
            conn.close()
    return files

def get_file_metadata(vault_name: str, file_id: str) -> Optional[Dict[str, Any]]:
    """Belirli bir dosyanın meta verilerini ID ile alır."""
    sql = "SELECT id, original_filename, encrypted_filename, iv, file_type, size_bytes FROM files WHERE id = ?"
    metadata = None
    try:
        conn = db_connect(vault_name)
        cursor = conn.cursor()
        cursor.execute(sql, (file_id,))
        row = cursor.fetchone()
        if row:
            metadata = dict(row)
    except sqlite3.Error as e:
        print(f"HATA: '{vault_name}' veritabanından meta veri alınamadı (ID: {file_id}): {e}")
    finally:
        if conn:
            conn.close()
    return metadata

def delete_file_record(vault_name: str, file_id: str) -> bool:
    """Dosya meta verisini veritabanından siler."""
    sql = "DELETE FROM files WHERE id = ?"
    success = False
    try:
        conn = db_connect(vault_name)
        cursor = conn.cursor()
        cursor.execute(sql, (file_id,))
        conn.commit()
        success = cursor.rowcount > 0 # Silme işlemi başarılı oldu mu?
        if success:
            print(f"Dosya kaydı silindi (ID: {file_id})")
        else:
             print(f"Uyarı: Silinecek dosya kaydı bulunamadı (ID: {file_id})")
    except sqlite3.Error as e:
        print(f"HATA: '{vault_name}' veritabanından dosya kaydı silinemedi (ID: {file_id}): {e}")
    finally:
        if conn:
            conn.close()
    return success 