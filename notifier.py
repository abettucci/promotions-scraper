"""
Notificador de promociones vía Telegram Bot.

Uso standalone:
    python notifier.py                  # Digest de hoy de todos los supers
    python notifier.py --supermarket carrefour   # Solo Carrefour
    python notifier.py --all            # Todas las promos activas (no solo hoy)

Se puede llamar directamente desde scraper.py con --notify.
"""
import requests
import sqlite3
import argparse
import unicodedata
from datetime import datetime
from pathlib import Path
import config

# ── Emojis por banco/billetera ────────────────────────────────────────────────
ENTITY_EMOJI = {
    'banco nación': '🏦',
    'banco galicia': '🟣',
    'santander': '🔴',
    'bbva': '🔵',
    'macro': '🟡',
    'banco patagonia': '🏔️',
    'club la nación': '📰',
    'carrefour banco': '🔵',
    'mercado pago': '💙',
    'modo': '📱',
    'naranja x': '🟠',
    'cuenta dni': '🪪',
    'ualá': '💜',
    'personal pay': '📲',
}

SUPERMARKET_EMOJI = {
    'carrefour': '🛒',
    'supermercados día': '🛍️',
    'coto digital': '🛒',
    'jumbo (cencosud)': '🦁',
    'más online (changoMás)': '🛒',
}

# Días en español → número de semana (lunes=0)
DAY_MAP = {
    'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
    'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6,
}
DAY_NAMES_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def _today_name() -> str:
    """Devuelve el nombre del día de hoy en español."""
    return DAY_NAMES_ES[datetime.now().weekday()]


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def _promo_is_today(valid_days: str) -> bool:
    """True si la promo aplica hoy según su campo valid_days.
    Normaliza acentos: scrapers guardan "Miercoles"/"Sabado" sin tilde.
    """
    if not valid_days:
        return True  # sin restricción de día → siempre aplica
    vd = _strip_accents(valid_days).lower()
    if 'todos los dias' in vd or 'diario' in vd:
        return True
    today = _strip_accents(_today_name()).lower()
    return today in vd


def _entity_emoji(bank: str, wallet: str) -> str:
    combined = (bank or wallet or '').lower()
    for key, emoji in ENTITY_EMOJI.items():
        if key in combined:
            return emoji
    return '💳'


def _format_promo(promo: dict) -> str:
    """Formatea una promoción en una línea compacta."""
    emoji = _entity_emoji(promo.get('bank'), promo.get('wallet'))
    entity = promo.get('bank') or promo.get('wallet') or 'N/A'
    discount = promo.get('discount') or ''

    parts = [f"{emoji} *{discount}* — {entity}"]

    details = []
    if promo.get('valid_days'):
        details.append(f"📅 {promo['valid_days']}")
    if promo.get('store_types'):
        details.append(f"🏪 {promo['store_types']}")
    if promo.get('tope'):
        details.append(f"⚠️ Tope {promo['tope']}")
    if promo.get('min_purchase'):
        details.append(f"🛍️ Mínimo {promo['min_purchase']}")

    if details:
        parts.append('   ' + ' | '.join(details))

    return '\n'.join(parts)


def _build_supermarket_message(supermarket_name: str, promotions: list, today_only: bool) -> str:
    """
    Construye el mensaje Markdown para un supermercado.
    Retorna string vacío si no hay promos para enviar.
    """
    if today_only:
        promos = [p for p in promotions if _promo_is_today(p.get('valid_days', ''))]
    else:
        promos = promotions

    if not promos:
        return ''

    today_str = datetime.now().strftime('%A %d %b').capitalize()
    sm_emoji = SUPERMARKET_EMOJI.get(supermarket_name.lower(), '🛒')

    lines = [
        f"{sm_emoji} *{supermarket_name}* — {today_str}",
        '─' * 32,
    ]

    for promo in promos:
        lines.append(_format_promo(promo))
        lines.append('')  # separador

    lines.append(f"_Total: {len(promos)} promoci{'ó' if len(promos)==1 else 'o'}nes{'  de hoy' if today_only else ' activas'}_")

    return '\n'.join(lines)


