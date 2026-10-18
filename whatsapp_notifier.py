"""Cliente mínimo y fail-closed para el sidecar privado de WhatsApp Web."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

import config


def normalize_phone(value: str) -> str:
    """Devuelve E.164 sin ``+`` para el ``chat_id`` del sidecar."""
    raw = str(value or "").strip()
    if not raw.startswith("+"):
        raise ValueError("Usá el teléfono en formato internacional, por ejemplo +54911...")
    digits = re.sub(r"\D", "", raw)
    if not re.fullmatch(r"[1-9]\d{7,14}", digits):
        raise ValueError("Teléfono de WhatsApp inválido")
    return digits


def _fernet():
    try:
        from cryptography.fernet import Fernet
        return Fernet(config.PROFILE_ENCRYPTION_KEY.encode("ascii"))
    except Exception:
        return None


def encrypt_phone(value: str) -> str:
    cipher = _fernet()
    if not cipher:
        raise ValueError("cifrado de perfil no configurado")
    return cipher.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_phone(value: str | None) -> str | None:
    cipher = _fernet()
    if not value or not cipher:
        return None
    try:
        return cipher.decrypt(value.encode("ascii")).decode("utf-8")
    except Exception:
        return None


class WhatsAppNotifier:
    def __init__(self):
        self.url = config.WHATSAPP_SIDECAR_URL
        self.secret = config.WHATSAPP_SIDECAR_SECRET

    def ready(self) -> bool:
        parsed = urlparse(self.url)
        return bool(_fernet() and self.secret and parsed.scheme == "https" and parsed.netloc and not parsed.username)

    def send_message(self, phone: str, text: str) -> bool:
        if not self.ready():
            print("⚠️ WhatsApp no configurado: faltan URL HTTPS o secret")
            return False
        try:
            chat_id = normalize_phone(phone)
        except ValueError:
            return False
        # WhatsApp Web no interpreta HTML de Telegram; entregamos texto plano.
        plain = re.sub(r"<[^>]+>", "", str(text or "")).strip()
        if not plain or len(plain) > 3900:
            return False
        try:
            response = requests.post(
                f"{self.url}/send",
                json={"chat_id": chat_id, "chat_type": "private", "text": plain},
                headers={"Authorization": f"Bearer {self.secret}", "Content-Type": "application/json"},
                timeout=(5, 15),
            )
            if not response.ok:
                print(f"⚠️ WhatsApp sidecar respondió {response.status_code}")
                return False
            return True
        except requests.RequestException as error:
            print(f"⚠️ WhatsApp sidecar no disponible: {type(error).__name__}")
            return False
