"""
Bot handlers para el webhook de Telegram.

Cada comando se resuelve consultando directamente la DB de promociones y la de
usuarios. La interacción es two-way: comandos en texto + inline keyboards para
paginación y selección.

Comandos:
  P0: /start /ayuda /hoy /mis
  P1: /buscar /banco /super /combustible /stats
  P2: /medios /notify /hora
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Optional

import config
from database import UserDatabase
from notifier import (
    TelegramNotifier,
    _format_promo,
    _today_name,
    DAY_NAMES_ES,
)

PAGE_SIZE = 8  # promos por página (Telegram tiene 4096 chars/msg)


# ── DB helpers ────────────────────────────────────────────────────────────────
def _promos_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _query_promotions(
    *,
    today_only: bool = False,
    category: Optional[str] = None,
    bank_filter: Optional[str] = None,
    supermarket_filter: Optional[str] = None,
    search: Optional[str] = None,
    payment_methods: Optional[list[dict]] = None,
    limit: int = 200,
) -> list[dict]:
    """Single query helper para todos los comandos. Solo activas y vigentes."""
    conn = _promos_conn()
    today_iso = date.today().isoformat()
    where = [
        "p.is_active = 1",
        "(p.valid_until IS NULL OR p.valid_until = '' OR p.valid_until >= ?)",
        "(p.valid_from IS NULL OR p.valid_from = '' OR p.valid_from <= ?)",
    ]
    params: list = [today_iso, today_iso]

    if category:
        where.append("LOWER(COALESCE(s.category, 'supermarket')) = ?")
        params.append(category.lower())

    if bank_filter:
        where.append("(LOWER(p.bank) LIKE ? OR LOWER(p.wallet) LIKE ?)")
        params.extend([f"%{bank_filter.lower()}%"] * 2)

    if supermarket_filter:
        where.append("LOWER(s.name) LIKE ?")
        params.append(f"%{supermarket_filter.lower()}%")

    if search:
        where.append("(LOWER(p.title) LIKE ? OR LOWER(p.terms_raw) LIKE ?)")
        params.extend([f"%{search.lower()}%"] * 2)

    if today_only:
        today_es = _today_name()
        where.append(
            "(p.valid_days IS NULL OR p.valid_days = '' "
            "OR LOWER(p.valid_days) LIKE ? OR LOWER(p.valid_days) LIKE '%todos los d%')"
        )
        params.append(f"%{today_es}%")

    if payment_methods:
        method_clauses = []
        for m in payment_methods:
            name = (m.get("name") or "").lower()
            if name:
                method_clauses.append("LOWER(p.bank) LIKE ?")
                method_clauses.append("LOWER(p.wallet) LIKE ?")
                params.extend([f"%{name}%", f"%{name}%"])
        if method_clauses:
            where.append("(" + " OR ".join(method_clauses) + ")")

    sql = f"""
        SELECT p.id, p.title, p.discount, p.bank, p.wallet, p.card_type,
               p.payment_method, p.store_types, p.valid_days,
               p.valid_from, p.valid_until, p.tope, p.min_purchase,
               s.name AS supermarket_name,
               COALESCE(s.category, 'supermarket') AS category
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        WHERE {' AND '.join(where)}
        ORDER BY s.name, p.scraped_at DESC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Render helpers ────────────────────────────────────────────────────────────
