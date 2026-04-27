"""
Setup / inspect del webhook de Telegram.

Uso:
    python scripts/setup_webhook.py              # Muestra estado actual
    python scripts/setup_webhook.py --set        # Setea webhook (lee config.TELEGRAM_WEBHOOK_URL)
    python scripts/setup_webhook.py --delete     # Borra el webhook
    python scripts/setup_webhook.py --url <url>  # Setea webhook con URL custom

Variables de entorno requeridas:
    TELEGRAM_BOT_TOKEN     — token del bot (de @BotFather)
    TELEGRAM_WEBHOOK_URL   — URL pública (ej: https://promoar.up.railway.app/webhook/telegram)
    TELEGRAM_WEBHOOK_SECRET (opcional) — header de seguridad
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
import config


def _api(method: str) -> str:
    if not config.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN no configurado en .env")
        sys.exit(1)
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"


def info():
    r = requests.get(_api("getWebhookInfo"), timeout=15)
    data = r.json()
    if not data.get("ok"):
        print(f"❌ Error: {data}")
        return
    info = data["result"]
    print("─" * 50)
    print(f"URL:                 {info.get('url') or '(no webhook configurado)'}")
    print(f"Pendientes:          {info.get('pending_update_count', 0)}")
    print(f"Tiene cert custom:   {info.get('has_custom_certificate')}")
    last_err = info.get("last_error_message")
    if last_err:
        print(f"Último error:        {last_err}")
        print(f"Hace:                {info.get('last_error_date')}")
    print(f"Allowed updates:     {info.get('allowed_updates') or 'all'}")
    print("─" * 50)


def set_webhook(url: str):
    payload = {
        "url": url,
        "allowed_updates": ["message", "edited_message", "callback_query"],
        "drop_pending_updates": True,
    }
    if config.TELEGRAM_WEBHOOK_SECRET:
        payload["secret_token"] = config.TELEGRAM_WEBHOOK_SECRET
    r = requests.post(_api("setWebhook"), json=payload, timeout=15)
    data = r.json()
    if data.get("ok"):
        print(f"✅ Webhook seteado: {url}")
        if config.TELEGRAM_WEBHOOK_SECRET:
            print(f"   Con secret: {'*' * 8}{config.TELEGRAM_WEBHOOK_SECRET[-4:]}")
    else:
        print(f"❌ Error: {data}")


def delete_webhook():
    r = requests.post(_api("deleteWebhook"), json={"drop_pending_updates": True}, timeout=15)
    data = r.json()
    if data.get("ok"):
        print("✅ Webhook borrado")
    else:
        print(f"❌ Error: {data}")


def main():
    parser = argparse.ArgumentParser(description="Setup webhook de Telegram")
    parser.add_argument("--set", action="store_true", help="Setea webhook con TELEGRAM_WEBHOOK_URL")
    parser.add_argument("--delete", action="store_true", help="Borra el webhook")
    parser.add_argument("--url", help="URL custom para setear")
    args = parser.parse_args()

    if args.delete:
        delete_webhook()
    elif args.set or args.url:
        url = args.url or config.TELEGRAM_WEBHOOK_URL
        if not url:
            print("❌ Necesitás setear TELEGRAM_WEBHOOK_URL en .env o pasar --url")
            sys.exit(1)
        set_webhook(url)
    else:
        info()


if __name__ == "__main__":
    main()
