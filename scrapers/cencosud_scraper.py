#!/usr/bin/env python3
"""
Scraper de Cencosud (Jumbo) - Promociones Bancarias

La página https://www.jumbo.com.ar/descuentos-del-dia se arma desde un único
documento de VTEX Master Data (entidad JN, id "bankDiscount"). Su campo `value`
es un JSON string con ~200 promos compartidas entre Jumbo, Disco y Vea.

Flujo:
  1. GET /api/dataentities/JN/documents/bankDiscount (requests, sin navegador).
  2. Filtrar las promos del sitio Jumbo ('jumboargentinaio' en websites) vigentes
     hoy (dateStart <= ahora <= dateEnd, epoch).
  3. Una promo por item: el item ya trae todos sus días (antes se scrapeaba el
     DOM día por día y el dedup cruzado dejaba un solo día por promo).

Campos útiles del item: banks[].name, discount ("24.99", "11.99" → se redondea),
discountText ("cuotas sin interés", "%", ", 6 y 12 Cuotas..."), installmentsText
(subtítulo de la card), info (legal corto), legals (legal completo), isExclusive
("Exclusivo Online"), paymentMethod (Crédito/Débito/Billetera Virtual).
days: "1".."6" = Lunes..Sábado (el sitio no tiene pestaña Domingo).
"""
import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


_API_URL = 'https://www.jumbo.com.ar/api/dataentities/JN/documents/bankDiscount'
_WEBSITE = 'jumboargentinaio'
_HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
}
_AR_TZ = timezone(timedelta(hours=-3))
_DAY_NAMES = {
    '0': 'Domingo', '1': 'Lunes', '2': 'Martes', '3': 'Miércoles',
    '4': 'Jueves', '5': 'Viernes', '6': 'Sábado', '7': 'Domingo',
}
_DAY_ORDER = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

# nombre en la API (normalizado) → (entidad para el título, bank, wallet, payment_method)
_ENTITIES = {
    'visa y master': ('Visa y Mastercard', None, None, 'Tarjetas de crédito Visa y Mastercard bancarias'),
    'cencopay': ('CencoPay', 'CencoPay', None, 'Tarjeta de crédito CencoPay'),
    'cencopay cuenta': ('CencoPay Cuenta', 'CencoPay', None, 'CencoPay Cuenta (QR / cuenta digital)'),
    'tarjeta naranja x': ('Naranja X', 'Naranja X', None, None),
    'naranja x': ('Naranja X', 'Naranja X', None, None),
    'nacion': ('Banco Nación', 'Banco Nación', None, None),
    'banco nacion': ('Banco Nación', 'Banco Nación', None, None),
    'banco hipotecario': ('Banco Hipotecario', 'Banco Hipotecario', 'MODO', 'QR MODO / App BH'),
    'supervielle': ('Banco Supervielle', 'Banco Supervielle', None, None),
    'banco comafi': ('Banco Comafi', 'Banco Comafi', None, None),
    'banco patagonia': ('Banco Patagonia', 'Banco Patagonia', None, None),
    'banco cordoba': ('Bancor', 'Bancor', None, 'Tarjeta Cordobesa'),
    'banco macro': ('Banco Macro', 'Banco Macro', None, None),
    'banco galicia': ('Banco Galicia', 'Banco Galicia', None, None),
    'banco ciudad': ('Banco Ciudad', 'Banco Ciudad', None, None),
    'banco provincia': ('Banco Provincia', 'Banco Provincia', None, None),
    'tarjeta sol': ('Tarjeta Sol', 'Tarjeta Sol', None, None),
    'modo': ('MODO', None, 'MODO', 'MODO'),
    'mercado pago': ('Mercado Pago', None, 'Mercado Pago', None),
    'cuenta dni': ('Cuenta DNI', 'Banco Provincia', 'Cuenta DNI', 'Cuenta DNI'),
    'amex': ('American Express', 'American Express', None, 'American Express'),
    'american express': ('American Express', 'American Express', None, 'American Express'),
    'medios de pago': ('Jubilados', None, None, 'Todos los medios de pago'),
    'club rio negro': ('Club Río Negro', 'Club Río Negro', None, 'Credencial Club Río Negro'),
    'club la voz': ('Club La Voz', 'Club La Voz', None, 'Credencial Club La Voz'),
    'club la gaceta': ('Club La Gaceta', 'Club La Gaceta', None, 'Credencial Club La Gaceta'),
    'club la capital': ('Club La Capital', 'Club La Capital', None, 'Credencial Club La Capital'),
    'club la nacion': ('Club La Nación', 'Club La Nación', None, 'Credencial Club La Nación'),
    'andes pass': ('Andes Pass', 'Andes Pass', None, 'Credencial Andes Pass'),
}