def _paginate(promos: list[dict], page: int) -> tuple[list[dict], int]:
    """Devuelve (slice, total_pages) — page es 1-indexed."""
    total_pages = max(1, (len(promos) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    return promos[start:start + PAGE_SIZE], total_pages


def _render_promos(promos: list[dict], header: str, page: int = 1) -> tuple[str, dict]:
    """Devuelve (texto formateado, reply_markup). Vacío si no hay promos."""
    if not promos:
        return f"{header}\n\n_No se encontraron promociones._", {}

    page_promos, total_pages = _paginate(promos, page)

    lines = [header, "─" * 28]
    for p in page_promos:
        sm = p.get("supermarket_name") or ""
        lines.append(f"🏷️ *{sm}*")
        lines.append(_format_promo(p))
        lines.append("")
    lines.append(f"_Página {page}/{total_pages} · {len(promos)} resultados_")
    return "\n".join(lines), {}


def _pagination_markup(callback_prefix: str, page: int, total_pages: int,
                        extra_args: str = "") -> dict:
    """Inline keyboard «1/N»."""
    if total_pages <= 1:
        return {}
    suffix = f":{extra_args}" if extra_args else ""
    buttons = []
    if page > 1:
        buttons.append({
            "text": "« Anterior",
            "callback_data": f"{callback_prefix}:{page - 1}{suffix}"[:64],
        })
    buttons.append({"text": f"{page}/{total_pages}", "callback_data": "noop"})
    if page < total_pages:
        buttons.append({
            "text": "Siguiente »",
            "callback_data": f"{callback_prefix}:{page + 1}{suffix}"[:64],
        })
    return {"inline_keyboard": [buttons]}


# ── Comandos ──────────────────────────────────────────────────────────────────
def cmd_start(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    text = (
        "👋 *Hola! Soy el bot de PromoAR*\n\n"
        "Te muestro promos bancarias activas en supermercados y combustibles "
        "de Argentina.\n\n"
        "*Comandos públicos:*\n"
        "• /hoy — promos vigentes hoy\n"
        "• /buscar `<texto>` — buscar promos\n"
        "• /banco `<nombre>` — filtrar por banco/wallet\n"
        "• /super `<nombre>` — filtrar por super o marca\n"
        "• /combustible — promos de combustible hoy\n"
        "• /stats — estadísticas\n\n"
        "*Comandos personalizados* (requieren cuenta):\n"
        "• /mis — promos para tus medios de pago\n"
        "• /medios — ver/editar tus medios\n"
        "• /notify `on|off` — toggle notificaciones diarias\n"
        "• /hora `<0-23>` — hora del digest diario\n\n"
        "Para vincular tu cuenta, registrate en la web y agregá este chat_id "
        f"en tu perfil:\n`{chat_id}`\n\n"
        "/ayuda — más detalles"
    )
    return text, {}


def cmd_ayuda(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    text = (
        "📖 *Ayuda — PromoAR Bot*\n\n"
        "*Comandos públicos*\n\n"
        "`/hoy` — Lista promos vigentes hoy. Paginado con botones.\n\n"
        "`/buscar nafta` — Busca \"nafta\" en título y T&C.\n\n"
        "`/banco galicia` — Promos del Banco Galicia.\n"
        "`/banco modo` — Promos pagando con MODO.\n\n"
        "`/super coto` — Promos en Coto.\n"
        "`/super ypf` — Promos en YPF.\n\n"
        "`/combustible` — Solo promos de combustible vigentes hoy.\n\n"
        "`/stats` — Total de promos, supers y bancos.\n\n"
        "*Comandos privados* (requieren cuenta linkeada)\n\n"
        "`/mis` — Promos que matchean tus medios de pago.\n"
        "`/medios` — Ver tus medios. Editá desde la web.\n"
        "`/notify on` o `/notify off` — Toggle digest diario.\n"
        "`/hora 9` — Cambiar hora del digest (0-23).\n\n"
        "Para vincular: registrate en la web → perfil → "
        f"pegá `{chat_id}` en \"Telegram chat_id\"."
    )
    return text, {}


def cmd_hoy(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    promos = _query_promotions(today_only=True)
    today_label = datetime.now().strftime("%A %d/%m").capitalize()
    header = f"📅 *Promos de hoy — {today_label}*"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("hoy", page, total_pages)


def cmd_mis(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    user = user_db.get_user_by_telegram_chat_id(chat_id)
    if not user:
        return (
            "🔒 *No tenés cuenta linkeada*\n\n"
            "Para usar /mis, registrate en la web y pegá este chat_id en tu perfil:\n"
            f"`{chat_id}`"
        ), {}

    methods = user_db.get_user_payment_methods(user["id"])
    if not methods:
        return (
            "💳 *Tu cuenta no tiene medios de pago*\n\n"
            "Configurá tus tarjetas/billeteras desde la web (perfil → medios de pago) "
            "y volvé a probar /mis."
        ), {}

    promos = _query_promotions(today_only=True, payment_methods=methods)
    methods_str = ", ".join(m["name"] for m in methods)
    header = f"💳 *Tus promos de hoy*\n_Medios: {methods_str}_"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("mis", page, total_pages)


def cmd_buscar(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    query = (args or "").strip()
    if not query:
        return "❓ Uso: `/buscar <texto>` — ej: `/buscar nafta`", {}
    promos = _query_promotions(search=query)
    header = f"🔍 *Búsqueda:* `{query}`"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("buscar", page, total_pages, extra_args=query[:32])


def cmd_banco(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    bank = (args or "").strip()
    if not bank:
        return "❓ Uso: `/banco <nombre>` — ej: `/banco galicia` o `/banco modo`", {}
    promos = _query_promotions(bank_filter=bank)
    header = f"🏦 *Promos de:* `{bank}`"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("banco", page, total_pages, extra_args=bank[:32])


def cmd_super(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    sm = (args or "").strip()
    if not sm:
        return "❓ Uso: `/super <nombre>` — ej: `/super coto` o `/super ypf`", {}
    promos = _query_promotions(supermarket_filter=sm)
    header = f"🏪 *Promos en:* `{sm}`"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("super", page, total_pages, extra_args=sm[:32])


def cmd_combustible(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    promos = _query_promotions(today_only=True, category="fuel")
    header = "⛽ *Promos de combustible — hoy*"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("combustible", page, total_pages)


def cmd_stats(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    conn = _promos_conn()
    today_iso = date.today().isoformat()
    total = conn.execute(
        "SELECT COUNT(*) FROM promotions p WHERE p.is_active = 1 "
        "AND (p.valid_until IS NULL OR p.valid_until = '' OR p.valid_until >= ?)",
        (today_iso,),
    ).fetchone()[0]
    by_cat = conn.execute("""
        SELECT COALESCE(s.category, 'supermarket') AS cat, COUNT(p.id) AS n
        FROM promotions p JOIN supermarkets s ON p.supermarket_id = s.id
        WHERE p.is_active = 1 GROUP BY cat
    """).fetchall()
    super_n = conn.execute(
        "SELECT COUNT(DISTINCT s.id) FROM supermarkets s "
        "JOIN promotions p ON p.supermarket_id = s.id WHERE p.is_active = 1"
    ).fetchone()[0]
    bank_n = conn.execute(
        "SELECT COUNT(DISTINCT bank) FROM promotions WHERE is_active = 1 AND bank IS NOT NULL AND bank != ''"
    ).fetchone()[0]
    conn.close()

    cat_lines = [f"  • {r['cat']}: {r['n']}" for r in by_cat]
    text = (
        "📊 *Estadísticas PromoAR*\n\n"
        f"🎯 Promos activas: *{total}*\n"
        f"🏪 Comercios con promos: *{super_n}*\n"
        f"🏦 Bancos/wallets distintos: *{bank_n}*\n\n"
        "*Por categoría:*\n" + "\n".join(cat_lines)
    )
    return text, {}


def cmd_medios(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    user = user_db.get_user_by_telegram_chat_id(chat_id)
    if not user:
        return f"🔒 Linkea tu cuenta primero. Usá /start para ver cómo.", {}

    methods = user_db.get_user_payment_methods(user["id"])
    if not methods:
        text = (
            "💳 *No tenés medios de pago configurados*\n\n"
            "Editalos desde la web (perfil → medios de pago)."
        )
        return text, {}

    by_type: dict[str, list[str]] = {}
    for m in methods:
        by_type.setdefault(m["type"], []).append(m["name"])
    lines = ["💳 *Tus medios de pago*\n"]
    type_labels = {"bank": "🏦 Bancos", "wallet": "📱 Wallets", "club": "🎟️ Clubes"}
    for t, names in by_type.items():
        lines.append(f"*{type_labels.get(t, t)}:*")
        for n in names:
            lines.append(f"  • {n}")
        lines.append("")
    lines.append("_Para editar, usá la web (perfil)._")
    return "\n".join(lines), {}


def cmd_notify(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    user = user_db.get_user_by_telegram_chat_id(chat_id)
    if not user:
        return "🔒 Linkea tu cuenta primero. Usá /start.", {}

    flag = (args or "").strip().lower()
    if flag not in ("on", "off"):
        current = "ON" if user.get("notify_daily") else "OFF"
        return f"🔔 Notificaciones: *{current}*\n\nUso: `/notify on` o `/notify off`", {}

    notify_on = flag == "on"
    user_db.update_user_telegram(
        user["id"],
        chat_id,
        notify_daily=notify_on,
        notify_hour=user.get("notify_hour") or 9,
    )
    return f"✅ Notificaciones diarias *{'activadas' if notify_on else 'desactivadas'}*", {}


def cmd_hora(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    user = user_db.get_user_by_telegram_chat_id(chat_id)
    if not user:
        return "🔒 Linkea tu cuenta primero. Usá /start.", {}

    raw = (args or "").strip()
    try:
        hour = int(raw)
        assert 0 <= hour <= 23
    except (ValueError, AssertionError):
        current = user.get("notify_hour") or 9
        return f"🕐 Hora actual del digest: *{current}:00*\n\nUso: `/hora 9` (entre 0 y 23)", {}

    user_db.update_user_telegram(
        user["id"],
        chat_id,
        notify_daily=bool(user.get("notify_daily")),
        notify_hour=hour,
    )
    return f"✅ Digest diario configurado a las *{hour}:00*", {}


# ── Dispatcher ────────────────────────────────────────────────────────────────
COMMANDS = {
    "start": cmd_start,
    "ayuda": cmd_ayuda,
    "help": cmd_ayuda,
    "hoy": cmd_hoy,
    "mis": cmd_mis,
    "buscar": cmd_buscar,
    "banco": cmd_banco,
    "super": cmd_super,
    "combustible": cmd_combustible,
    "stats": cmd_stats,
    "medios": cmd_medios,
    "notify": cmd_notify,
    "hora": cmd_hora,
}


def handle_message(update: dict, user_db: UserDatabase, notifier: TelegramNotifier) -> None:
    """Procesa un message entrante. Idempotente — Telegram puede reentregar."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat_id = str(msg["chat"]["id"])
    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        # No-op para texto plano. Podemos sugerir /ayuda en el futuro.
        return

    # Telegram permite /comando@botname — descartamos el sufijo
    head, _, args = text.partition(" ")
    cmd = head[1:].split("@", 1)[0].lower()

    handler = COMMANDS.get(cmd)
    if not handler:
        notifier.send_message_to(chat_id, f"❓ Comando desconocido: `{cmd}`\n\nUsá /ayuda")
        return

    reply_text, reply_markup = handler(chat_id, args, user_db)
    notifier.send_message_to(chat_id, reply_text, reply_markup=reply_markup or None)


def handle_callback_query(update: dict, user_db: UserDatabase, notifier: TelegramNotifier) -> None:
    """Procesa botones inline (paginación)."""
    cq = update.get("callback_query")
    if not cq:
        return
    chat_id = str(cq["message"]["chat"]["id"])
    message_id = cq["message"]["message_id"]
    data = cq.get("data") or ""
    callback_id = cq["id"]

    if data == "noop":
        notifier.answer_callback_query(callback_id)
        return

    # Formato: "<cmd>:<page>[:<extra>]"
    parts = data.split(":", 2)
    if len(parts) < 2:
        notifier.answer_callback_query(callback_id)
        return

    cmd, page_str, *rest = parts
    try:
        page = int(page_str)
    except ValueError:
        notifier.answer_callback_query(callback_id)
        return
    extra = rest[0] if rest else ""

    handler = COMMANDS.get(cmd)
    if not handler:
        notifier.answer_callback_query(callback_id)
        return

    # Solo los handlers paginables aceptan page kwarg
    try:
        reply_text, reply_markup = handler(chat_id, extra, user_db, page=page)
    except TypeError:
        reply_text, reply_markup = handler(chat_id, extra, user_db)

    notifier.edit_message_text(chat_id, message_id, reply_text, reply_markup=reply_markup or None)
    notifier.answer_callback_query(callback_id)
