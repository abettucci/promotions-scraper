"""
Bot handlers para el webhook de Telegram.

Cada comando se resuelve consultando directamente la DB de promociones y la de
usuarios. La interacción es two-way: comandos en texto + inline keyboards para
paginación y selección.

Usa parse_mode=HTML (más robusto que Markdown para texto scrapeado).

Comandos:
  P0: /start /ayuda /hoy /mis
  P1: /buscar /banco /super /combustible /stats
  P2: /medios /notify /hora
"""
from __future__ import annotations

import html
import sqlite3
from datetime import date, datetime
from typing import Optional

import config
from database import UserDatabase
from notifier import TelegramNotifier, _strip_accents, _today_name, DAY_NAMES_ES

PAGE_SIZE = 8  # promos por página (Telegram tiene 4096 chars/msg)


# ── DB helpers ────────────────────────────────────────────────────────────────
def _promos_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _has_supermarket_category() -> bool:
    try:
        conn = _promos_conn()
        rows = conn.execute("PRAGMA table_info(supermarkets)").fetchall()
        conn.close()
        return any(row["name"] == "category" for row in rows)
    except Exception:
        return False


_HAS_SUPERMARKET_CATEGORY = _has_supermarket_category()


def _query_promotions(
    *,
    today_only: bool = False,
    category: Optional[str] = None,
    bank_filter: Optional[str] = None,
    supermarket_filter: Optional[str] = None,
    search: Optional[str] = None,
    payment_methods: Optional[list[dict]] = None,
    modality_filter: Optional[str] = None,
    discount_filter: Optional[str] = None,
    payment_filter: Optional[str] = None,
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
        if _HAS_SUPERMARKET_CATEGORY:
            where.append("LOWER(COALESCE(s.category, 'supermarket')) = ?")
            params.append(category.lower())
        elif category.lower() != "supermarket":
            where.append("1 = 0")

    if bank_filter:
        where.append(
            "(LOWER(p.bank) LIKE ? OR LOWER(p.wallet) LIKE ? "
            "OR LOWER(COALESCE(p.payment_method,'')) LIKE ? "
            "OR LOWER(COALESCE(p.title,'')) LIKE ?)"
        )
        params.extend([f"%{bank_filter.lower()}%"] * 4)

    if supermarket_filter:
        where.append("LOWER(s.name) LIKE ?")
        params.append(f"%{supermarket_filter.lower()}%")

    if search:
        where.append("(LOWER(p.title) LIKE ? OR LOWER(p.terms_raw) LIKE ?)")
        params.extend([f"%{search.lower()}%"] * 2)

    if today_only:
        today_es = _today_name()
        today_norm = _strip_accents(today_es).lower()
        if today_norm != today_es:
            where.append(
                "(p.valid_days IS NULL OR p.valid_days = '' "
                "OR LOWER(p.valid_days) LIKE ? OR LOWER(p.valid_days) LIKE ? "
                "OR LOWER(p.valid_days) LIKE '%todos los d%')"
            )
            params.extend([f"%{today_es}%", f"%{today_norm}%"])
        else:
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
                method_clauses.append(
                    "(LOWER(p.bank) LIKE ? OR LOWER(p.wallet) LIKE ? "
                    "OR LOWER(COALESCE(p.payment_method,'')) LIKE ? "
                    "OR LOWER(COALESCE(p.title,'')) LIKE ?)"
                )
                params.extend([f"%{name}%"] * 4)
        if method_clauses:
            where.append("(" + " OR ".join(method_clauses) + ")")

    if modality_filter == "online":
        where.append("LOWER(COALESCE(p.store_types, '')) LIKE '%online%'")
    elif modality_filter == "presencial":
        where.append("LOWER(COALESCE(p.store_types, '')) LIKE '%presencial%'")

    if discount_filter == "descuento":
        where.append("(LOWER(COALESCE(p.discount, '')) LIKE '%descuento%' OR p.discount LIKE '%\\%%' ESCAPE '\\')")
    elif discount_filter == "cuotas":
        where.append("LOWER(COALESCE(p.discount, '')) LIKE '%cuota%'")

    payment_terms = {
        "credito": "crédito",
        "debito": "débito",
        "cuenta": "dinero en cuenta",
    }
    if payment_filter in payment_terms:
        term = payment_terms[payment_filter]
        where.append(
            "(LOWER(COALESCE(p.card_type, '')) LIKE ? OR "
            "LOWER(COALESCE(p.payment_method, '')) LIKE ? OR "
            "LOWER(COALESCE(p.title, '')) LIKE ? OR "
            "LOWER(COALESCE(p.terms_raw, '')) LIKE ?)"
        )
        params.extend([f"%{term}%"] * 4)

    sql = f"""
        SELECT p.id, p.title, p.discount, p.bank, p.wallet, p.card_type,
               p.payment_method, p.store_types, p.valid_days,
               p.valid_from, p.valid_until, p.tope, p.min_purchase,
               p.terms_raw, p.exclusions, p.requirements, p.url, p.acumulable,
               s.name AS supermarket_name,
               {"COALESCE(s.category, 'supermarket')" if _HAS_SUPERMARKET_CATEGORY else "'supermarket'"} AS category
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


# ── Render helpers (HTML) ─────────────────────────────────────────────────────
def _esc(value) -> str:
    """Escape seguro para parse_mode=HTML."""
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def _format_promo_html(p: dict) -> str:
    """Formatea una promo en HTML escapado."""
    discount = _esc(p.get("discount") or "")
    entity = _esc(p.get("bank") or p.get("wallet") or "N/A")
    parts = [f"💳 <b>{discount}</b> — {entity}"]

    details = []
    if p.get("valid_days"):
        details.append(f"📅 {_esc(p['valid_days'])}")
    if p.get("store_types"):
        details.append(f"🏪 {_esc(p['store_types'])}")
    if p.get("tope"):
        details.append(f"⚠️ Tope {_esc(p['tope'])}")
    if p.get("min_purchase"):
        details.append(f"🛍️ Mínimo {_esc(p['min_purchase'])}")
    if p.get("exclusions"):
        details.append("⚠️ Aplica exclusiones · ver condiciones")
    if details:
        parts.append("   " + " | ".join(details))
    return "\n".join(parts)


def _paginate(promos: list[dict], page: int) -> tuple[list[dict], int]:
    """Devuelve (slice, total_pages) — page es 1-indexed."""
    total_pages = max(1, (len(promos) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    return promos[start:start + PAGE_SIZE], total_pages


def _render_promos(promos: list[dict], header: str, page: int = 1) -> tuple[str, dict]:
    """Devuelve (texto formateado HTML, reply_markup). Vacío si no hay promos."""
    if not promos:
        return f"{header}\n\n<i>No se encontraron promociones.</i>", {}

    page_promos, total_pages = _paginate(promos, page)

    lines = [header, "─" * 28]
    for p in page_promos:
        sm = _esc(p.get("supermarket_name") or "")
        lines.append(f"🏷️ <b>{sm}</b>")
        lines.append(_format_promo_html(p))
        lines.append("")
    lines.append(f"<i>Página {page}/{total_pages} · {len(promos)} resultados</i>")
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


def _category_markup(scope: str) -> dict:
    """Selector inicial para no mezclar supermercados y combustible."""
    return {
        "inline_keyboard": [[
            {"text": "🛒 Supermercados", "callback_data": f"{scope}cat:supermarket"},
            {"text": "⛽ Combustible", "callback_data": f"{scope}cat:fuel"},
        ]]
    }


def _results_markup(promos: list[dict], callback_prefix: str, page: int,
                    total_pages: int, scope: str, category_code: str,
                    filter_state: Optional[tuple[str, str]] = None) -> dict:
    """Paginación, acceso a condiciones y filtro guiado para un resultado."""
    if filter_state:
        filter_kind, filter_value = filter_state
        markup = _filtered_pagination_markup(scope, category_code, filter_kind, filter_value, page, total_pages)
    else:
        markup = _pagination_markup(callback_prefix, page, total_pages)
    rows = list(markup.get("inline_keyboard", []))
    page_promos, _ = _paginate(promos, page)
    for promo in page_promos:
        promo_id = promo.get("id")
        if isinstance(promo_id, int) and promo_id > 0:
            label = (promo.get("bank") or promo.get("wallet") or promo.get("supermarket_name") or "esta promo")
            rows.append([{
                "text": f"Ver condiciones · {label}"[:64],
                "callback_data": f"terms:{promo_id}",
            }])
    rows.append([{"text": "⚙️ Filtrar resultados", "callback_data": f"f:{scope}:{category_code}"}])
    return {"inline_keyboard": rows}


def _filtered_pagination_markup(scope: str, category: str, filter_kind: str,
                                filter_value: str, page: int, total_pages: int) -> dict:
    if total_pages <= 1:
        return {}
    buttons = []
    if page > 1:
        buttons.append({"text": "« Anterior", "callback_data": f"pf:{scope}:{category}:{filter_kind}:{filter_value}:{page - 1}"})
    buttons.append({"text": f"{page}/{total_pages}", "callback_data": "noop"})
    if page < total_pages:
        buttons.append({"text": "Siguiente »", "callback_data": f"pf:{scope}:{category}:{filter_kind}:{filter_value}:{page + 1}"})
    return {"inline_keyboard": [buttons]}


# ── Comandos ──────────────────────────────────────────────────────────────────
def cmd_start(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    text = (
        "👋 <b>Hola! Soy el bot de PromoAR</b>\n\n"
        "Te muestro promos bancarias activas en supermercados y combustibles "
        "de Argentina.\n\n"
        "<b>Comandos públicos:</b>\n"
        "• /hoy — elegí promos de supermercados o combustible\n"
        "• /buscar &lt;texto&gt; — buscar promos\n"
        "• /banco &lt;nombre&gt; — filtrar por banco/wallet\n"
        "• /super &lt;nombre&gt; — filtrar por super o marca\n"
        "• /combustible — promos de combustible hoy\n"
        "• Escribime una pregunta — ej. <i>¿El vino Alaris está excluido en Coto hoy?</i>\n"
        "• /stats — estadísticas\n\n"
        "<b>Comandos personalizados</b> (requieren cuenta):\n"
        "• /mis — promos para tus medios de pago\n"
        "• /medios — ver tus medios\n"
        "• /notify on|off — toggle notificaciones diarias\n"
        "• /hora &lt;0-23&gt; — hora del digest diario\n\n"
        "Para vincular tu cuenta, registrate en la web y agregá este chat_id "
        f"en tu perfil:\n<code>{_esc(chat_id)}</code>\n\n"
        "/ayuda — más detalles"
    )
    return text, {}


def cmd_ayuda(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    text = (
        "📖 <b>Ayuda — PromoAR Bot</b>\n\n"
        "<b>Comandos públicos</b>\n\n"
        "<code>/hoy</code> — Elegí supermercados o combustible y recibí solo esa categoría.\n\n"
        "<code>/buscar nafta</code> — Busca \"nafta\" en título y T&amp;C.\n\n"
        "<code>/banco galicia</code> — Promos del Banco Galicia.\n"
        "<code>/banco modo</code> — Promos pagando con MODO.\n\n"
        "<code>/super coto</code> — Promos en Coto.\n"
        "<code>/super ypf</code> — Promos en YPF.\n\n"
        "<code>/combustible</code> — Solo promos de combustible vigentes hoy.\n\n"
        "<b>Preguntas en lenguaje natural</b>\n\n"
        "También podés escribirme sin comando. Por ejemplo:\n"
        "<i>¿El vino Alaris está excluido de la promo de Coto hoy?</i>\n"
        "<i>¿En qué súper me conviene comprar vino hoy?</i>\n\n"
        "Las recomendaciones usan tus medios vinculados si tenés cuenta y aclaran "
        "cuando los T&amp;C no permiten confirmar un producto.\n\n"
        "<code>/stats</code> — Total de promos, supers y bancos.\n\n"
        "<b>Comandos privados</b> (requieren cuenta linkeada)\n\n"
        "<code>/mis</code> — Promos que matchean tus medios de pago.\n"
        "<code>/medios</code> — Ver tus medios. Editá desde la web.\n"
        "<code>/notify on</code> o <code>/notify off</code> — Toggle digest diario.\n"
        "<code>/hora 9</code> — Cambiar hora del digest (0-23).\n\n"
        "Para vincular: registrate en la web → perfil → "
        f"pegá <code>{_esc(chat_id)}</code> en \"Telegram chat_id\"."
    )
    return text, {}


def cmd_hoy(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    today_label = datetime.now().strftime("%A %d/%m").capitalize()
    text = (
        f"📅 <b>Promos de hoy — {_esc(today_label)}</b>\n\n"
        "¿Qué promociones querés ver?"
    )
    return text, _category_markup("hoy")


def _cmd_hoy_category(category: str, header: str, callback_prefix: str,
                       page: int) -> tuple[str, dict]:
    promos = _query_promotions(today_only=True, category=category)
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    category_code = "s" if category == "supermarket" else "f"
    return text, _results_markup(promos, callback_prefix, page, total_pages, "h", category_code)


def cmd_hoy_supermarkets(chat_id: str, args: str, user_db: UserDatabase,
                         page: int = 1) -> tuple[str, dict]:
    return _cmd_hoy_category(
        "supermarket", "🛒 <b>Promos de supermercados — hoy</b>", "hoysuper", page,
    )


def cmd_hoy_fuel(chat_id: str, args: str, user_db: UserDatabase,
                 page: int = 1) -> tuple[str, dict]:
    return _cmd_hoy_category(
        "fuel", "⛽ <b>Promos de combustible — hoy</b>", "hoyfuel", page,
    )


def _linked_payment_methods(chat_id: str, user_db: UserDatabase) -> tuple[Optional[str], list[dict]]:
    user = user_db.get_user_by_telegram_chat_id(chat_id)
    if not user:
        return (
            "🔒 <b>No tenés cuenta linkeada</b>\n\n"
            "Para usar /mis, registrate en la web y pegá este chat_id en tu perfil:\n"
            f"<code>{_esc(chat_id)}</code>",
            [],
        )

    methods = user_db.get_user_payment_methods(user["id"])
    if not methods:
        return (
            "💳 <b>Tu cuenta no tiene medios de pago</b>\n\n"
            "Configurá tus tarjetas/billeteras desde la web (perfil → medios de pago) "
            "y volvé a probar /mis.",
            [],
        )
    return None, methods


def _cmd_mis_category(chat_id: str, user_db: UserDatabase, category: str,
                      header: str, callback_prefix: str, page: int = 1,
                      modality_filter: Optional[str] = None,
                      discount_filter: Optional[str] = None,
                      payment_filter: Optional[str] = None) -> tuple[str, dict]:
    error, methods = _linked_payment_methods(chat_id, user_db)
    if error:
        return error, {}

    promos = _query_promotions(
        today_only=True,
        category=category,
        payment_methods=methods,
        modality_filter=modality_filter,
        discount_filter=discount_filter,
        payment_filter=payment_filter,
    )
    methods_str = _esc(", ".join(method["name"] for method in methods))
    text, _ = _render_promos(promos, f"{header}\n<i>Medios: {methods_str}</i>", page)
    _, total_pages = _paginate(promos, page)
    category_code = "s" if category == "supermarket" else "f"
    return text, _results_markup(promos, callback_prefix, page, total_pages, "m", category_code)


def cmd_mis_supermarkets(chat_id: str, args: str, user_db: UserDatabase,
                         page: int = 1) -> tuple[str, dict]:
    return _cmd_mis_category(
        chat_id, user_db, "supermarket", "💳 <b>Tus promos de supermercados — hoy</b>",
        "missuper", page,
    )


def cmd_mis_fuel(chat_id: str, args: str, user_db: UserDatabase,
                 page: int = 1) -> tuple[str, dict]:
    return _cmd_mis_category(
        chat_id, user_db, "fuel", "⛽ <b>Tus promos de combustible — hoy</b>",
        "misfuel", page,
    )


def cmd_mis(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    error, _ = _linked_payment_methods(chat_id, user_db)
    if error:
        return error, {}
    return (
        "💳 <b>Tus promos de hoy</b>\n\n"
        "¿Qué categoría querés revisar con tus medios de pago?",
        _category_markup("mis"),
    )


def cmd_buscar(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    query = (args or "").strip()
    if not query:
        return "❓ Uso: <code>/buscar &lt;texto&gt;</code> — ej: <code>/buscar nafta</code>", {}
    promos = _query_promotions(search=query)
    header = f"🔍 <b>Búsqueda:</b> <code>{_esc(query)}</code>"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("buscar", page, total_pages, extra_args=query[:32])


def cmd_banco(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    bank = (args or "").strip()
    if not bank:
        return "❓ Uso: <code>/banco &lt;nombre&gt;</code> — ej: <code>/banco galicia</code> o <code>/banco modo</code>", {}
    promos = _query_promotions(bank_filter=bank)
    header = f"🏦 <b>Promos de:</b> <code>{_esc(bank)}</code>"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("banco", page, total_pages, extra_args=bank[:32])


def cmd_super(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    sm = (args or "").strip()
    if not sm:
        return "❓ Uso: <code>/super &lt;nombre&gt;</code> — ej: <code>/super coto</code> o <code>/super ypf</code>", {}
    promos = _query_promotions(supermarket_filter=sm)
    header = f"🏪 <b>Promos en:</b> <code>{_esc(sm)}</code>"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("super", page, total_pages, extra_args=sm[:32])


def cmd_combustible(chat_id: str, args: str, user_db: UserDatabase, page: int = 1) -> tuple[str, dict]:
    promos = _query_promotions(today_only=True, category="fuel")
    header = "⛽ <b>Promos de combustible — hoy</b>"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    return text, _pagination_markup("combustible", page, total_pages)


def cmd_stats(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    conn = _promos_conn()
    today_iso = date.today().isoformat()
    active_clause = (
        "p.is_active = 1 "
        "AND (p.valid_until IS NULL OR p.valid_until = '' OR p.valid_until >= ?) "
        "AND (p.valid_from IS NULL OR p.valid_from = '' OR p.valid_from <= ?)"
    )
    total = conn.execute(
        f"SELECT COUNT(*) FROM promotions p WHERE {active_clause}",
        (today_iso, today_iso),
    ).fetchone()[0]
    category_expr = "COALESCE(s.category, 'supermarket')" if _HAS_SUPERMARKET_CATEGORY else "'supermarket'"
    by_cat = conn.execute(f"""
        SELECT {category_expr} AS cat, COUNT(p.id) AS n
        FROM promotions p JOIN supermarkets s ON p.supermarket_id = s.id
        WHERE {active_clause} GROUP BY cat
    """, (today_iso, today_iso)).fetchall()
    super_n = conn.execute(
        "SELECT COUNT(DISTINCT s.id) FROM supermarkets s "
        f"JOIN promotions p ON p.supermarket_id = s.id WHERE {active_clause}",
        (today_iso, today_iso),
    ).fetchone()[0]
    bank_n = conn.execute(
        f"SELECT COUNT(DISTINCT bank) FROM promotions p WHERE {active_clause} "
        "AND bank IS NOT NULL AND bank != ''",
        (today_iso, today_iso),
    ).fetchone()[0]
    conn.close()

    cat_lines = [f"  • {_esc(r['cat'])}: {r['n']}" for r in by_cat]
    text = (
        "📊 <b>Estadísticas PromoAR</b>\n\n"
        f"🎯 Promos activas: <b>{total}</b>\n"
        f"🏪 Comercios con promos: <b>{super_n}</b>\n"
        f"🏦 Bancos/wallets distintos: <b>{bank_n}</b>\n\n"
        "<b>Por categoría:</b>\n" + "\n".join(cat_lines)
    )
    return text, {}


def cmd_medios(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    user = user_db.get_user_by_telegram_chat_id(chat_id)
    if not user:
        return "🔒 Linkea tu cuenta primero. Usá /start para ver cómo.", {}

    methods = user_db.get_user_payment_methods(user["id"])
    if not methods:
        text = (
            "💳 <b>No tenés medios de pago configurados</b>\n\n"
            "Editalos desde la web (perfil → medios de pago)."
        )
        return text, {}

    by_type: dict[str, list[str]] = {}
    for m in methods:
        by_type.setdefault(m["type"], []).append(m["name"])
    lines = ["💳 <b>Tus medios de pago</b>\n"]
    type_labels = {"bank": "🏦 Bancos", "wallet": "📱 Wallets", "club": "🎟️ Clubes"}
    for t, names in by_type.items():
        lines.append(f"<b>{type_labels.get(t, _esc(t))}:</b>")
        for n in names:
            lines.append(f"  • {_esc(n)}")
        lines.append("")
    lines.append("<i>Para editar, usá la web (perfil).</i>")
    return "\n".join(lines), {}


def cmd_notify(chat_id: str, args: str, user_db: UserDatabase) -> tuple[str, dict]:
    user = user_db.get_user_by_telegram_chat_id(chat_id)
    if not user:
        return "🔒 Linkea tu cuenta primero. Usá /start.", {}

    flag = (args or "").strip().lower()
    if flag not in ("on", "off"):
        current = "ON" if user.get("notify_daily") else "OFF"
        return f"🔔 Notificaciones: <b>{current}</b>\n\nUso: <code>/notify on</code> o <code>/notify off</code>", {}

    notify_on = flag == "on"
    user_db.update_user_telegram(
        user["id"],
        chat_id,
        notify_daily=notify_on,
        notify_hour=user.get("notify_hour") or 9,
    )
    return f"✅ Notificaciones diarias <b>{'activadas' if notify_on else 'desactivadas'}</b>", {}


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
        return f"🕐 Hora actual del digest: <b>{current}:00</b>\n\nUso: <code>/hora 9</code> (entre 0 y 23)", {}

    user_db.update_user_telegram(
        user["id"],
        chat_id,
        notify_daily=bool(user.get("notify_daily")),
        notify_hour=hour,
    )
    return f"✅ Digest diario configurado a las <b>{hour}:00</b>", {}


# ── Filtros guiados de resultados ────────────────────────────────────────────
_FILTER_DIMENSIONS = {
    "m": ("Modalidad", [("o", "🌐 Online"), ("p", "🏪 Presencial")]),
    "b": ("Tipo de beneficio", [("d", "🏷️ Descuento"), ("q", "🧾 Cuotas")]),
    "p": ("Medio de pago", [("c", "💳 Crédito"), ("d", "💳 Débito"), ("e", "💰 Dinero en cuenta")]),
}
_FILTER_VALUES = {
    ("m", "o"): ("modality_filter", "online", "Online"),
    ("m", "p"): ("modality_filter", "presencial", "Presencial"),
    ("b", "d"): ("discount_filter", "descuento", "Descuento"),
    ("b", "q"): ("discount_filter", "cuotas", "Cuotas"),
    ("p", "c"): ("payment_filter", "credito", "Crédito"),
    ("p", "d"): ("payment_filter", "debito", "Débito"),
    ("p", "e"): ("payment_filter", "cuenta", "Dinero en cuenta"),
}
_SCOPE_LABELS = {"h": "Promos de hoy", "m": "Tus promos de hoy"}
_CATEGORY_VALUES = {"s": "supermarket", "f": "fuel"}


def _filter_menu(scope: str, category_code: str) -> tuple[str, dict]:
    if scope not in _SCOPE_LABELS or category_code not in _CATEGORY_VALUES:
        return "❓ No pude reconocer ese filtro.", {}
    buttons = [
        [{"text": f"{label}", "callback_data": f"k:{scope}:{category_code}:{code}"}]
        for code, (label, _) in _FILTER_DIMENSIONS.items()
    ]
    buttons.append([{"text": "← Volver a resultados", "callback_data": f"r:{scope}:{category_code}"}])
    return "⚙️ <b>Filtrar resultados</b>\n\nElegí qué querés filtrar:", {"inline_keyboard": buttons}


def _filter_options(scope: str, category_code: str, kind: str) -> tuple[str, dict]:
    dimension = _FILTER_DIMENSIONS.get(kind)
    if scope not in _SCOPE_LABELS or category_code not in _CATEGORY_VALUES or not dimension:
        return "❓ No pude reconocer ese filtro.", {}
    label, options = dimension
    buttons = [
        [{"text": option_label, "callback_data": f"a:{scope}:{category_code}:{kind}:{option_code}"}]
        for option_code, option_label in options
    ]
    buttons.append([{"text": "← Otros filtros", "callback_data": f"f:{scope}:{category_code}"}])
    return f"⚙️ <b>{_esc(label)}</b>\n\nElegí una opción:", {"inline_keyboard": buttons}


def _filtered_results(chat_id: str, user_db: UserDatabase, scope: str,
                      category_code: str, kind: str, value: str,
                      page: int = 1) -> tuple[str, dict]:
    category = _CATEGORY_VALUES.get(category_code)
    filter_config = _FILTER_VALUES.get((kind, value))
    if scope not in _SCOPE_LABELS or not category or not filter_config:
        return "❓ No pude reconocer ese filtro.", {}

    filter_name, filter_value, filter_label = filter_config
    query_kwargs = {"today_only": True, "category": category, filter_name: filter_value}
    header_prefix = "📅" if scope == "h" else "💳"
    if scope == "m":
        error, methods = _linked_payment_methods(chat_id, user_db)
        if error:
            return error, {}
        query_kwargs["payment_methods"] = methods

    promos = _query_promotions(**query_kwargs)
    category_label = "supermercados" if category == "supermarket" else "combustible"
    header = f"{header_prefix} <b>{_SCOPE_LABELS[scope]} · {category_label}</b>\n<i>Filtro: {_esc(filter_label)}</i>"
    text, _ = _render_promos(promos, header, page)
    _, total_pages = _paginate(promos, page)
    callback_prefix = {("h", "s"): "hoysuper", ("h", "f"): "hoyfuel", ("m", "s"): "missuper", ("m", "f"): "misfuel"}[(scope, category_code)]
    return text, _results_markup(
        promos, callback_prefix, page, total_pages, scope, category_code, (kind, value),
    )


def _promotion_conditions(promotion_id: int) -> Optional[dict]:
    """Lee solo una promo vigente para el callback de condiciones."""
    conn = _promos_conn()
    today_iso = date.today().isoformat()
    row = conn.execute(
        """
        SELECT p.id, p.title, p.discount, p.bank, p.wallet, p.card_type,
               p.payment_method, p.store_types, p.valid_days, p.valid_from,
               p.valid_until, p.tope, p.min_purchase, p.terms_raw, p.exclusions,
               p.requirements, p.acumulable, p.url, s.name AS supermarket_name,
               COALESCE(NULLIF((SELECT t.raw_text FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1), ''), p.terms_raw) AS raw_text,
               COALESCE(NULLIF(NULLIF((SELECT t.exclusions FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1), '[]'), ''), p.exclusions) AS terms_exclusions,
               COALESCE(NULLIF(NULLIF((SELECT t.requirements FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1), '[]'), ''), p.requirements) AS terms_requirements
        FROM promotions p JOIN supermarkets s ON p.supermarket_id = s.id
        WHERE p.id = ? AND p.is_active = 1
          AND (p.valid_until IS NULL OR p.valid_until = '' OR p.valid_until >= ?)
          AND (p.valid_from IS NULL OR p.valid_from = '' OR p.valid_from <= ?)
        """,
        (promotion_id, today_iso, today_iso),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _format_conditions_html(promo: dict) -> str:
    lines = [
        f"📋 <b>Condiciones · {_esc(promo.get('supermarket_name'))}</b>",
        f"<b>{_esc(promo.get('title'))}</b>",
    ]
    if promo.get("store_types"):
        lines.append(f"🏪 <b>Modalidad:</b> {_esc(promo['store_types'])}")
    if promo.get("payment_method"):
        lines.append(f"💳 <b>Medio:</b> {_esc(promo['payment_method'])}")
    if promo.get("tope"):
        lines.append(f"⚠️ <b>Tope:</b> {_esc(promo['tope'])}")
    if promo.get("terms_requirements"):
        lines.append(f"✅ <b>Condiciones:</b> {_esc(promo['terms_requirements'])}")
    if promo.get("terms_exclusions"):
        lines.append(f"⛔ <b>Aplican exclusiones:</b> {_esc(promo['terms_exclusions'])}")
    raw_text = (promo.get("raw_text") or "").strip()
    if raw_text:
        lines.append(f"\n<i>T&C:</i> {_esc(raw_text[:2600])}")
    return "\n".join(lines)


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

# Callbacks internos: no se exponen como comandos de texto, solo para paginar
# la categoría elegida desde /hoy.
CALLBACK_COMMANDS = {
    **COMMANDS,
    "hoysuper": cmd_hoy_supermarkets,
    "hoyfuel": cmd_hoy_fuel,
    "missuper": cmd_mis_supermarkets,
    "misfuel": cmd_mis_fuel,
}

_CATEGORY_CALLBACKS = {
    "hoycat:supermarket": cmd_hoy_supermarkets,
    "hoycat:fuel": cmd_hoy_fuel,
    "miscat:supermarket": cmd_mis_supermarkets,
    "miscat:fuel": cmd_mis_fuel,
}


def handle_message(update: dict, user_db: UserDatabase, notifier: TelegramNotifier) -> None:
    """Procesa un message entrante. Idempotente — Telegram puede reentregar."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat_id = str(msg["chat"]["id"])
    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        from promo_questions import answer_promo_question

        # Para preguntas abiertas se consulta solo la información vigente hoy.
        # Si el chat está vinculado, la comparación usa sus medios de pago.
        user = user_db.get_user_by_telegram_chat_id(chat_id)
        methods = user_db.get_user_payment_methods(user["id"]) if user else []
        reply_text = answer_promo_question(
            text,
            _query_promotions(today_only=True, limit=500),
            methods,
        )
        if reply_text:
            notifier.send_message_to(chat_id, reply_text, parse_mode="HTML")
        return

    # Telegram permite /comando@botname — descartamos el sufijo
    head, _, args = text.partition(" ")
    cmd = head[1:].split("@", 1)[0].lower()

    handler = COMMANDS.get(cmd)
    if not handler:
        notifier.send_message_to(
            chat_id,
            f"❓ Comando desconocido: <code>{_esc(cmd)}</code>\n\nUsá /ayuda",
            parse_mode="HTML",
        )
        return

    reply_text, reply_markup = handler(chat_id, args, user_db)
    notifier.send_message_to(
        chat_id, reply_text,
        reply_markup=reply_markup or None,
        parse_mode="HTML",
    )


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

    category_handler = _CATEGORY_CALLBACKS.get(data)
    if category_handler:
        reply_text, reply_markup = category_handler(chat_id, "", user_db, page=1)
        notifier.edit_message_text(
            chat_id, message_id, reply_text,
            reply_markup=reply_markup or None,
            parse_mode="HTML",
        )
        notifier.answer_callback_query(callback_id)
        return

    filter_parts = data.split(":")
    if len(filter_parts) == 3 and filter_parts[0] == "f":
        reply_text, reply_markup = _filter_menu(filter_parts[1], filter_parts[2])
        notifier.edit_message_text(chat_id, message_id, reply_text, reply_markup=reply_markup or None, parse_mode="HTML")
        notifier.answer_callback_query(callback_id)
        return

    if len(filter_parts) == 4 and filter_parts[0] == "k":
        reply_text, reply_markup = _filter_options(filter_parts[1], filter_parts[2], filter_parts[3])
        notifier.edit_message_text(chat_id, message_id, reply_text, reply_markup=reply_markup or None, parse_mode="HTML")
        notifier.answer_callback_query(callback_id)
        return

    if len(filter_parts) == 3 and filter_parts[0] == "r":
        callback_handler = {
            ("h", "s"): cmd_hoy_supermarkets, ("h", "f"): cmd_hoy_fuel,
            ("m", "s"): cmd_mis_supermarkets, ("m", "f"): cmd_mis_fuel,
        }.get((filter_parts[1], filter_parts[2]))
        if callback_handler:
            reply_text, reply_markup = callback_handler(chat_id, "", user_db, page=1)
            notifier.edit_message_text(chat_id, message_id, reply_text, reply_markup=reply_markup or None, parse_mode="HTML")
        notifier.answer_callback_query(callback_id)
        return

    if len(filter_parts) == 5 and filter_parts[0] == "a":
        reply_text, reply_markup = _filtered_results(
            chat_id, user_db, filter_parts[1], filter_parts[2], filter_parts[3], filter_parts[4], page=1,
        )
        notifier.edit_message_text(chat_id, message_id, reply_text, reply_markup=reply_markup or None, parse_mode="HTML")
        notifier.answer_callback_query(callback_id)
        return

    if len(filter_parts) == 6 and filter_parts[0] == "pf":
        try:
            filtered_page = int(filter_parts[5])
        except ValueError:
            notifier.answer_callback_query(callback_id)
            return
        if filtered_page < 1 or filtered_page > 100:
            notifier.answer_callback_query(callback_id)
            return
        reply_text, reply_markup = _filtered_results(
            chat_id, user_db, filter_parts[1], filter_parts[2], filter_parts[3], filter_parts[4], page=filtered_page,
        )
        notifier.edit_message_text(chat_id, message_id, reply_text, reply_markup=reply_markup or None, parse_mode="HTML")
        notifier.answer_callback_query(callback_id)
        return

    if len(filter_parts) == 2 and filter_parts[0] == "terms":
        try:
            promotion_id = int(filter_parts[1])
        except ValueError:
            notifier.answer_callback_query(callback_id)
            return
        if promotion_id < 1 or promotion_id > 2_147_483_647:
            notifier.answer_callback_query(callback_id)
            return
        promo = _promotion_conditions(promotion_id)
        if promo:
            notifier.edit_message_text(chat_id, message_id, _format_conditions_html(promo), parse_mode="HTML")
        else:
            notifier.edit_message_text(chat_id, message_id, "ℹ️ Esta promoción ya no está vigente.", parse_mode="HTML")
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

    handler = CALLBACK_COMMANDS.get(cmd)
    if not handler:
        notifier.answer_callback_query(callback_id)
        return

    # Solo los handlers paginables aceptan page kwarg
    try:
        reply_text, reply_markup = handler(chat_id, extra, user_db, page=page)
    except TypeError:
        reply_text, reply_markup = handler(chat_id, extra, user_db)

    notifier.edit_message_text(
        chat_id, message_id, reply_text,
        reply_markup=reply_markup or None,
        parse_mode="HTML",
    )
    notifier.answer_callback_query(callback_id)
