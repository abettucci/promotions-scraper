"""
Cliente HTTP minimalista para Resend.

No usa el SDK oficial — solo POST a la API REST. Mantiene la dep liviana.

Env vars requeridas:
    RESEND_API_KEY      — desde resend.com → API Keys
    EMAIL_FROM          — remitente verificado (ej: noreply@promoar.app)
    FRONTEND_RESET_URL  — URL base del frontend (ej: https://promoar.app)
"""
import os
import requests
from typing import Optional

import config


def _api_key() -> Optional[str]:
    return os.getenv("RESEND_API_KEY", "")


def _from_email() -> str:
    return os.getenv("EMAIL_FROM", "noreply@promoar.app")


def is_configured() -> bool:
    return bool(_api_key())


def send_email(to: str, subject: str, html: str, text: str = "") -> bool:
    """Envía un email vía Resend. Retorna True si Resend acepta el envío."""
    api_key = _api_key()
    if not api_key:
        print("⚠️  RESEND_API_KEY no configurado — email no enviado")
        return False

    payload = {
        "from": _from_email(),
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if not resp.ok:
            print(f"❌ Resend error {resp.status_code}: {resp.text[:300]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"❌ Resend request error: {e}")
        return False


# ── Templates ─────────────────────────────────────────────────────────────────
def send_password_reset_email(to: str, reset_url: str) -> bool:
    subject = "Recuperá tu contraseña — PromoAR"
    html = f"""
    <!doctype html>
    <html>
      <body style="font-family: -apple-system, system-ui, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; color: #0f172a;">
        <h1 style="font-size: 22px; margin: 0 0 16px;">🔑 Recuperá tu contraseña</h1>
        <p>Recibimos un pedido para resetear la contraseña de tu cuenta en PromoAR.</p>
        <p>Hacé click en el siguiente botón para crear una nueva contraseña. El link expira en <strong>1 hora</strong>.</p>
        <p style="margin: 32px 0;">
          <a href="{reset_url}"
             style="display: inline-block; background: #0f172a; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
            Crear nueva contraseña
          </a>
        </p>
        <p style="color: #64748b; font-size: 14px;">
          Si no pediste resetear tu contraseña, ignorá este mail. Tu cuenta sigue segura.
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 32px 0;"/>
        <p style="color: #94a3b8; font-size: 12px;">
          ¿No funciona el botón? Copiá y pegá esta URL en tu navegador:<br/>
          <span style="word-break: break-all;">{reset_url}</span>
        </p>
      </body>
    </html>
    """
    text = (
        "Recuperá tu contraseña — PromoAR\n\n"
        "Recibimos un pedido para resetear la contraseña de tu cuenta.\n"
        f"Abrí este link para crear una nueva (expira en 1 hora):\n\n{reset_url}\n\n"
        "Si no pediste esto, ignorá este mail."
    )
    return send_email(to, subject, html, text)
