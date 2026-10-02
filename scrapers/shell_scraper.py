"""
Scraper de Shell Argentina — Descuentos vigentes

La página es AEM (Adobe Experience Manager) y expone su modelo completo en JSON:
  GET https://www.shell.com.ar/conductores/descuentos-vigentes.model.json

Estructura del modelo (descubierta 2026-10):
  - Nodo organism="Tabs": model.links = etiquetas de tabs ("Todos los días",
    "Lunes", ...) y children = un Container por tab (model.title = día).
  - Cada Container tiene nodos organism="PromoSimple":
      · model.title = título promocional
      · model.text  = <p> con descuento/tope y <sup>(N)</sup> → legal N
  - Un nodo organism="PromoSimple.Text" con <ol><li> = legales 1..N.

Sin navegador ni IA: un GET, parseo determinístico y cruce card ↔ legal.
Las fechas salen del legal (la card no las tiene); el orquestador descarta
las vencidas.
"""
import asyncio
import calendar
import re
from datetime import date
from html import unescape
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from fuel_conditions import extract_fuel_conditions


MODEL_URL = 'https://www.shell.com.ar/conductores/descuentos-vigentes.model.json'
PAGE_URL = 'https://www.shell.com.ar/conductores/descuentos-vigentes.html'
_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json,text/html;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-AR,es;q=0.9',
}
_TIMEOUT = 30

_WEEKDAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
}
_MONTH_RE = '|'.join(_MONTHS)
_WEEKDAY_RE = r'lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?'

# Bancos: el orden importa (Bancor antes que "Provincia", que matchea
# "Banco Provincia de Córdoba" en el legal de Bancor).
_BANKS = [
    (r'BANCOR\b|BANCO\s+DE\s+C[OÓ]RDOBA|PROVINCIA\s+DE\s+C[OÓ]RDOBA', 'Bancor'),
    (r'BANCO\s+CIUDAD|CIUDAD\s+DE\s+BUENOS\s+AIRES', 'Banco Ciudad'),
    (r'GALICIA\b', 'Banco Galicia'),
    (r'COMAFI\b', 'Banco Comafi'),
    (r'SUPERVIELLE\b', 'Banco Supervielle'),
    (r'PATAGONIA\b', 'Banco Patagonia'),
    (r'BANCO\s+MACRO|\bMACRO\b', 'Banco Macro'),
    (r'SANTANDER', 'Banco Santander'),
    (r'\bBBVA\b', 'BBVA'),
    (r'\bICBC\b', 'ICBC'),
    (r'\bHSBC\b', 'HSBC'),
    (r'CREDICOOP', 'Banco Credicoop'),
    (r'HIPOTECARIO', 'Banco Hipotecario'),
    (r'COLUMBIA', 'Banco Columbia'),
    (r'BANCO\s+PROVINCIA|\bBAPRO\b|PROVINCIA\s+DE\s+BUENOS\s+AIRES', 'Banco Provincia'),
    (r'NACI[OÓ]N\b|\bBNA\b', 'Banco Nación'),
    (r'BRUBANK', 'Brubank'),
    (r'NARANJA', 'Naranja X'),
]

# Billeteras / programas: el primero que matchea es el "wallet" de la promo.
_WALLETS = [
    (r'\bRIPIO\b', 'Ripio'),
    (r'\bMODO\b', 'MODO'),
    (r'MERCADO\s*PAGO', 'Mercado Pago'),
    (r'CUENTA\s*DNI', 'Cuenta DNI'),
    (r'PERSONAL\s*PAY', 'Personal Pay'),
    (r'\b365\b|TARJETA\s*365|CLUB\s*CLAR[IÍ]N', 'Club Clarín 365'),
    (r'CLUB\s+EASY', 'Club Easy'),
    (r'JUMBO\s*\+|VEA\s+AHORRO', 'Jumbo+ / Vea Ahorro'),
    (r'SHELL\s*BOX', 'Shell Box'),
]

