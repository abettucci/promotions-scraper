#!/usr/bin/env python3
"""
Scraper de Más Online (ChangoMás) - Promociones Bancarias

La página https://www.masonline.com.ar/promociones-bancarias es una app VTEX
(valtech.gdn-banks-promotions) que arma las tarjetas desde dos consultas
GraphQL persistidas:
- GetPromos: un documento por promo con título, subtítulo (tope / mínimo y un
  código único como "(MP3)"), % o cuotas, flags por día de la semana, canal
  (market = sólo tiendas, express = tiendas + online), vigencia y legal.
- GetBanks: idBank → nombre de la entidad.

Consumimos esos JSON directo (sin navegador ni IA) y normalizamos al contrato
del orquestador. Las fechas puntuales que publica el legal (p. ej. "sábado
24/10/26, 28/11/26 y 26/12/26") van a valid_from/valid_until y al título.
"""
import asyncio
import base64
import calendar
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import requests

from terms_parser import TermsParser


GRAPHQL_URL = 'https://www.masonline.com.ar/_v/public/graphql/v1'
ACCOUNT = 'masonlineprod'
SENDER = 'valtech.gdn-banks-promotions@0.x'
PROVIDER = 'vtex.store-graphql@2.x'
HASH_GET_PROMOS = '1a071ebc5dc407a3f65e687b0f4c0a3b8d12a0c45d8d11370075c3b2a505251c'
HASH_GET_BANKS = '968d464317be357766de0e3beb313a55e0ebf7f45f2ef4a02c99fdf4ebca0876'

# La API guarda fechas en UTC a las 00:00; en Argentina eso es el día anterior
# 21:00, que es justamente el último día vigente cuando active_to es exclusivo.
ART = timezone(timedelta(hours=-3))

DAY_FIELDS = [
    ('monday', 'Lunes'), ('tuesday', 'Martes'), ('wednesday', 'Miércoles'),
    ('thursday', 'Jueves'), ('friday', 'Viernes'), ('saturday', 'Sábado'),
    ('sunday', 'Domingo'),
]
DAY_NAMES = [name for _, name in DAY_FIELDS]
PLURAL_DAYS = {'Sábado': 'Sábados', 'Domingo': 'Domingos'}

MONTHS = {
    'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
    'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'SETIEMBRE': 9, 'OCTUBRE': 10,
    'NOVIEMBRE': 11, 'DICIEMBRE': 12,
}
_MONTH_RE = '(?:' + '|'.join(MONTHS) + ')'
# Textos ya normalizados (mayúsculas, sin tildes).
_WEEKDAY_RE = r'(?:LUNES|MARTES|MIERCOLES|JUEVES|VIERNES|SABADOS?|DOMINGOS?)'
_WEEKDAY_INDEX = {
    'LUNES': 0, 'MARTES': 1, 'MIERCOLES': 2, 'JUEVES': 3, 'VIERNES': 4,
    'SABADO': 5, 'SABADOS': 5, 'DOMINGO': 6, 'DOMINGOS': 6,
}

