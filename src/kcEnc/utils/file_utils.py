import os
from pathlib import Path

APP_NAME = "kcEnc"
VAULTS_DIR_NAME = "Vaults"

def get_app_support_dir() -> Path:
    """macOS için uygulama destek dizinini döndürür."""
    return Path.home() / "Library" / "Application Support" / APP_NAME

def get_vaults_dir() -> Path:
    """Kasaların saklanacağı ana dizini döndürür."""
    return get_app_support_dir() / VAULTS_DIR_NAME

def get_vault_path(vault_name: str) -> Path:
    """Belirli bir kasanın tam yolunu döndürür."""
    return get_vaults_dir() / vault_name

def ensure_vaults_dir_exists():
    """Kasa dizininin var olduğundan emin olur, yoksa oluşturur."""
    vaults_dir = get_vaults_dir()
    try:
        vaults_dir.mkdir(parents=True, exist_ok=True)
        print(f"Kasa dizini kontrol edildi/oluşturuldu: {vaults_dir}") # Loglama için
    except OSError as e:
        print(f"HATA: Kasa dizini oluşturulamadı: {vaults_dir}\n{e}")
        # Burada daha robust bir hata yönetimi yapılabilir (örn. kullanıcıya bildirim)
        raise # Şimdilik hatayı tekrar yükseltelim

# Ana uygulama başlangıcında çağrılabilir
# if __name__ == "__main__":
#     ensure_vaults_dir_exists() 