# Frases de exclusión: "no será aplicado ... a través de MercadoPago" no debe
# convertir a Mercado Pago en la billetera de la promo.
_NEGATION_RE = re.compile(
    r'\bno\s+(?:ser[aá]\s+)?(?:aplica|aplicad|v[aá]lid|incluye)|exclu[iy]|excepto|salvo', re.I
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de texto (fechas, montos)
# ─────────────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = unescape(text or '').replace('​', '').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _html_text(html: str) -> str:
    return _clean(BeautifulSoup(html or '', 'html.parser').get_text(' ', strip=True))


def _positive_sentences(text: str) -> str:
    """Quita oraciones de exclusión ("no aplica ...", "excepto ...")."""
    parts = re.split(r'(?<=[.;])\s+', text or '')
    return ' '.join(p for p in parts if not _NEGATION_RE.search(p))


def _year(y: Optional[str]) -> Optional[int]:
    if not y:
        return None
    y = int(y)
    return 2000 + y if y < 100 else y


def _safe_date(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_dates(text: str, default_year: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
    """Extrae (valid_from, valid_until) ISO de un legal en español.

    Cubre: "del 01/09/2026 al 30/09/2026", "hasta el 30/09/2026",
    "Válida el jueves 10 de septiembre", "del 1 de septiembre al 30 de
    septiembre de 2026", "los viernes del mes de septiembre de 2026" (mes
    completo), "DÍA 1 DE OCTUBRE DE 2026 HASTA ... 31 DE OCTUBRE DE 2026".
    """
    if not text:
        return None, None
    t = _clean(text).lower()
    default_year = default_year or date.today().year
    tokens = []  # (start, end, y|None, m, d|None, kind)

    for m in re.finditer(r'(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?(?![\d/])', t):
        d, mo = int(m.group(1)), int(m.group(2))
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            continue
        if not m.group(3):
            # Sin año sólo si hay contexto de vigencia ("del 1/10", "hasta 31/10")
            if not re.search(r'(?:del?|al|desde|hasta|el)\s*$', t[max(0, m.start() - 8):m.start()]):
                continue
        tokens.append((m.start(), m.end(), _year(m.group(3)), mo, d, 'day'))

    day_month = re.compile(
        r'(?<!\d)(\d{1,2})\s+(?:de(?:l)?\s+)?(?:mes\s+de\s+)?(' + _MONTH_RE + r')'
        r'(?:\s+(?:de|del)\s+(\d{4}))?'
    )
    for m in day_month.finditer(t):
        tokens.append((m.start(), m.end(), _year(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)), 'day'))

    month_span = re.compile(r'(?:mes\s+de|de|del)\s+(' + _MONTH_RE + r')(?:\s+(?:de|del)\s+(\d{4}))?')
    for m in month_span.finditer(t):
        if any(s <= m.start() < e or s < m.end() <= e for s, e, *_ in tokens):
            continue
        # "viernes de octubre", "mes de septiembre de 2026" (sin día)
        before = t[max(0, m.start() - 25):m.start()]
        if not (m.group(2) or re.search(r'(?:' + _WEEKDAY_RE + r'|mes)\s*$', before)):
            continue
        tokens.append((m.start(), m.end(), _year(m.group(2)), _MONTHS[m.group(1)], None, 'month'))

    if not tokens:
        return None, None
    tokens.sort()
    years = [tk[2] for tk in tokens if tk[2]]
    dates = []
    for s, e, y, mo, d, kind in tokens:
        y = y or (years[0] if years else default_year)
        if kind == 'month':
            last = calendar.monthrange(y, mo)[1]
            dates.append((s, _safe_date(y, mo, 1), _safe_date(y, mo, last), 'month'))
        else:
            dd = _safe_date(y, mo, d)
            dates.append((s, dd, dd, 'day'))
    dates = [x for x in dates if x[1]]
    if not dates:
        return None, None

    if len(dates) == 1:
        s, d1, d2, kind = dates[0]
        if kind == 'month':
            return d1.isoformat(), d2.isoformat()
        before = t[max(0, s - 45):s]
        if re.search(r'desde(?:\s+el)?\s*$', before):
            return d1.isoformat(), None
        if re.search(r'(?:hasta|al|vence\w*)(?:\s+el)?(?:\s+d[ií]a)?\s*$', before):
            return None, d1.isoformat()
        if re.search(r'(?:v[aá]lid[ao]s?|vigente)(?:\s+para)?\s+(?:el|los)\s+(?:(?:' + _WEEKDAY_RE + r')\s+)?$', before) \
                or re.search(r'(?:' + _WEEKDAY_RE + r')\s+$', before):
            return d1.isoformat(), d1.isoformat()
        return None, d1.isoformat()

    start = min(x[1] for x in dates)
    end = max(x[2] for x in dates)
    return start.isoformat(), end.isoformat()


def _money(raw: str) -> str:
    """'10000' / '10.000' / '13.000.-' → '$10.000'."""
    digits = re.sub(r'\D', '', (raw or '').split(',')[0])
    if not digits:
        return ''
    return '$' + f"{int(digits):,}".replace(',', '.')


def _period(window: str) -> str:
    w = window.lower()
    if re.search(r'por\s+mes|mensual|mensuales|en\s+total\s+por\s+mes', w):
        return 'mensual'
    if re.search(r'por\s+semana|semanal', w):
        return 'semanal'
    if re.search(r'quincenal', w):
        return 'quincenal'
    if re.search(r'por\s+d[ií]a|diari', w):
        return 'diario'
    if re.search(r'por\s+(?:compra|transacci[oó]n|carga)', w):
        return 'por compra'
    return ''


def _find_topes(text: str) -> List[Tuple[int, str, str]]:
    """[(pos, '$10.000', periodo)] para cada monto precedido por 'tope'."""
    out = []
    for m in re.finditer(r'tope\b([^$]{0,60}?)\$\s*([\d.]+)', text, re.I):
        amount = _money(m.group(2))
        if not amount:
            continue
        window = m.group(1) + text[m.end():m.end() + 45]
        out.append((m.start(), amount, _period(window)))
    for m in re.finditer(r'\$\s*([\d.]+)\s+en\s+total\s+por\s+(mes|semana)', text, re.I):
        out.append((m.start(), _money(m.group(1)), 'mensual' if m.group(2).lower() == 'mes' else 'semanal'))
    return out


def _period_from_legal(amount: str, legal: str) -> str:
    """Busca la periodicidad del monto en el legal (la card a veces la omite)."""
    if not legal:
        return ''
    digits = re.sub(r'\D', '', amount)
    for m in re.finditer(r'\$\s*([\d.]+)', legal):
        if re.sub(r'\D', '', m.group(1)) == digits:
            p = _period(legal[m.end():m.end() + 90])
            if p:
                return p
    for _, _, p in _find_topes(legal):
        if p:
            return p
    return ''


def _fmt_tope(amount: str, period: str) -> str:
    return f"{amount} {period}".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Scraper
# ─────────────────────────────────────────────────────────────────────────────

class ShellScraper:
    def __init__(self):
        self.name = 'Shell'
        self.url = PAGE_URL

    async def scrape(self) -> List[Dict]:
        print(f"\n🔍 Scraping {self.name}...")
        print(f"   🌐 {MODEL_URL}")
        model = await asyncio.to_thread(self._fetch_model)
        if not model:
            print(f"   ❌ {self.name}: no se pudo obtener el modelo AEM — 0 promos")
            return []
        promos = self.parse_model(model)
        for p in promos:
            entity = p['bank'] or p['wallet'] or '?'
            print(f"      + {entity:22s} | {p['discount'] or '—':32s} | {p['valid_days']:14s} "
                  f"| {p['valid_from'] or '—'} → {p['valid_until'] or '—'} | tope: {p['tope'] or '—'}")
        print(f"\n✅ {self.name}: {len(promos)} promociones")
        return promos

    def _fetch_model(self) -> Optional[dict]:
        try:
            r = requests.get(MODEL_URL, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"   ❌ Error al obtener {MODEL_URL}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Recorrido del modelo AEM
    # ─────────────────────────────────────────────────────────────────────────

    def parse_model(self, model: dict) -> List[Dict]:
        footnotes = self._parse_footnotes(model)
        print(f"   📋 {len(footnotes)} legales cargados")
        legal_years = [int(y) for y in re.findall(r'/(20\d\d)\b', ' '.join(footnotes.values()))]
        default_year = max(set(legal_years), key=legal_years.count) if legal_years else None

        promos: List[Dict] = []
        titles: Dict[str, int] = {}
        for day_label, node in self._iter_promo_nodes(model):
            for promo in self._parse_node(node, day_label, footnotes, default_year):
                # El título debe ser único por fuente (UNIQUE supermarket,title,bank)
                base = promo['title']
                n = titles.get(base, 0)
                titles[base] = n + 1
                if n:
                    promo['title'] = f"{base} ({n + 1})"
                promos.append(promo)
        return promos

    def _iter_promo_nodes(self, model: dict):
        """Yield (día del tab, nodo PromoSimple) recorriendo el árbol."""
        def walk(node, day):
            if not isinstance(node, dict):
                return
            org = node.get('organism') or ''
            title = (node.get('model') or {}).get('title') if isinstance(node.get('model'), dict) else None
            if org == 'Container' and title and self._normalize_days(title):
                day = title
            if org == 'PromoSimple':
                yield day or 'Todos los días', node
            for child in node.get('children') or []:
                yield from walk(child, day)
        yield from walk(model, None)

    def _parse_footnotes(self, model: dict) -> Dict[int, str]:
        """Busca el PromoSimple.Text con la <ol> de legales → {1: texto, ...}."""
        best: Dict[int, str] = {}

        def walk(node):
            nonlocal best
            if isinstance(node, dict):
                if node.get('organism') == 'PromoSimple.Text':
                    html = (node.get('model') or {}).get('text') or ''
                    soup = BeautifulSoup(html, 'html.parser')
                    for ol in soup.find_all('ol'):
                        lis = ol.find_all('li', recursive=False)
                        if len(lis) > len(best):
                            best = {i: _clean(li.get_text(' ', strip=True)) for i, li in enumerate(lis, 1)}
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(model)
        return best

    # ─────────────────────────────────────────────────────────────────────────
    # Parseo de cada card
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_node(self, node: dict, day_label: str, footnotes: Dict[int, str],
                    default_year: Optional[int]) -> List[Dict]:
        m = node.get('model') or {}
        headline = _clean(m.get('title') or '')
        html = m.get('text') or ''
        image = m.get('image') or {}
        img_url, img_alt = image.get('src') or '', image.get('alt') or ''
        node_key = (node.get('id') or '').split('/tabs/')[-1] or headline
        refs = [int(n) for n in re.findall(r'<sup>\s*\(?\s*(\d+)\s*\)?\s*</sup>', html)]
        card = _html_text(re.sub(r'<sup>.*?</sup>', ' ', html, flags=re.S))
        card = re.sub(r'\s+([.,)])', r'\1', card)
        if not headline and not card:
            return []

        legals = [footnotes[n] for n in refs if n in footnotes]
        common = dict(
            headline=headline, card=card, day_label=day_label, img_url=img_url,
            img_alt=img_alt, default_year=default_year,
        )

        # Varias legales con beneficios distintos (Galicia 10% / Éminent 15% /
        # Haberes 10%) → una promo por legal. Si comparten el mismo % (Comafi
        # por cartera) queda una sola promo con tope por tramo.
        legal_pcts = [self._legal_pct(l) for l in legals]
        if len(legals) > 1 and len(set(legal_pcts)) > 1 and all(legal_pcts):
            out = []
            for n, legal, pct in zip(refs, legals, legal_pcts):
                out.append(self._build(**common, legals=[legal], refs=[n], node_key=node_key,
                                       split_pct=pct))
            return [p for p in out if p]
        promo = self._build(**common, legals=legals, refs=refs, node_key=node_key)
        return [promo] if promo else []

    def _build(self, headline, card, day_label, img_url, img_alt, default_year,
               legals, refs, node_key, split_pct: Optional[str] = None) -> Optional[Dict]:
        legal = ' '.join(legals)
        legal_pos = _positive_sentences(legal)
        head_card = f"{headline} {card}"

        bank = self._identify(_BANKS, head_card) or self._identify(_BANKS, img_alt) \
            or self._identify(_BANKS, legal_pos)
        wallet = self._identify(_WALLETS, _positive_sentences(head_card)) \
            or self._identify(_WALLETS, legal_pos)

        if split_pct:
            qualifier = self._legal_qualifier(legal)
            discount = f"{split_pct}%"
            if re.search(r'\bextra\b|adicional', legal, re.I) or (
                    qualifier and re.search(re.escape(qualifier) + r'.{0,80}?extra', card, re.I)):
                discount += ' extra'
            discount = f"{discount} {qualifier}".strip() if qualifier else discount
            topes = _find_topes(legal)
            tope = _fmt_tope(topes[0][1], topes[0][2]) if topes else ''
        else:
            discount = self._card_discount(card)
            if not discount:
                discount = f"{self._legal_pct(legal)}%" if self._legal_pct(legal) else ''
            if not discount and re.search(r'duplic\w+\s+(?:tus\s+)?puntos', card, re.I):
                discount = 'Puntos x2'
            tope = self._card_tope(card, legal)

        # Fechas = unión de los legales referenciados (cada uno trae su vigencia)
        ranges = [parse_dates(l, default_year) for l in legals]
        froms = [f for f, _ in ranges if f]
        untils = [u for _, u in ranges if u]
        valid_from = min(froms) if froms else None
        valid_until = max(untils) if untils and len(untils) == len(ranges) else None

        if not (discount or bank or wallet):
            return None

        card_type = self._card_type(card) or self._card_type(legal_pos)
        payment_method = None
        if wallet == 'MODO':
            payment_method = 'MODO BNA+' if re.search(r'BNA\s*\+', head_card + legal, re.I) else 'QR MODO'
        elif re.search(r'(?:trav[eé]s\s+de|app|con|desde)\s+(?:la\s+app\s+)?shell\s*box|shell\s*box\s+(?:como\s+medio|para\s+pagar)',
                       head_card + ' ' + legal_pos, re.I):
            payment_method = 'App Shell Box'
            if wallet == 'Ripio':
                payment_method = 'App Shell Box (tarjeta prepaga Ripio)'
                card_type = card_type or 'Prepaga'

        product = ''
        low = card.lower()
        if 'lubricante' in low and not re.search(r'v-power|combustible|nafta', low):
            product = 'lubricantes'
        elif 'v-power' in low and 'lubricante' not in low:
            product = 'V-Power'

        days = self._normalize_days(day_label) or day_label
        entity = bank or wallet or 'Shell'
        if bank and wallet and wallet not in ('MODO',):
            entity = f"{bank} + {wallet}"
        title_disc = discount if len(discount) <= 40 else discount.split(' (')[0]
        title = f"{entity} {title_disc}" + (f" en {product}" if product else '') + f" - {days}"

        requirements, exclusions = extract_fuel_conditions(legal)
        return {
            'supermarket':    self.name,
            'title':          title,
            'description':    f"{headline}: {card}"[:400] if headline else card[:400],
            'discount':       discount,
            'bank':           bank,
            'wallet':         wallet,
            'card_type':      card_type,
            'payment_method': payment_method,
            'tope':           tope or None,
            'valid_days':     days,
            'valid_from':     valid_from,
            'valid_until':    valid_until,
            'exclusions':     ' | '.join(exclusions),
            'requirements':   ' | '.join(requirements),
            'terms_raw':      legal or card,
            'image_url':      img_url,
            'url':            self.url,
            'source_id':      f"shell:{node_key}:{'-'.join(map(str, refs)) or 0}",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Extractores
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _identify(patterns, text: str) -> Optional[str]:
        t = (text or '').upper()
        for pattern, name in patterns:
            if re.search(pattern, t):
                return name
        return None

    @staticmethod
    def _legal_pct(legal: str) -> Optional[str]:
        m = re.search(r'(\d{1,2})\s*%\s*(?:\([^)]*\)\s*)?de\s+(?:descuento|ahorro|bonificaci[oó]n|reintegro)', legal or '', re.I)
        if not m:
            m = re.search(r'(?:descuento|ahorro|bonificaci[oó]n|reintegro)\s+del?\s+(\d{1,2})\s*%', legal or '', re.I)
        return m.group(1) if m else None

    @staticmethod
    def _legal_qualifier(legal: str) -> str:
        m = re.search(r'para\s+clientes\s+(?:Galicia\s+)?(?:,\s*)?(?:para\s+clientes\s+)?'
                      r'((?:Galicia\s+)?(?:[ÉE]minent|Haberes|Plan\s+Sueldo|Black|Premium|Platinum|Singular|Plus)\b)',
                      legal or '', re.I)
        if not m:
            # "para clientes Galicia, para Clientes Éminent"
            m = re.search(r'Clientes\s+([ÉE]minent|Haberes)', legal or '', re.I)
        return m.group(1).replace('Galicia ', '') if m else ''

    @staticmethod
    def _clean_qualifier(q: str) -> str:
        q = re.sub(r'\b(?:tarjetas?|clientes?|Mastercard|Visa|del?|tus?)\b', ' ', q, flags=re.I)
        q = re.sub(r'\s+(?:o|y)\s+', '/', q.strip())
        return re.sub(r'\s+', ' ', q).strip(' ,/')

    def _card_discount(self, card: str) -> str:
        pct_re = re.compile(r'(\d{1,2})\s*%')
        hits = list(pct_re.finditer(card))
        if not hits:
            return ''
        main = hits[0].group(1)
        if len(hits) == 1:
            after = card[hits[0].end():hits[0].end() + 30].lower()
            return f"{main}% reintegro" if after.strip().startswith(('de reintegro', 'reintegro')) else f"{main}%"
        extras = []
        for h in hits[1:]:
            before = card[max(0, h.start() - 110):h.start()]
            after = card[h.end():h.end() + 60]
            cond = re.search(r'si\s+(?:ten[eé]s|sos)\s+(.{3,60}?),', before, re.I)
            if cond:
                qual = self._clean_qualifier(cond.group(1))
                if re.search(r'es\s+(?:de\s+)?(?:un\s+)?$', before, re.I) or re.search(r'beneficio[^,]*es', before, re.I):
                    extras.append(f"({h.group(1)}% {qual})")
                else:
                    extras.append(f"(+{h.group(1)}% {qual})")
            elif re.search(r'adem[aá]s|adicional|extra', before[-60:] + after[:20], re.I):
                tag = ''
                if re.search(r'UXD|cripto', after, re.I):
                    tag = ' UXD'
                cc = re.search(r'tarjeta\s+de\s+(cr[eé]dito\s+\w+)', after, re.I)
                if cc:
                    g = cc.group(1)
                    tag = f" ({g[0].upper()}{g[1:]})"
                extras.append(f"+ {h.group(1)}% reintegro{tag}")
            else:
                pcts = sorted({int(x.group(1)) for x in hits})
                # Mismo % para todos los tramos (Comafi por cartera) → "20%"
                return f"{main}%" if len(pcts) == 1 else f"Hasta {pcts[-1]}%"
        return ' '.join([f"{main}%"] + extras)

    def _card_tope(self, card: str, legal: str) -> str:
        if re.search(r'sin\s+tope', card, re.I):
            return 'Sin tope'
        topes = _find_topes(card)
        if not topes:
            topes = _find_topes(legal)
            if not topes:
                return ''
            return _fmt_tope(topes[0][1], topes[0][2])
        topes = [(pos, amt, per or _period_from_legal(amt, legal)) for pos, amt, per in topes]

        # Topes por tramo de tarjeta: "con tarjetas Global y Classic (tope semanal $6.000)"
        tiers = []
        for m in re.finditer(r'con\s+(?:tarjetas\s+)?([A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóú ]{2,40}?)\s*\(\s*tope[^$)]*\$\s*([\d.]+)\)', card):
            qual = self._clean_qualifier(m.group(1))
            if re.search(r'[ÚU]nico', card[max(0, m.start() - 60):m.start()]):
                qual = f"Único {qual}"
            tiers.append((qual, _money(m.group(2)), _period(card[m.start():m.end()]) or _period_from_legal(m.group(2), legal)))
        if len({amt for _, amt, _ in tiers}) > 1:
            grouped: Dict[Tuple[str, str], List[str]] = {}
            for qual, amt, per in tiers:
                grouped.setdefault((amt, per), []).append(qual)
            return '; '.join(f"{_fmt_tope(a, p)} ({'/'.join(qs)})" for (a, p), qs in grouped.items())

        first = topes[0]
        distinct = {amt for _, amt, _ in topes}
        if len(distinct) == 1:
            return _fmt_tope(first[1], first[2])
        # Tope adicional de un tramo condicional ("si sos Plan Sueldo ... tope $5.000")
        cond = re.search(r'si\s+sos\s+(.{3,60}?),', card, re.I)
        if cond and len(topes) == 2:
            qual = self._clean_qualifier(cond.group(1))
            return f"{_fmt_tope(first[1], first[2])} (+{_fmt_tope(topes[1][1], topes[1][2])} {qual})"
        best = max(topes, key=lambda x: int(re.sub(r'\D', '', x[1])))
        return f"Según producto (hasta {_fmt_tope(best[1], best[2])})"

    @staticmethod
    def _card_type(text: str) -> Optional[str]:
        t = (text or '').lower()
        credit = bool(re.search(r'cr[eé]dito', t))
        debit = bool(re.search(r'd[eé]bito', t))
        if credit and debit:
            return 'Crédito, Débito'
        if credit:
            return 'Crédito'
        if debit:
            return 'Débito'
        if re.search(r'prepaga', t):
            return 'Prepaga'
        return None

    @staticmethod
    def _normalize_days(label: str) -> Optional[str]:
        low = (label or '').lower().strip()
        if 'todos los d' in low:
            return 'Todos los días'
        if re.search(r'lunes\s+a\s+viernes', low):
            return 'Lunes, Martes, Miércoles, Jueves, Viernes'
        found = []
        for wd in _WEEKDAYS:
            stem = wd.lower().replace('é', '[eé]').replace('á', '[aá]')
            if re.search(r'\b' + stem, low):
                found.append(wd)
        return ', '.join(found) or None