def _norm(text: str) -> str:
    text = (text or '').strip().lower()
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'), ('ñ', 'n')):
        text = text.replace(a, b)
    return re.sub(r'\s+', ' ', text)


def _clean(text: Any) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def _fmt_amount(raw: str) -> Optional[str]:
    digits = re.sub(r'[^\d]', '', raw.split(',')[0])
    if not digits or int(digits) <= 0:
        return None
    return f"${int(digits):,}".replace(',', '.')


class CencosudScraper:
    def __init__(self):
        self.name = 'Jumbo (Cencosud)'
        self.base_url = 'https://www.jumbo.com.ar/descuentos-del-dia'

    async def scrape(self) -> List[Dict]:
        print(f"\n🔍 Scraping {self.name}...")
        print(f"   🌐 API: {_API_URL}")
        try:
            items = await asyncio.to_thread(self._fetch_items)
        except Exception as e:
            print(f"   ⚠️ No se pudo consultar bankDiscount: {type(e).__name__}")
            return []

        promotions = self.parse_items(items)
        print(f"✅ {self.name}: {len(promotions)} promociones encontradas")
        return promotions

    @staticmethod
    def _fetch_items() -> List[Dict]:
        import requests
        response = requests.get(
            _API_URL,
            params={'_fields': 'value,id', 'an': 'jumboargentina'},
            headers=_HTTP_HEADERS,
            timeout=(8, 30),
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        value = payload.get('value') if isinstance(payload, dict) else None
        items = json.loads(value) if isinstance(value, str) else value
        if not isinstance(items, list):
            raise ValueError('formato inesperado')
        return items

    # ──────────────────────────────────────────────────────────
    # Parsing
    # ──────────────────────────────────────────────────────────

    def parse_items(self, items: List[Dict], now: Optional[float] = None,
                    website: str = _WEBSITE) -> List[Dict]:
        now = time.time() if now is None else now
        promotions: List[Dict] = []
        for item in items:
            if not isinstance(item, dict) or website not in (item.get('websites') or []):
                continue
            try:
                start, end = int(item.get('dateStart') or 0), int(item.get('dateEnd') or 0)
            except (TypeError, ValueError):
                continue
            if not (start <= now <= end):
                continue
            try:
                promo = self._parse_item(item, start, end)
            except Exception as e:  # un item raro no tira abajo la corrida
                print(f"   ⚠️ Item ignorado: {e}")
                continue
            if promo:
                promotions.append(promo)
        return self._ensure_unique_titles(promotions)

    def _parse_item(self, item: Dict, start: int, end: int) -> Optional[Dict]:
        banks = [b for b in (item.get('banks') or []) if isinstance(b, dict) and _clean(b.get('name'))]
        raw_entity = _clean(banks[0]['name']) if banks else ''
        subtitle = _clean(item.get('installmentsText'))
        info = _clean(item.get('info'))
        legals = _clean(item.get('legals'))
        full_text = f"{subtitle}. {info}. {legals}"

        discount = self._format_discount(item.get('discount'), item.get('discountText'), full_text)
        if not discount:
            return None

        entity, bank, wallet, payment_method = self._entity(raw_entity)
        card_type = self._card_type(item.get('paymentMethod'), f"{subtitle} {info}", subtitle)
        if not payment_method and entity == 'Naranja X':
            payment_method = 'Tarjeta de crédito Naranja X' if card_type == 'Crédito' else 'Tarjetas Naranja X'

        valid_days = self._valid_days(item.get('days') or [], full_text)
        store_types = self._store_types(item, f"{subtitle}. {info}" if info else legals, legals)

        requirements: List[str] = []
        qualifier = self._qualifier(subtitle, discount)
        if entity == 'Jubilados':
            requirements.append('Jubilados, pensionados y mayores de 60 años (presentar documentación / Jumbo+)')
            m = re.search(r'(\d+)\s*%\s*con\s+cencopay', subtitle, re.I)
            if m:
                qualifier = f"({m.group(1)}% con CencoPay)"
        if re.search(r'jubilad', subtitle + info, re.I) and entity != 'Jubilados':
            requirements.append('Exclusivo jubilados')
            qualifier = qualifier or 'Jubilados'
        branches = re.search(r'en las sucursales de ([^.]+?)\.', info, re.I)
        if branches:
            requirements.append(f"Sucursales de {branches.group(1).strip()}")
        local = re.search(r'EN (?:EL|LOS) LOCAL(?:ES)? (JUMBO [^,.]+?)(?:,| Y EN| EN EL SITIO)', info, re.I)
        if local:
            requirements.append(f"Válido en {local.group(1).title()} y jumbo.com.ar")
        if entity == 'Banco Patagonia':
            brand = self._card_brand(subtitle)
            qualifier = brand or qualifier

        title = entity + f" {discount}"
        if qualifier:
            title += f" {qualifier}"
        if store_types == 'Online':
            title += ' (Online)'
        title += f" - {valid_days}"

        exclusions = []
        m = re.search(r'(?:NO INCLUYE|SE EXCLUYE[N]?|EXCLUYE)\s*:?\s*([^.]{5,600})', f"{info}. {legals}", re.I)
        if m:
            exclusions.append(m.group(1).strip())

        valid_from = datetime.fromtimestamp(start, _AR_TZ).date().isoformat()
        # dateEnd suele ser 23:59 (inclusive) o 00:00 del día siguiente (exclusivo).
        valid_until = (datetime.fromtimestamp(end, _AR_TZ) - timedelta(seconds=1)).date().isoformat()

        key = '|'.join([raw_entity, str(item.get('discount')), _clean(item.get('discountText')),
                        subtitle, str(item.get('dateStart')), ','.join(item.get('days') or [])])
        return {
            'title': title[:200],
            'discount': discount,
            'bank': bank,
            'wallet': wallet,
            'card_type': card_type,
            'payment_method': payment_method,
            'store_types': store_types,
            'valid_days': valid_days,
            'valid_from': valid_from,
            'valid_until': valid_until,
            'url': self.base_url,
            'image_url': (banks[0].get('image') or None) if banks else None,
            'terms_raw': legals or info,
            'tope': self._extract_tope(subtitle, info, '' if entity == 'Jubilados' else legals),
            'min_purchase': self._extract_min_purchase(f"{subtitle}. {info}. {legals}"),
            'acumulable': self._acumulable(f"{info}. {legals}"),
            'exclusions': exclusions,
            'requirements': requirements,
            'source_id': 'jumbo-' + hashlib.sha1(key.encode('utf-8')).hexdigest()[:12],
        }

    @staticmethod
    def _entity(raw: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        key = _norm(raw)
        if key in _ENTITIES:
            return _ENTITIES[key]
        # Nombre nuevo: se usa tal cual (con mayúscula inicial) como banco.
        name = raw.strip()
        name = name[0].upper() + name[1:] if name else 'Medios de pago'
        return name, name, None, None

    @staticmethod
    def _card_type(payment_methods: Any, text: str, subtitle: str = '') -> Optional[str]:
        sub = subtitle.lower()
        has_credit, has_debit = bool(re.search(r'cr[ée]dito', sub)), bool(re.search(r'd[ée]bito', sub))
        if has_credit != has_debit:
            return 'Crédito' if has_credit else 'Débito'
        keys = list(payment_methods.keys()) if isinstance(payment_methods, dict) else []
        types = [t for t in ('Crédito', 'Débito') if t in keys]
        if not types:
            low = text.lower()
            if re.search(r'd[ée]bito', low):
                types.append('Débito')
            if re.search(r'cr[ée]dito', low):
                types.insert(0, 'Crédito')
        return ', '.join(types) or None

    @staticmethod
    def _format_discount(raw_value: Any, raw_text: Any, full_text: str) -> str:
        """'24.99' → 25 (el sitio carga 24.99 para mostrar 25), '11.99' cuotas → 12."""
        try:
            value = float(str(raw_value).replace(',', '.'))
        except (TypeError, ValueError):
            return ''
        if value <= 0:
            return ''
        number = int(round(value))
        text = _clean(raw_text)
        low = _norm(text)

        if 'cuota' in low:
            # "3" + ", 6 y 12 Cuotas sin Interés" / "y 4 cuotas" / "6 y 12 Cuotas"
            pre = re.split(r'cuotas?', text, flags=re.I)[0]
            extra = re.findall(r'\d+', pre)
            if '%' in pre:
                return f"{number}% y {' y '.join(extra)} cuotas sin interés" if extra else f"{number}%"
            nums = [str(number)] + extra
            if len(nums) == 1:
                joined = nums[0]
            else:
                joined = ', '.join(nums[:-1]) + ' y ' + nums[-1]
            return f"{joined} cuotas sin interés"
        if 'mil' in low and '$' in text:
            return f"${number * 1000:,}".replace(',', '.') + ' reintegro'
        if low in ('', '%') or low.startswith('%'):
            # Sólo "reintegro" si el texto lo dice para ESTE porcentaje (los legales de
            # Jumbo agrupan varias promos y mencionan reintegros de otras).
            explicit = (
                rf'\b{number}\s*%\s*(?:de\s+)?reintegro|reintegro\s*(?:\(cashback\)\s*)?del\s*{number}\s*%|'
                r'^\W*de\s+reintegro|se\s+otorgar[áa]\s+un\s+reintegro'
            )
            if re.search(explicit, full_text, re.I):
                return f"{number}% reintegro"
            return f"{number}%"
        return f"{number}%"

    @staticmethod
    def _qualifier(subtitle: str, discount: str) -> Optional[str]:
        """Subtítulo de la card cuando describe el alcance ('en Electro', 'en Tv y más')."""
        sub = subtitle.strip(' .')
        if not sub:
            return None
        if '$' in sub:
            return None  # ya queda en tope / min_purchase
        if re.match(r'en\s', sub, re.I) and len(sub) <= 60:
            rest = sub[3:].strip()
            if rest.isupper():
                rest = rest.capitalize()
            return f"en {rest}"
        if '%' in discount and re.match(r'\d+\s+cuotas\s+sin\s+inter', sub, re.I):
            return '+ ' + sub.lower()
        return None

    @staticmethod
    def _card_brand(subtitle: str) -> Optional[str]:
        low = subtitle.lower()
        if 'american express' in low or 'amex' in low:
            return 'American Express'
        if 'visa' in low:
            return 'Visa'
        if 'mastercard' in low:
            return 'Mastercard'
        return None

    @staticmethod
    def _valid_days(days: List[Any], text: str) -> str:
        names = {_DAY_NAMES[str(d).strip()] for d in days if str(d).strip() in _DAY_NAMES}
        if not names:
            return 'Todos los días'
        # El sitio sólo tiene pestañas Lunes..Sábado: los "todos los días" vienen como 1..6
        # y las promos de fin de semana suelen marcar sólo el sábado.
        if 'Sábado' in names and re.search(r'domingos?\b', text, re.I) and not re.search(
                r'(?:no|excepto|salvo)\s+(?:v[aá]lid[oa]\s+)?(?:los\s+)?domingos?', text, re.I):
            names.add('Domingo')
        if {'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'} <= names:
            return 'Todos los días'
        return ', '.join(d for d in _DAY_ORDER if d in names)

    @staticmethod
    def _store_types(item: Dict, text: str, legals: str = '') -> str:
        """Canal según la card (subtítulo + legal corto); el legal completo agrupa varias promos."""
        upper = text.upper()
        presencial_re = r'EXCLUSIVO\s+(?:PARA\s+)?(?:VENTAS?\s+|COMPRAS?\s+)?PRESENCIAL(?!\s+Y)'
        presencial_only = re.search(
            presencial_re + r'|SOLO\s+(?:PARA\s+)?VENTA\s+PRESENCIAL|'
            r'V[AÁ]LIDO\s+PRESENCIAL|EXCLUSIVO\s+COMPRAS\s+PRESENCIALES', upper)
        online_only = re.search(r'EXCLUSIVO\s+(?:PARA\s+)?(?:VENTA\s+|COMPRAS?\s+)?ONLINE|SOLO\s+VENTA\s+NO\s+PRESENCIAL|'
                                r'EN\s+LOS\s+SITIOS\s+WEB\s+OBTENIENDO', upper)
        mentions_web = re.search(r'ONLINE|SITIO|WEB|JUMBO\.COM\.AR', upper)
        if presencial_only and not online_only:
            return 'Tiendas'
        if item.get('isExclusive') or online_only:
            # El sello "Exclusivo Online" a veces contradice el legal ("EXCLUSIVO VENTA
            # PRESENCIAL", p. ej. 30% CencoPay Cuenta con QR): manda el legal.
            if not online_only and re.search(presencial_re, legals.upper()):
                return 'Tiendas'
            return 'Online'
        if re.search(r'COMPRAS?\s+PRESENCIAL', upper) and not mentions_web:
            return 'Tiendas'
        return 'Online, Tiendas'

    # ──────────────────────────────────────────────────────────
    # Tope / compra mínima / acumulable
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _tope_in(text: str) -> Tuple[Optional[str], Optional[str]]:
        for m in re.finditer(r'\btopes?\b', text, re.I):
            window = text[m.start():m.start() + 160]
            amount = re.search(r'\$\s*(\d{1,3}(?:[.,]\d{3})+|\d{3,})|\b(\d{1,3}(?:\.\d{3})+)\b', window)
            if not amount:
                continue
            raw = amount.group(1) or amount.group(2)
            context = window[:amount.end() + 70].lower()
            if re.search(r'diari|por d[ií]a\b', context):
                period = 'diario'
            elif re.search(r'semana|semanal', context):
                period = 'semanal'
            elif re.search(r'\bmes\b|mensual', context):
                period = 'mensual'
            elif 'vigencia' in context:
                period = 'por vigencia'
            else:
                period = None
            return _fmt_amount(raw), period
        return None, None

    def _extract_tope(self, subtitle: str, info: str, legals: str) -> Optional[str]:
        for text in (subtitle, info, legals):
            if re.search(r'sin\s+tope', text, re.I):
                return 'Sin tope'
            amount, period = self._tope_in(text)
            if amount:
                if not period:
                    # el período suele estar en el legal ("$15.000 POR MES")
                    for other in (info, legals):
                        other_amount, other_period = self._tope_in(other)
                        if other_amount == amount and other_period:
                            period = other_period
                            break
                    if not period and re.search(r'tope\s+mensual', f"{info} {legals}", re.I):
                        period = 'mensual'
                return f"{amount} {period}" if period else amount
        return None

    @staticmethod
    def _extract_min_purchase(text: str) -> Optional[str]:
        m = re.search(
            r'(?:m[ií]nimo\s+de\s+compra(?:\s+de)?|a\s+partir\s+de|superiores?\s+a(?:\s+total\s+de)?|'
            r'mayores?\s+a)\s*\$\s*(\d[\d.,]*)', text, re.I)
        return _fmt_amount(m.group(1)) if m else None

    @staticmethod
    def _acumulable(text: str) -> Optional[bool]:
        if re.search(r'no\s+(?:es\s+)?acumulable', text, re.I):
            return False
        if re.search(r'acumulable', text, re.I):
            return True
        return None

    @staticmethod
    def _ensure_unique_titles(promotions: List[Dict]) -> List[Dict]:
        seen: Dict[str, int] = {}
        for promo in promotions:
            title = promo['title']
            if title in seen:
                seen[title] += 1
                promo['title'] = f"{title} ({seen[title]})"
            else:
                seen[title] = 1
        return promotions
