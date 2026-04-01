# backend/utils/crypto.py
from cryptography.fernet import Fernet
from backend.core.config import settings

def encrypt_password(password: str) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    return cipher.encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    return cipher.decrypt(encrypted.encode()).decode()