# Entidades publicadas en GetBanks → nombres normalizados del contrato.
# label: cómo se nombra en el título; channel: medio por el que se paga.
ENTITIES = {
    'masclub': {'label': 'MásClub', 'payment': 'Todos los medios de pago',
                'requirement': 'Exclusiva para socios de MásClub'},
    'mercado pago': {'wallet': 'Mercado Pago', 'channel': 'QR Mercado Pago'},
    # Una sola fila para "todas las billeteras": el legal la procesa con el
    # QR interoperable de Mercado Pago, por eso se menciona en payment_method
    # (así la encuentra quien filtra por Mercado Pago sin inventar un fan-out).
    'billeteras virtuales': {'wallet': 'Billeteras virtuales (QR)',
                             'channel': 'QR de cualquier billetera virtual (procesado por Mercado Pago)'},
    'banco patagonia': {'bank': 'Banco Patagonia'},
    'banco nacion bna': {'bank': 'Banco Nación', 'channel': 'QR MODO BNA+'},
    'buepp banco ciudad': {'bank': 'Banco Ciudad', 'channel': 'QR MODO (App Ciudad o Buepp)'},
    'banco credicoop modo': {'bank': 'Banco Credicoop', 'channel': 'QR MODO (Credicoop Móvil o MODO)'},
    'modo': {'wallet': 'MODO', 'channel': 'MODO (bancos adheridos)'},
    'hipotecario modo': {'bank': 'Banco Hipotecario', 'channel': 'QR MODO (App BH o MODO)'},
    'icbc modo': {'bank': 'ICBC', 'channel': 'MODO o ICBC Mobile Banking'},
    'icbc sueldos': {'bank': 'ICBC', 'channel': 'MODO o ICBC Mobile Banking',
                     'requirement': 'Exclusiva para clientes que cobran el sueldo en ICBC'},
    # "Patagonia 365" es la tarjeta del Banco del Chubut, no del Banco Patagonia.
    'patagonia 365': {'bank': 'Banco del Chubut'},
    'yoy modo': {'bank': 'YOY', 'channel': 'MODO o App YOY'},
    'yoy': {'bank': 'YOY', 'channel': 'MODO o App YOY'},
    'banco supervielle': {'bank': 'Banco Supervielle'},
    'naranjax': {'bank': 'Naranja X'},
    'banco comafi modo': {'bank': 'Banco Comafi', 'channel': 'QR MODO'},
    'banco provincia - cuenta dni': {'bank': 'Banco Provincia', 'wallet': 'Cuenta DNI',
                                     'label': 'Cuenta DNI', 'channel': 'Cuenta DNI'},
    'banco columbia': {'bank': 'Banco Columbia'},
    'sol': {'bank': 'Tarjeta Sol'},
    'banco galicia': {'bank': 'Banco Galicia'},
    'anses': {'label': 'ANSES', 'payment': 'Todos los medios de pago',
              'requirement': 'Exclusiva para beneficiarios de ANSES (presentar DNI)'},
    'empleados publicos': {'label': 'Empleados públicos', 'payment': 'Todos los medios de pago',
                           'requirement': 'Exclusiva para empleados municipales y provinciales '
                                          '(presentar DNI y recibo de sueldo)'},
    # "Tarjeta Cordobesa" es la tarjeta de Bancor (Banco de Córdoba).
    'bancor': {'bank': 'Bancor'},
    'credicuotas': {'wallet': 'Credicuotas', 'channel': 'QR Credicuotas (línea de crédito)'},
}

# Respaldo si GetBanks no responde: ids vistos en producción (2026-10).
FALLBACK_BANK_NAMES = {
    '8fab960f-8b29-11ef-b37f-98380ffd16cd': 'MasClub',
    '8ccbdf0d-905d-11ee-8452-0eb8fa5466a5': 'Mercado Pago',
    '15ff1c4e-2630-11f0-b37f-93b1d8eaa315': 'Billeteras Virtuales',
    'fdfcc594-907a-11ed-83ab-0ab135d7cee1': 'Banco Patagonia',
    'e9570b46-44c8-11ed-83ab-0a7e73da0665': 'Banco Nación BNA',
    '6db380e1-bb9d-4ed9-82ef-15a799aec451': 'Buepp Banco Ciudad',
    '0956bf6c-983a-11ee-8452-1298279711fd': 'Banco Credicoop MODO',
    '6bbbedf1-ab40-11ee-8452-127334bd7427': 'Modo',
    'c40d38d3-1a7a-11ee-83ab-0263dabe290f': 'Hipotecario_Modo',
    '06fc4208-78d8-11ee-83ab-0a1649dfa6b1': 'ICBC Modo',
    'c7025517-3067-11ee-83ab-125c839bfdf1': 'Patagonia 365',
    '2f59e6b6-b357-430a-9e82-3781b870bc52': 'ICBC_Sueldos',
    'ab6abe23-54fd-11ef-8452-1211a9021aa7': 'Yoy_MODO',
    'b7409f62-44f4-11ed-83ab-1600502170e1': 'Banco Supervielle',
    '9a9c3703-2fe8-11ee-83ab-0ecaeb3d03b5': 'NaranjaX',
    '7daf51ea-1f6b-11ef-8452-0e6ca8a392fd': 'Yoy',
    'a234c39c-7f5a-11ef-b37f-f2e65af65faa': 'Banco_Comafi_MODO',
    'f9315b48-4f81-11ef-8452-121b3ce95f81': 'Banco Provincia - Cuenta DNI',
    '62913526-f5e0-11ef-b37f-940e7c6d2e3e': 'Banco Columbia',
    'a58230b6-3575-11ef-8452-0affd045eab9': 'Sol',
    '6167861a-a593-11ee-8452-0af780f66fd5': 'Banco Galicia',
    '32f07815-982d-11ee-8452-1288a753a239': 'Anses',
    'd247d13c-0881-11ef-8452-0affe9b94723': 'Empleados Públicos',
    'ec7714dc-2866-405a-843a-8f8476c47b01': 'BANCOR',
    '1ca7093d-5c03-45ef-8550-a8f06cd46921': 'Credicuotas',
}

