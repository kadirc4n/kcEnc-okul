import os
import json
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import uuid # Encrypted filename için
import sqlite3 # create_vault içinde hata yakalama için

from ..utils.file_utils import get_vaults_dir, ensure_vaults_dir_exists, get_vault_path
from .crypto_utils import (
    generate_salt,
    derive_key,
    encrypt_check_block,
    verify_check_block,
    encrypt_data, # Adım 4 için eklendi
    decrypt_data, # Adım 5 için eklendi
    DEFAULT_ITERATIONS,
    InvalidTag
)
# Database manager import edildi
from .database_manager import (
    initialize_database,
    add_file_record,
    get_all_files,
    get_file_metadata,
    delete_file_record,
    get_db_path # Dosya silme onayı için eklendi
)

VAULT_CONFIG_FILE = "vault_config.json"
VAULT_FILES_DIR = "files"
ENCRYPTED_FILE_SUFFIX = ".enc"

def list_vaults() -> List[str]:
    """Mevcut kasaların isimlerini listeler."""
    vaults_base_dir = get_vaults_dir()
    ensure_vaults_dir_exists() # Dizin yoksa oluştur
    try:
        # Sadece içinde config dosyası olan dizinleri geçerli kasa sayalım
        valid_vaults = []
        for d in vaults_base_dir.iterdir():
            if d.is_dir() and (d / VAULT_CONFIG_FILE).is_file():
                valid_vaults.append(d.name)
        return valid_vaults
    except OSError as e:
        print(f"HATA: Kasa dizini okunamadı: {vaults_base_dir}\n{e}")
        return []

def create_vault(vault_name: str, password: str) -> bool:
    """Yeni bir kasa oluşturur."""
    if not vault_name or not password:
        print("HATA: Kasa adı ve parola boş olamaz.")
        return False

    vault_path = get_vault_path(vault_name)
    if vault_path.exists():
        print(f"HATA: '{vault_name}' isimli kasa zaten mevcut.")
        return False

    try:
        # Ana dizinleri oluştur
        files_dir = vault_path / VAULT_FILES_DIR
        files_dir.mkdir(parents=True, exist_ok=True)

        # Kriptografik işlemleri yap
        salt = generate_salt()
        key = derive_key(password, salt, DEFAULT_ITERATIONS)
        check_iv, check_ciphertext = encrypt_check_block(key)

        # Yapılandırma dosyasını oluştur
        config_data = {
            "salt": base64.b64encode(salt).decode('ascii'),
            "iterations": DEFAULT_ITERATIONS,
            "check_iv": base64.b64encode(check_iv).decode('ascii'),
            "check_ciphertext": base64.b64encode(check_ciphertext).decode('ascii')
        }
        config_path = vault_path / VAULT_CONFIG_FILE
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)

        # Veritabanını başlat (Adım 3)
        initialize_database(vault_name)

        print(f"Kasa '{vault_name}' başarıyla oluşturuldu: {vault_path}")
        del key
        return True

    except sqlite3.Error as e:
         print(f"HATA: Kasa oluşturulurken veritabanı hatası: {e}")
         # Rollback yapılabilir
         return False
    except OSError as e:
        print(f"HATA: Kasa oluşturulurken dosya sistemi hatası: {e}")
        return False
    except Exception as e:
        print(f"HATA: Kasa oluşturulurken beklenmedik hata: {e}")
        return False

def load_vault_config(vault_name: str) -> Optional[Dict]:
    """Kasa yapılandırma dosyasını yükler."""
    config_path = get_vault_path(vault_name) / VAULT_CONFIG_FILE
    if not config_path.is_file():
        # print(f"HATA: '{vault_name}' için yapılandırma dosyası bulunamadı: {config_path}")
        # Bu hata list_vaults tarafından zaten elenmiş olmalı
        return None
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        # Temel alanların varlığını kontrol et
        if not all(k in config_data for k in ["salt", "iterations", "check_iv", "check_ciphertext"]):
            print(f"HATA: '{vault_name}' yapılandırma dosyası eksik alan içeriyor.")
            return None
        return config_data
    except json.JSONDecodeError:
        print(f"HATA: '{vault_name}' yapılandırma dosyası bozuk (JSON). {config_path}")
        return None
    except Exception as e:
        print(f"HATA: '{vault_name}' yapılandırma dosyası okunurken hata: {e}")
        return None

def unlock_vault(vault_name: str, password: str) -> Optional[bytes]:
    """Kasayı açmayı dener ve başarılı olursa anahtarı döndürür."""
    config = load_vault_config(vault_name)
    if not config:
        return None # Hata mesajı load_vault_config içinde verildi

    try:
        salt = base64.b64decode(config['salt'])
        iterations = int(config['iterations'])
        check_iv = base64.b64decode(config['check_iv'])
        check_ciphertext = base64.b64decode(config['check_ciphertext'])

        key = derive_key(password, salt, iterations)

        if verify_check_block(key, check_iv, check_ciphertext):
            print(f"Kasa '{vault_name}' kilidi başarıyla açıldı.")
            return key
        else:
            print(f"HATA: '{vault_name}' için geçersiz parola.")
            del key # Başarısız denemede anahtarı temizle
            return None
    except (ValueError, TypeError, KeyError, base64.binascii.Error) as e:
        print(f"HATA: '{vault_name}' yapılandırma verisi işlenirken veya parola doğrulanırken hata: {e}")
        # Anahtar türetilmişse temizleyelim
        if 'key' in locals(): del key
        return None
    except Exception as e:
        print(f"HATA: Kasa kilidi açılırken beklenmedik hata: {e}")
        if 'key' in locals(): del key
        return None

