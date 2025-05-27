import os
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# PRD'de belirtilen iterasyon sayısı (ayarlanabilir)
DEFAULT_ITERATIONS = 390_000
SALT_SIZE_BYTES = 16
KEY_SIZE_BYTES = 32 # AES-256 için
AES_GCM_IV_SIZE_BYTES = 12 # AES-GCM için önerilen 96 bit
AES_GCM_TAG_SIZE_BYTES = 16 # AES-GCM için 128 bit tag

CHECK_BLOCK_PLAINTEXT = b"kcEnc Vault Check"

def derive_key(password: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    """Verilen parola ve salt'tan PBKDF2HMAC kullanarak anahtar türetir."""
    if not password or not salt:
        raise ValueError("Parola ve salt boş olamaz.")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE_BYTES,
        salt=salt,
        iterations=iterations,
    )
    key = kdf.derive(password.encode('utf-8'))
    return key

def generate_salt() -> bytes:
    """Güvenli bir rastgele salt oluşturur."""
    return os.urandom(SALT_SIZE_BYTES)

def encrypt_check_block(key: bytes) -> tuple[bytes, bytes]:
    """Doğrulama bloğunu şifreler (iv, ciphertext_with_tag)."""
    aesgcm = AESGCM(key)
    iv = os.urandom(AES_GCM_IV_SIZE_BYTES)
    ciphertext_with_tag = aesgcm.encrypt(iv, CHECK_BLOCK_PLAINTEXT, None)
    return iv, ciphertext_with_tag

def verify_check_block(key: bytes, iv: bytes, ciphertext_with_tag: bytes) -> bool:
    """Şifreli doğrulama bloğunu çözerek anahtarı doğrular."""
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(iv, ciphertext_with_tag, None)
        return plaintext == CHECK_BLOCK_PLAINTEXT
    except InvalidTag:
        return False
    except Exception as e:
        # Beklenmedik diğer hataları loglamak iyi olabilir
        print(f"Check block doğrulamada beklenmedik hata: {e}")
        return False

# --- Dosya Şifreleme Fonksiyonları (Adım 4'te detaylandırılacak) ---

def encrypt_data(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """Veriyi şifreler, (iv, ciphertext_with_tag) döndürür."""
    # Bu fonksiyon Adım 4'te kullanılacak, şimdilik temel hali
    aesgcm = AESGCM(key)
    iv = os.urandom(AES_GCM_IV_SIZE_BYTES)
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext, None)
    return iv, ciphertext_with_tag

def decrypt_data(key: bytes, iv: bytes, ciphertext_with_tag: bytes) -> bytes:
    """Şifreli veriyi çözer, plaintext döndürür. Başarısız olursa InvalidTag fırlatır."""
    # Bu fonksiyon Adım 5'te kullanılacak, şimdilik temel hali
    aesgcm = AESGCM(key)
    # InvalidTag exception'ı çağıran kod tarafından yakalanmalı
    plaintext = aesgcm.decrypt(iv, ciphertext_with_tag, None)
    return plaintext 