NETWORKS = [
    (r'\bvisa\b', 'Visa'), (r'master\s*card', 'Mastercard'),
    (r'american\s+express|\bamex\b', 'American Express'), (r'\bcabal\b', 'Cabal'),
    (r'naranja\s*x', 'Naranja X'), (r'patagonia\s+365', 'Patagonia 365'),
    (r'\bsol\b', 'Sol'),
]


def _norm(text: str) -> str:
    """Mayúsculas sin tildes y con espacios simples (para regex de legales)."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', text).upper().strip()


def _money(raw: str) -> Optional[str]:
    digits = re.sub(r'\D', '', raw or '')
    if not digits or int(digits) <= 0:
        return None
    return '$' + f"{int(digits):,}".replace(',', '.')


def _int_or_none(value) -> Optional[int]:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _api_date(value: Optional[str]) -> Optional[date]:
    """Fecha ISO de la API (UTC) → día calendario en Argentina."""
    if not value or value == 'null':
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ART).date()


def _year(raw: Optional[str], default: int) -> int:
    if not raw:
        return default
    year = int(raw)
    return year + 2000 if year < 100 else year


def _safe_date(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


class MasOnlineScraper:
    def __init__(self):
        self.name = 'Más Online (ChangoMás)'
        self.base_url = 'https://www.masonline.com.ar/promociones-bancarias'
        self.terms_parser = TermsParser()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'),
            'Accept': 'application/json',
            'Accept-Language': 'es-AR,es;q=0.9',
        })

    # ------------------------------------------------------------------ API
    def _query(self, operation: str, sha256: str, variables: Dict) -> List[Dict]:
        extensions = {
            'persistedQuery': {'version': 1, 'sha256Hash': sha256, 'sender': SENDER, 'provider': PROVIDER},
            'variables': base64.b64encode(json.dumps(variables).encode()).decode(),
        }
        params = {
            'workspace': 'master', 'maxAge': 'short', 'appsEtag': 'remove', 'domain': 'store',
            'locale': 'es-AR', 'operationName': operation, 'variables': '{}',
            'extensions': json.dumps(extensions),
        }
        resp = self.session.get(GRAPHQL_URL, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        documents = ((payload.get('data') or {}).get('documents'))
        if documents is None:
            raise RuntimeError(f"{operation}: respuesta sin documentos ({str(payload)[:200]})")
        return [{f['key']: f['value'] for f in doc.get('fields', [])} for doc in documents]

    def fetch(self) -> Tuple[List[Dict], Dict[str, str]]:
        """Descarga promos activas (misma consulta que la web) y el mapa de bancos."""
        now = datetime.now(ART).strftime('%Y-%m-%dT%H:%M:%S')
        promos = self._query('GetPromos', HASH_GET_PROMOS, {
            'where': f'active=true AND ((active_from < {now}) AND (active_to > {now}))',
            'account': ACCOUNT,
        })
        try:
            banks = {b['id']: b.get('name', '') for b in
                     self._query('GetBanks', HASH_GET_BANKS, {'account': ACCOUNT})}
        except Exception as e:
            print(f"   ⚠️ GetBanks falló ({e}); se usa el mapa de bancos conocido")
            banks = {}
        return promos, {**FALLBACK_BANK_NAMES, **banks}

    async def scrape(self) -> List[Dict]:
        print(f"\n🔍 Scraping {self.name} - Promociones Bancarias (API VTEX)...")
        try:
            docs, banks = await asyncio.to_thread(self.fetch)
        except Exception as e:
            print(f"   ❌ Error consultando la API de promociones: {e}")
            return []
        promos = self.parse_documents(docs, banks)
        print(f"   ✅ {len(promos)} promociones ({len(docs)} documentos)")
        return promos

    # -------------------------------------------------------------- parseo
    def parse_documents(self, docs: List[Dict], banks: Dict[str, str],
                        today: Optional[date] = None) -> List[Dict]:
        today = today or datetime.now(ART).date()
        promos = []
        for doc in docs:
            if str(doc.get('active', 'true')).lower() == 'false':
                continue
            try:
                promo = self._parse_doc(doc, banks, today)
            except Exception as e:  # una tarjeta rara no debe tirar la fuente entera
                print(f"   ⚠️ No se pudo parsear la promo {doc.get('id')}: {e}")
                continue
            if promo:
                promos.append(promo)

        # El código del subtítulo ya hace único el título; si dos documentos
        # comparten código y beneficio, el id del documento desempata.
        seen = {}
        for promo in promos:
            if promo['title'] in seen:
                promo['title'] = f"{promo['title']} [{promo['source_id'][:8]}]"
            seen[promo['title']] = True
        return promos

    def _parse_doc(self, doc: Dict, banks: Dict[str, str], today: date) -> Optional[Dict]:
        title_raw = (doc.get('title') or '').strip()
        sub = re.sub(r'\s+', ' ', doc.get('sub_title') or '').strip()
        valid_text = (doc.get('validText') or '').strip()
        legal = re.sub(r'[ \t]*\n[ \t]*', ' ', doc.get('legal') or '').strip()
        legal = re.sub(r' {2,}', ' ', legal)
        legal_n = _norm(legal)
        card_text = f"{title_raw} {sub}"

        code_match = re.search(r'\(+\s*([A-Za-z0-9][A-Za-z0-9\-]*)\s*\)\s*\*?\s*$', sub)
        code = code_match.group(1).upper() if code_match else None

        entity = self._entity(banks.get(doc.get('idBank') or '', ''))

        # 1. Beneficio
        pct = _int_or_none(doc.get('discount_percentage'))
        cuotas = _int_or_none(doc.get('discounts_amount_installments'))
        is_reintegro = 'reintegro' in (doc.get('discount_text_info') or '').lower()
        if pct and cuotas:
            if re.search(rf'EN\s+{cuotas}\s+CUOTAS', legal_n) and 'REINTEGRO' in legal_n:
                discount = f"{pct}% reintegro en {cuotas} cuotas"
            else:
                discount = f"{pct}% o {cuotas} cuotas sin interés"
        elif pct:
            discount = f"{pct}% reintegro" if is_reintegro else f"{pct}%"
        elif cuotas:
            discount = f"{cuotas} cuotas sin interés"
        else:
            return None

        # 2. Días (flags estructurados) y si el legal habla de los mismos días
        flag_days = [name for field, name in DAY_FIELDS if str(doc.get(field)).lower() == 'true']
        # Los flags a veces vienen incompletos (Billeteras 15% trae sáb/dom pero
        # la tarjeta y el legal dicen "Viernes, Sábados y Domingos").
        text_days = self._days_from_text(valid_text)
        flag_days = [d for d in DAY_NAMES if d in flag_days or d in text_days]
        legal_trusted = self._legal_matches_days(legal_n, flag_days)

        # 3. Fechas puntuales y vigencia
        dates = self._explicit_dates(legal_n, flag_days, today) if legal_trusted else []
        dates = sorted(set(dates) | set(self._explicit_dates(_norm(valid_text), flag_days, today)))
        if dates:
            upcoming = [d for d in dates if d >= today] or dates
            valid_from, valid_until = upcoming[0], upcoming[-1]
            valid_days = self._format_dates(upcoming)
        else:
            valid_from, valid_until = self._validity(legal_n if legal_trusted else '', today)
            if len(flag_days) == 7 or not flag_days:
                valid_days = 'Todos los días'
            else:
                valid_days = ', '.join(flag_days)
        active_from, active_to = _api_date(doc.get('active_from')), _api_date(doc.get('active_to'))
        if valid_from and valid_until and valid_until < valid_from:
            valid_until = None  # typo del legal (p. ej. "DEL 1/10/2026 AL 31/12/2025")
        valid_from = valid_from or active_from
        valid_until = valid_until or active_to

        # 4. Tope y mínimo
        requirements = []
        if entity.get('requirement'):
            requirements.append(entity['requirement'])
        tope = self._tope(card_text, sub, legal_n)
        # Sólo se confía en el tope del legal si describe un único beneficio
        # (sin tramos de 20%/30% o planes con topes distintos).
        legal_pcts = set(re.findall(r'(\d{1,2})\s*%', legal_n)) - {'0'}
        legal_tope = (self._legal_single_tope(legal_n)
                      if legal_trusted and pct and legal_pcts == {str(pct)} else None)
        sub_amounts = re.findall(r'\$?\s*(\d{1,3}(?:\.\d{3})+|\d{4,})', sub.split('(')[0] if '(' in sub else sub)
        if (tope and tope != 'Sin tope' and legal_tope and len(set(sub_amounts)) == 1
                and _money(sub_amounts[0]) != legal_tope):
            requirements.append(f"Tope según legal: {legal_tope} (la tarjeta de la web indica {tope})")
            tope = legal_tope + tope[len(_money(sub_amounts[0]) or ''):]
        min_purchase = self._min_purchase(sub, legal_n if legal_trusted else '')
        range_match = re.search(r'a partir de \$\s*([\d.]+)\s+a\s+\$\s*([\d.]+)', sub, re.I)
        if range_match:
            requirements.append(
                f"Compras de {_money(range_match.group(1))} a {_money(range_match.group(2))}")

        # 5. Tarjeta, medio de pago y canal
        card_type = self._card_type(card_text, bool(cuotas))
        payment_method = self._payment_method(card_text, entity)
        store_types = self._store_types(doc, card_text, valid_text, legal_n)

        # 6. Título único y legible
        label = entity.get('label') or entity.get('bank') or entity.get('wallet') or 'Más Online'
        qualifiers = self._qualifiers(title_raw, sub, store_types)
        title = f"{label} {discount} - {valid_days}"
        if qualifiers:
            title += f" - {', '.join(qualifiers)}"
        if code:
            title += f" ({code})"

        terms = self.terms_parser.parse(legal) if legal else {}
        if terms.get('requirements'):
            requirements.append(terms['requirements'])

        return {
            'title': title,
            'discount': discount,
            'bank': entity.get('bank'),
            'wallet': entity.get('wallet'),
            'card_type': card_type,
            'payment_method': payment_method,
            'store_types': store_types,
            'valid_days': valid_days,
            'valid_from': valid_from.isoformat() if valid_from else None,
            'valid_until': valid_until.isoformat() if valid_until else None,
            'tope': tope,
            'min_purchase': min_purchase,
            'acumulable': self._acumulable(f"{sub} {legal_n}"),
            'terms_raw': legal[:8000] or sub,
            'exclusions': terms.get('exclusions') or None,
            'requirements': ' | '.join(requirements) or None,
            'url': self.base_url,
            'source_id': doc.get('id') or code,
        }

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _entity(bank_name: str) -> Dict:
        key = re.sub(r'\s+', ' ', _norm(bank_name).replace('_', ' ')).lower().strip()
        if key in ENTITIES:
            return dict(ENTITIES[key])
        if not key:
            return {}
        # Entidad nueva: limpiar sufijos "_MODO" y conservar el nombre publicado.
        has_modo = bool(re.search(r'\bmodo\b', key))
        clean = re.sub(r'[_\s]*modo\b', '', bank_name, flags=re.I).replace('_', ' ').strip() or bank_name
        entity = {'bank': clean}
        if has_modo:
            entity['channel'] = 'QR MODO'
        return entity

    @staticmethod
    def _days_from_text(valid_text: str) -> List[str]:
        """Días nombrados en validText ("Jueves a Domingos", "Viernes, Sábados y Domingos")."""
        text_n = _norm(valid_text)
        if re.search(r'TODOS LOS DIAS', text_n):
            return list(DAY_NAMES)
        names = re.findall(rf'\b{_WEEKDAY_RE}\b', text_n)
        idx = [_WEEKDAY_INDEX[n] for n in names]
        m = re.search(rf'\b({_WEEKDAY_RE})\s+A\s+({_WEEKDAY_RE})\b', text_n)
        if m:
            start, end = _WEEKDAY_INDEX[m.group(1)], _WEEKDAY_INDEX[m.group(2)]
            idx += list(range(start, end + 1)) if start <= end else list(range(start, 7)) + list(range(0, end + 1))
        return [DAY_NAMES[i] for i in sorted(set(idx))]

    @staticmethod
    def _legal_matches_days(legal_n: str, flag_days: List[str]) -> bool:
        """False si el legal sólo menciona otros días (legal copiado de otra promo)."""
        mentioned = {_WEEKDAY_INDEX[w] for w in re.findall(rf'\b{_WEEKDAY_RE}\b', legal_n)}
        if not mentioned or not flag_days:
            return True
        flags = {DAY_NAMES.index(d) for d in flag_days}
        return bool(mentioned & flags)

    @staticmethod
    def _explicit_dates(text_n: str, flag_days: List[str], today: date) -> List[date]:
        """Fechas puntuales: "LUNES 5, 12, 19 Y 26 DE OCTUBRE DE 2026",
        "SABADO 24/10/26, 28/11/26 Y 26/12/26", "SABADO 24 Y DOMINGO 25 DE OCTUBRE".

        Sólo se aceptan si cada fecha cae en uno de los días marcados en la
        promo; así un número suelto del legal no se convierte en vigencia.
        """
        if not text_n:
            return []
        found: List[date] = []
        item = rf'(?:{_WEEKDAY_RE}\s+)?\d{{1,2}}'
        for m in re.finditer(
                rf'\b{_WEEKDAY_RE}\s+(\d{{1,2}}(?:\s*(?:,|\bY\b)\s*{item})*)\s+DE\s+({_MONTH_RE})'
                rf'(?:\s+(?:DE|DEL)?\s*(\d{{4}}))?', text_n):
            month, year = MONTHS[m.group(2)], _year(m.group(3), today.year)
            found += [d for d in (_safe_date(year, month, int(x)) for x in re.findall(r'\d{1,2}', m.group(1))) if d]
        slash = r'\d{1,2}/\d{1,2}(?:/\d{2,4})?'
        for m in re.finditer(rf'\b{_WEEKDAY_RE}\s+({slash}(?:\s*(?:,|\bY\b)\s*{slash})*)', text_n):
            for d, mo, y in re.findall(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', m.group(1)):
                parsed = _safe_date(_year(y, today.year), int(mo), int(d))
                if parsed:
                    found.append(parsed)
        if not found:
            return []
        if flag_days:
            allowed = {DAY_NAMES.index(d) for d in flag_days}
            if any(d.weekday() not in allowed for d in found):
                return []
        return sorted(set(found))

    @staticmethod
    def _format_dates(dates: List[date]) -> str:
        """[sáb 24/10, sáb 28/11] → "Sábados 24/10 y 28/11"; agrupa por día."""
        groups: Dict[int, List[date]] = {}
        for d in dates:
            groups.setdefault(d.weekday(), []).append(d)
        parts = []
        for weekday in sorted(groups, key=lambda w: groups[w][0]):
            items = [d.strftime('%d/%m') for d in groups[weekday]]
            name = DAY_NAMES[weekday]
            if len(items) > 1:
                name = PLURAL_DAYS.get(name, name)
                joined = ', '.join(items[:-1]) + ' y ' + items[-1]
            else:
                joined = items[0]
            parts.append(f"{name} {joined}")
        return ' y '.join(parts) if len(parts) <= 2 else ', '.join(parts[:-1]) + ' y ' + parts[-1]

    @staticmethod
    def _validity(legal_n: str, today: date) -> Tuple[Optional[date], Optional[date]]:
        """Vigencia desde el legal: rango numérico, rango textual o "DE OCTUBRE 2026"."""
        if not legal_n:
            return None, None
        m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})\s*,?\s*(?:AL|HASTA(?:\s+EL)?|Y(?:\s+EL)?|-)\s*'
                      r'(\d{1,2})/(\d{1,2})/(\d{2,4})', legal_n)
        if m:
            d1, m1, y1, d2, m2, y2 = m.groups()
            return (_safe_date(_year(y1, today.year), int(m1), int(d1)),
                    _safe_date(_year(y2, today.year), int(m2), int(d2)))
        m = re.search(rf'(\d{{1,2}}) DE ({_MONTH_RE})(?: DE (\d{{4}}))?\s*(?:AL|HASTA|Y)(?: EL)? '
                      rf'(\d{{1,2}}) DE ({_MONTH_RE}) DE (\d{{4}})', legal_n)
        if m:
            d1, mo1, y1, d2, mo2, y2 = m.groups()
            y2 = int(y2)
            return (_safe_date(_year(y1, y2), MONTHS[mo1], int(d1)), _safe_date(y2, MONTHS[mo2], int(d2)))
        # "LOS JUEVES DE OCTUBRE 2026", "MARTES DE MES DE SEPTIEMBRE Y OCTUBRE 2026"
        m = re.search(rf'\b{_WEEKDAY_RE}\s+DE\s+(?:(?:L[AO]S?\s+)?MES(?:ES)?\s+DE\s+)?'
                      rf'({_MONTH_RE}(?:\s*(?:,|\bY\b)\s*{_MONTH_RE})*)(?:\s+(?:DE|DEL)?\s*(\d{{4}}))?', legal_n)
        if m:
            months = [MONTHS[x] for x in re.findall(_MONTH_RE, m.group(1))]
            year = _year(m.group(2), today.year)
            first, last = min(months), max(months)
            return date(year, first, 1), date(year, last, calendar.monthrange(year, last)[1])
        return None, None

    @staticmethod
    def _period(text: str) -> str:
        low = text.lower()
        if re.search(r'mensual|por mes', low):
            return 'mensual'
        if re.search(r'semanal|por semana', low):
            return 'semanal'
        if re.search(r'por transacci[oó]n', low):
            return 'por transacción'
        return ''

    def _tope(self, card_text: str, sub: str, legal_n: str) -> Optional[str]:
        if re.search(r'sin\s+tope', card_text, re.I):
            return 'Sin tope'
        segments = list(re.finditer(
            r'tope(\s+(?:mensual|semanal))?\s*:?\s*\$?\s*(\d[\d.]*\d|\d)(.*?)(?=\.\s|\.$|\(|tope|$)', sub, re.I))
        if not segments:
            return 'Sin tope' if re.search(r'SIN TOPE', legal_n) else None
        main = None
        extras = []
        for i, seg in enumerate(segments):
            amount = _money(seg.group(2))
            if not amount:
                continue
            rest = seg.group(3) or ''
            period = self._period((seg.group(1) or '') + ' ' + rest)
            by_bank = ' por banco' if re.search(r'por banco', rest, re.I) else ''
            if main is None:
                main = f"{amount} {period}".strip() + by_bank
                # "y $30.000 para Búho One, Sueldo..." → tramo alternativo
                for alt, who in re.findall(r'\by\s+\$\s*([\d.]+)\s+para\s+([^.]+)', rest, re.I):
                    extras.append(f"{_money(alt)} para {who.strip()}")
            else:
                who = re.search(r'para\s+(.+)', rest, re.I)
                extras.append(f"{amount} {period}".strip() + (f" para {who.group(1).strip()}" if who else ''))
        if not main:
            return None
        return main + (f" ({'; '.join(extras)})" if extras else '')

    @staticmethod
    def _legal_single_tope(legal_n: str) -> Optional[str]:
        """Tope del legal cuando hay un único monto (p. ej. Credicuotas $8.000)."""
        amounts = {_money(a) for a in re.findall(r'TOPE[^$.]{0,60}(?:\$\s*)+([\d.]*\d)', legal_n)}
        amounts.discard(None)
        return amounts.pop() if len(amounts) == 1 else None

    @staticmethod
    def _min_purchase(sub: str, legal_n: str) -> Optional[str]:
        m = (re.search(r'm[ií]n[ií]?mo\s+de\s+compra\s*:?\s*\$\s*([\d.]*\d)', sub, re.I)
             or re.search(r'a\s+partir\s+de\s*\$\s*([\d.]*\d)', sub, re.I))
        if not m and legal_n:
            m = re.search(r'(?:IGUALES O SUPERIORES A|COMPRAS? MINIMAS? DE|MINIMO DE COMPRA(?: DE)?)\s*\$\s*([\d.]*\d)',
                          legal_n)
        return _money(m.group(1)) if m else None

    @staticmethod
    def _card_type(card_text: str, has_cuotas: bool) -> Optional[str]:
        credit = bool(re.search(r'cr[eé]dito', card_text, re.I))
        debit = bool(re.search(r'd[eé]bito', card_text, re.I))
        if credit and debit:
            return 'Crédito, Débito'
        if credit or (has_cuotas and not debit):
            return 'Crédito'
        if debit:
            return 'Débito'
        return None

    @staticmethod
    def _payment_method(card_text: str, entity: Dict) -> Optional[str]:
        if entity.get('payment') or re.search(r'todos\s+los\s+medios\s+de\s+pago', card_text, re.I):
            return entity.get('payment') or 'Todos los medios de pago'
        networks = [name for pattern, name in NETWORKS if re.search(pattern, card_text, re.I)]
        parts = []
        if networks:
            parts.append('Tarjetas ' + ', '.join(networks))
        channel = entity.get('channel')
        if channel:
            if re.search(r'\bNFC\b', card_text):
                channel += ' (NFC)'
            parts.append(channel)
        return ' vía '.join(parts) or None

    @staticmethod
    def _store_types(doc: Dict, card_text: str, valid_text: str, legal_n: str) -> str:
        if re.search(r'exclusiv\w*\s+(?:en\s+las\s+tiendas\s+de\s+)?mas\s*go|en\s+mas\s*go\b|-\s*mas\s*go\b',
                     f"{card_text} {valid_text}", re.I):
            return 'Tiendas MasGO'
        # market = sólo tiendas físicas; express = tiendas + Más Online.
        if str(doc.get('market')).lower() == 'true':
            return 'Tiendas'
        if str(doc.get('express')).lower() == 'true' or str(doc.get('ecommerce')).lower() == 'true':
            return 'Online, Tiendas'
        if 'PRESENCIAL' in legal_n and 'ONLINE' not in legal_n:
            return 'Tiendas'
        return 'Online, Tiendas'

    @staticmethod
    def _qualifiers(title_raw: str, sub: str, store_types: str) -> List[str]:
        out = []
        m = re.match(r'(Plan\s+\S+)', title_raw, re.I)
        if m:
            out.append(m.group(1))
        m = re.match(r'Exclusivo\s+(\w+)\s*-', title_raw, re.I)
        if m:
            out.append(m.group(1))
        m = re.search(r'\bCon\s+((?:Cl[aá]sica\s+y\s+)?Plus|Singular)\b', title_raw, re.I)
        if m:
            out.append(m.group(1))
        if re.search(r'cuenta\s+sueldo', title_raw, re.I):
            out.append('Cuenta Sueldo')
        if re.search(r'primera\s+compra', title_raw, re.I):
            out.append('Primera compra')
        if re.search(r'\bNFC\b', title_raw):
            out.append('NFC')
        range_match = re.search(r'a partir de \$\s*([\d.]+)\s+a\s+\$\s*([\d.]+)', sub, re.I)
        single = re.search(r'a partir de \$\s*([\d.]*\d)', sub, re.I)
        if range_match:
            out.append(f"compras {_money(range_match.group(1))} a {_money(range_match.group(2))}")
        elif single:
            out.append(f"compras desde {_money(single.group(1))}")
        if store_types == 'Tiendas MasGO':
            out.append('MasGO')
        return out

    @staticmethod
    def _acumulable(text: str) -> Optional[str]:
        text_n = _norm(text)
        if re.search(r'\bNO\s+(?:ES\s+|SE\s+)?ACUM|NI\s+SON\s+ACUMULATIV', text_n):
            return 'No'
        if re.search(r'\bACUMULABLE\b', text_n):
            return 'Sí'
        return None


async def main():
    scraper = MasOnlineScraper()
    promos = await scraper.scrape()
    for promo in promos:
        print(f"- {promo['title']} | tope={promo['tope']} | min={promo['min_purchase']} | "
              f"{promo['valid_from']}→{promo['valid_until']} | {promo['card_type']} | "
              f"{promo['payment_method']} | {promo['store_types']}")


if __name__ == '__main__':
    asyncio.run(main())