# --- Adım 4: Dosya Ekleme --- #

def add_file_to_vault(vault_name: str, vault_key: bytes, source_file_path: Path) -> Optional[str]:
    """Bir dosyayı kasaya şifreleyerek ekler."""
    if not source_file_path.is_file():
        print(f"HATA: Kaynak dosya bulunamadı: {source_file_path}")
        return None

    try:
        # Dosya içeriğini oku
        plaintext = source_file_path.read_bytes()
        original_filename = source_file_path.name
        file_type = source_file_path.suffix
        size_bytes = source_file_path.stat().st_size

        # Şifrele
        iv, ciphertext_with_tag = encrypt_data(vault_key, plaintext)

        # Şifreli dosya adını oluştur
        encrypted_filename = str(uuid.uuid4()) + ENCRYPTED_FILE_SUFFIX
        encrypted_file_path = get_vault_path(vault_name) / VAULT_FILES_DIR / encrypted_filename

        # Şifreli dosyayı yaz
        encrypted_file_path.write_bytes(ciphertext_with_tag)

        # Meta veriyi DB'ye kaydet
        file_info = {
            "original_filename": original_filename,
            "encrypted_filename": encrypted_filename,
            "iv": iv,
            "file_type": file_type,
            "size_bytes": size_bytes
        }
        file_id = add_file_record(vault_name, file_info)

        if file_id:
            print(f"Dosya '{original_filename}' kasaya başarıyla eklendi.")
            return file_id
        else:
            # DB hatası olduysa şifreli dosyayı sil (rollback)
            print(f"HATA: Veritabanı kaydı başarısız olduğu için şifreli dosya siliniyor: {encrypted_file_path}")
            encrypted_file_path.unlink(missing_ok=True)
            return None

    except OSError as e:
        print(f"HATA: Dosya okuma/yazma hatası ('{source_file_path.name}'): {e}")
        return None
    except Exception as e:
        # crypto_utils'den InvalidTag gelmemeli ama diğer hatalar olabilir
        print(f"HATA: Dosya eklenirken beklenmedik hata ('{source_file_path.name}'): {e}")
        return None

# --- Adım 5: Dosya Listeleme, Çözme, Silme --- #

def list_files_in_vault(vault_name: str) -> List[Dict[str, Any]]:
    """Kasadaki dosyaların listesini (meta veri) döndürür."""
    return get_all_files(vault_name)

def get_decrypted_file_data(vault_name: str, vault_key: bytes, file_id: str) -> Optional[bytes]:
    """Belirli bir dosyanın şifresini çözüp içeriğini döndürür."""
    metadata = get_file_metadata(vault_name, file_id)
    if not metadata:
        print(f"HATA: Dosya meta verisi bulunamadı (ID: {file_id})")
        return None

    encrypted_filename = metadata.get('encrypted_filename')
    iv = metadata.get('iv')

    if not encrypted_filename or not iv:
        print(f"HATA: Meta veride eksik bilgi (ID: {file_id})")
        return None

    encrypted_file_path = get_vault_path(vault_name) / VAULT_FILES_DIR / encrypted_filename

    try:
        # Şifreli içeriği oku
        ciphertext_with_tag = encrypted_file_path.read_bytes()

        # Şifreyi çöz
        plaintext = decrypt_data(vault_key, iv, ciphertext_with_tag)
        print(f"Dosya '{metadata['original_filename']}' başarıyla çözüldü.")
        return plaintext

    except FileNotFoundError:
        print(f"HATA: Şifreli dosya bulunamadı: {encrypted_file_path}")
        # DB kaydını temizlemek düşünülebilir (tutarsızlık)
        return None
    except InvalidTag:
        print(f"HATA: Dosya şifre çözme hatası (InvalidTag - bozuk dosya veya yanlış anahtar?) (ID: {file_id})")
        return None
    except OSError as e:
         print(f"HATA: Şifreli dosya okunurken hata (ID: {file_id}): {e}")
         return None
    except Exception as e:
        print(f"HATA: Dosya çözülürken beklenmedik hata (ID: {file_id}): {e}")
        return None

def remove_file_from_vault(vault_name: str, file_id: str) -> bool:
    """Bir dosyayı kasadan (fiziksel dosya ve DB kaydı) siler."""
    metadata = get_file_metadata(vault_name, file_id)
    if not metadata:
        print(f"Uyarı: Silinecek dosya için meta veri bulunamadı (ID: {file_id})")
        # Belki sadece DB'den silmeyi deneyebiliriz?
        return delete_file_record(vault_name, file_id)

    encrypted_filename = metadata.get('encrypted_filename')
    if not encrypted_filename:
         print(f"HATA: Meta veride şifreli dosya adı eksik (ID: {file_id})")
         return False # Fiziksel dosyayı silemeyiz

    encrypted_file_path = get_vault_path(vault_name) / VAULT_FILES_DIR / encrypted_filename

    # Önce DB kaydını silmeyi dene (başarısız olursa fiziksel dosyayı silme)
    db_deleted = delete_file_record(vault_name, file_id)

    if db_deleted:
        try:
            encrypted_file_path.unlink(missing_ok=True) # Dosya yoksa hata verme
            print(f"Fiziksel dosya silindi: {encrypted_file_path}")
            return True
        except OSError as e:
            print(f"HATA: Fiziksel dosya silinirken hata: {encrypted_file_path}\n{e}")
            # DB kaydı silindi ama fiziksel dosya silinemedi. Bu durum loglanmalı.
            return False # Tam başarı değil
    else:
        # DB silme başarısız oldu
        return False 