def _split_message(text: str, limit: int = 4000) -> list:
    """Divide un mensaje largo en chunks respetando el límite de Telegram."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    return chunks


class TelegramNotifier:
    """Envía notificaciones de promociones via Telegram Bot API."""

    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self._base_url = f"https://api.telegram.org/bot{self.token}"

    def _enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, text: str) -> bool:
        """Envía un mensaje (con split automático si supera 4000 chars)."""
        if not self._enabled():
            print("⚠️  Telegram no configurado (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
            return False

        ok = True
        for chunk in _split_message(text):
            try:
                resp = requests.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        'chat_id': self.chat_id,
                        'text': chunk,
                        'parse_mode': 'Markdown',
                        'disable_web_page_preview': True,
                    },
                    timeout=15,
                )
                if not resp.ok:
                    print(f"❌ Telegram error {resp.status_code}: {resp.text[:200]}")
                    ok = False
            except requests.RequestException as e:
                print(f"❌ Telegram request error: {e}")
                ok = False
        return ok

    def send_promotions(self, db_path: Path = None, supermarket_filter: str = None, today_only: bool = True):
        """
        Lee la DB y envía un digest por cada supermercado.

        Args:
            db_path: Ruta al archivo SQLite (default: config.DATABASE_PATH)
            supermarket_filter: Si se especifica, solo ese supermercado
            today_only: True → solo promos válidas hoy; False → todas las activas
        """
        if not self._enabled():
            print("⚠️  Telegram no configurado — saltando notificación")
            return

        db_path = db_path or config.DATABASE_PATH
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        try:
            query = """
                SELECT p.*, s.name as supermarket_name
                FROM promotions p
                JOIN supermarkets s ON p.supermarket_id = s.id
                WHERE p.is_active = 1
            """
            params = []
            if supermarket_filter:
                query += " AND LOWER(s.name) LIKE ?"
                params.append(f"%{supermarket_filter.lower()}%")

            query += " ORDER BY s.name, p.discount DESC"

            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        if not rows:
            self.send_message("ℹ️ No hay promociones activas en la base de datos.")
            return

        # Agrupar por supermercado
        by_super: dict = {}
        for row in rows:
            name = row['supermarket_name']
            by_super.setdefault(name, []).append(dict(row))

        sent_count = 0
        for super_name, promos in by_super.items():
            msg = _build_supermarket_message(super_name, promos, today_only)
            if msg:
                print(f"   📤 Enviando digest de {super_name} ({len([p for p in promos if not today_only or _promo_is_today(p.get('valid_days',''))])} promos)...")
                self.send_message(msg)
                sent_count += 1

        if sent_count == 0:
            day = _today_name()
            self.send_message(f"ℹ️ No hay promociones activas para el día de hoy ({day}).")

    def send_scrape_summary(self, stats: dict):
        """Envía un resumen rápido al finalizar el scraping completo."""
        if not self._enabled():
            return

        elapsed = stats.get('elapsed_seconds', 0)
        lines = [
            "✅ *Scraping completado*",
            f"🏪 Exitosos: {stats.get('successful_scrapes', 0)} | ❌ Fallidos: {stats.get('failed_scrapes', 0)}",
            f"🎯 Total promos: {stats.get('total_promotions', 0)}",
            f"⏱️ Tiempo: {elapsed:.0f}s",
        ]
        self.send_message('\n'.join(lines))


    def send_user_digests(self):
        """
        Envía a cada usuario registrado (con Telegram configurado) las promociones
        que aplican para su stack de tarjetas/billeteras en el día de hoy.
        """
        from database import UserDatabase
        db = UserDatabase()
        users = db.get_users_for_notification()

        if not users:
            print("ℹ️  No hay usuarios con Telegram configurado y notify_daily=True")
            return

        today = _today_name()
        print(f"📤 Enviando digest personalizado a {len(users)} usuario(s) — {today}...")

        for user in users:
            chat_id = user.get("telegram_chat_id")
            if not chat_id:
                continue

            methods = db.get_user_payment_methods(user["id"])
            if not methods:
                continue  # sin métodos de pago configurados, no enviamos

            promos = db.get_promotions_for_user(user["id"], today_only=True)
            if not promos:
                self.send_message_to(chat_id, (
                    f"👋 ¡Buen {today}!\n\n"
                    "ℹ️ Hoy no hay promociones activas para tus tarjetas y billeteras."
                ))
                continue

            # Agrupar por supermercado
            by_super: dict = {}
            for p in promos:
                by_super.setdefault(p["supermarket_name"], []).append(p)

            # Header personalizado
            method_names = ", ".join(m["name"] for m in methods[:4])
            if len(methods) > 4:
                method_names += f" +{len(methods) - 4} más"

            header = (
                f"👋 ¡Buen {today}!\n"
                f"🎯 *Tus promos de hoy* ({method_names})\n"
                f"{'─' * 32}\n"
            )
            self.send_message_to(chat_id, header)

            for super_name, super_promos in by_super.items():
                sm_emoji = SUPERMARKET_EMOJI.get(super_name.lower(), '🛒')
                lines = [f"{sm_emoji} *{super_name}*"]
                for p in super_promos:
                    lines.append(_format_promo(p))
                    lines.append("")
                lines.append(f"_Total: {len(super_promos)} promoci{'ó' if len(super_promos)==1 else 'o'}nes_")
                self.send_message_to(chat_id, "\n".join(lines))

            print(f"   ✅ Enviado a {user['email']} ({len(promos)} promos)")

    def send_message_to(self, chat_id: str, text: str,
                         reply_markup: dict = None,
                         parse_mode: str = "Markdown") -> bool:
        """Envía un mensaje a un chat_id específico.

        reply_markup: dict opcional con inline_keyboard (formato Telegram).
        El reply_markup solo se adjunta al primer chunk si hay split.
        """
        if not self.token:
            print("⚠️  TELEGRAM_BOT_TOKEN no configurado")
            return False
        ok = True
        chunks = _split_message(text)
        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            if reply_markup is not None and i == len(chunks) - 1:
                payload["reply_markup"] = reply_markup
            try:
                resp = requests.post(
                    f"{self._base_url}/sendMessage",
                    json=payload,
                    timeout=15,
                )
                if not resp.ok:
                    print(f"❌ Telegram error {resp.status_code}: {resp.text[:200]}")
                    ok = False
            except requests.RequestException as e:
                print(f"❌ Telegram request error: {e}")
                ok = False
        return ok

    def answer_callback_query(self, callback_id: str, text: str = "") -> bool:
        """Responde a una callback_query (cierra el spinner del botón)."""
        if not self.token:
            return False
        try:
            requests.post(
                f"{self._base_url}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text},
                timeout=10,
            )
            return True
        except requests.RequestException:
            return False

    def edit_message_text(self, chat_id: str, message_id: int, text: str,
                           reply_markup: dict = None,
                           parse_mode: str = "Markdown") -> bool:
        """Edita un mensaje existente (útil para paginación in-place)."""
        if not self.token:
            return False
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        try:
            resp = requests.post(
                f"{self._base_url}/editMessageText",
                json=payload,
                timeout=15,
            )
            return resp.ok
        except requests.RequestException as e:
            print(f"❌ Telegram edit error: {e}")
            return False


# ── CLI standalone ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Notificador Telegram de promociones')
    parser.add_argument('--supermarket', '-s', help='Filtrar por supermercado', default=None)
    parser.add_argument('--all', action='store_true', help='Enviar todas las promos activas (no solo hoy)')
    parser.add_argument('--users', action='store_true', help='Enviar digest personalizado a cada usuario registrado')
    parser.add_argument('--token', help='Telegram bot token (override .env)', default=None)
    parser.add_argument('--chat-id', help='Telegram chat ID (override .env)', default=None)
    args = parser.parse_args()

    notifier = TelegramNotifier(token=args.token, chat_id=args.chat_id)

    if args.users:
        notifier.send_user_digests()
    else:
        today_only = not args.all
        print(f"📤 Enviando {'todas las promos activas' if not today_only else f'promos de hoy ({_today_name()})'}...")
        notifier.send_promotions(supermarket_filter=args.supermarket, today_only=today_only)

    print("✅ Listo")


if __name__ == '__main__':
    main()
