#!/usr/bin/env python3
"""
Scraper de Supermercados Día - Promociones Bancarias

La landing VTEX ``/medios-de-pago-y-promociones`` se renderiza del lado del
servidor y trae embebido (en un ``<script>`` JSON) el contenido del bloque
``...landing-medios-pago#props``. De ahí se usa ``content.cards`` (las tarjetas
que se ven en la página; ``props.cards`` es una copia vieja y NO se usa):

  - ``__editorItemTitle``: rótulo interno ("Naranja 25%", "5% BNA MODO").
  - ``active``: sólo las activas se muestran.
  - ``daysToShow``: días de la tarjeta (se ignora ``all``).
  - ``availableOn``: online / store.
  - ``associatedBanks``: entidad (puede venir vacía, p. ej. Credicoop).
  - ``terms``: legal completo (vigencia, tope, mínimo, tipo de tarjeta).

No necesita navegador: alcanza con un GET plano.
"""
import asyncio
import json
import os
import re
import tempfile
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple


_PROPS_SUFFIX = 'landing-medios-pago#props'
_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'es-AR,es;q=0.9',
}

_DAY_KEYS = (
    ('monday', 'Lunes'), ('tuesday', 'Martes'), ('wednesday', 'Miércoles'),
    ('thursday', 'Jueves'), ('friday', 'Viernes'), ('saturday', 'Sábado'),
    ('sunday', 'Domingo'),
)
_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
}
_MONTH_RE = '|'.join(_MONTHS)

# Nombre de entidad (associatedBanks o rótulo) → (bank, wallet, etiqueta).
_ENTITIES = (
    (r'^modo$', (None, 'MODO', 'MODO')),
    (r'prex', (None, 'Prex', 'Prex')),
    (r'personal\s*pay', (None, 'Personal Pay', 'Personal Pay')),
    (r'mercado\s*pago', (None, 'Mercado Pago', 'Mercado Pago')),
    (r'cuenta\s*dni', ('Banco Provincia', 'Cuenta DNI', 'Cuenta DNI')),
    (r'columbia', ('Banco Columbia', None, 'Banco Columbia')),
    (r'banco\s*del\s*sol', ('Banco del Sol', None, 'Banco del Sol')),
    (r'credicoop', ('Banco Credicoop', None, 'Banco Credicoop')),
    (r'corrientes', ('Banco de Corrientes', None, 'Banco de Corrientes')),
    (r'naranja', ('Naranja X', None, 'Naranja X')),
    (r'^bna$|banco\s*naci[oó]n', ('Banco Nación', None, 'Banco Nación')),
    (r'anses', ('ANSES', None, 'ANSES')),
    (r'sidecreer', ('Sidecreer', None, 'Sidecreer')),
    (r'tarjeta\s*ba|ciudadan[ií]a', (None, None, 'Ciudadanía Porteña')),
    (r'galicia', ('Banco Galicia', None, 'Banco Galicia')),
    (r'macro', ('Banco Macro', None, 'Banco Macro')),
    (r'ciudad', ('Banco Ciudad', None, 'Banco Ciudad')),
)
_CARD_BRANDS = (
    (r'\bvisa\b', 'Visa'), (r'master\s*card', 'Mastercard'),
    (r'american\s+express|\bamex\b', 'American Express'), (r'\bcabal\b', 'Cabal'),
)
# Tiendas regionales: el legal o la entidad restringe a una provincia.
_REGIONAL_ENTITIES = {'Banco de Corrientes': 'Corrientes'}

# Datos que Día publica SÓLO en la imagen de la tarjeta (el legal no los
# dice). Se indexan por el id del asset: si Día cambia la imagen, el dato deja
# de aplicarse y la tarjeta vuelve a parsearse sólo desde el legal.
_IMAGE_FACTS = {
    # ANSES: "10% de reintegro - Tope $2.000 por transacción - Del 1 de enero
    # al 31 de octubre - Tarjeta de débito (solo beneficiarios)".
    '5781d88c-21c3-4ce0-b76e-18a573e3d3ab': {
        'percent': 10, 'tope': '$2.000 por transacción', 'card_type': 'Débito',
        'valid_from': '2026-01-01', 'valid_until': '2026-10-31',
    },
    # Credicoop: el legal sólo da el ejemplo ($60.000 → $15.000); la imagen
    # confirma "25% de reintegro - Tope de $15.000 semanal".
    '7f92d03b-ce19-4469-a08c-8ea2283bde5d': {'percent': 25, 'tope': '$15.000 semanal'},
    # BNA + MODO viernes y sábados (oct–dic 2026): el legal trae tope y mínimo
    # pero no el porcentaje; la imagen dice "10% de reintegro".
    '91ba2a98-330a-446a-81ea-58f7ddb0b2e9': {'percent': 10},
}

_IMAGE_PROMPT = (
    "Es la tarjeta de una promoción bancaria de un supermercado argentino. "
    "Respondé SOLO un JSON: {\"percent\": <número entero del porcentaje de "
    "descuento o reintegro que se ve en grande, o null si no hay>}."
)


def _percent_from_image(url: str) -> Optional[int]:
    """Lee el % de la imagen de la tarjeta con Gemini cuando el legal no lo trae.

    Es un respaldo para tarjetas nuevas sin dato en _IMAGE_FACTS; sin
    GEMINI_API_KEY devuelve None y la tarjeta se omite con un aviso.
    """
    key = os.environ.get('GEMINI_API_KEY')
    if not key or not url:
        return None
    try:
        import google.generativeai as genai
        import requests
        from scrapers.ai_extractor import _resolve_gemini_model

        genai.configure(api_key=key)
        image = requests.get(url, headers=_HEADERS, timeout=20)
        image.raise_for_status()
        model = genai.GenerativeModel(_resolve_gemini_model(os.environ.get('AI_MODEL', 'gemini-2.5-flash')))
        response = model.generate_content([
            {'mime_type': image.headers.get('content-type', 'image/jpeg').split(';')[0], 'data': image.content},
            _IMAGE_PROMPT,
        ])
        match = re.search(r'\{.*\}', response.text or '', re.S)
        percent = json.loads(match.group(0)).get('percent') if match else None
        return int(percent) if percent and 0 < int(percent) <= 100 else None
    except Exception as exc:
        print(f"   ⚠️ No se pudo leer el porcentaje de la imagen: {exc}")
        return None


def _debug_dump(name: str, content: str) -> None:
    """Guarda artefactos de debug fuera del repo, sólo con DEBUG_SCRAPER."""
    if os.environ.get('DEBUG_SCRAPER', '').lower() not in ('1', 'true', 'yes'):
        return
    path = os.path.join(tempfile.gettempdir(), name)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)
    print(f"   💾 Debug: {path}")


class DiaScraper:
    def __init__(self):
        self.name = 'Supermercados Día'
        self.base_url = 'https://diaonline.supermercadosdia.com.ar/medios-de-pago-y-promociones'

    async def scrape(self) -> List[Dict]:
        print(f"\n🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.base_url}")
        try:
            html = await asyncio.to_thread(self._fetch_html)
        except Exception as error:
            print(f"   ❌ No se pudo descargar la landing de Día ({type(error).__name__}: {error})")
            return []
        _debug_dump('debug_dia_landing.html', html)

        cards = self._extract_cards(html)
        if not cards:
            print("   ⚠️ No se encontró el bloque landing-medios-pago en el HTML; no se devuelven promos")
            return []

        promotions = self._parse_cards(cards)
        print(f"\n✅ {self.name}: {len(promotions)} promociones")
        return promotions

    # ──────────────────────────────────────────────────────────────────────
    # Descarga / extracción del JSON embebido
    # ──────────────────────────────────────────────────────────────────────

    def _fetch_html(self) -> str:
        import requests
        response = requests.get(self.base_url, headers=_HEADERS, timeout=(8, 40))
        response.raise_for_status()
        return response.text

    @staticmethod
    def _extract_cards(html: str) -> List[Dict]:
        for match in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.S):
            body = match.group(1)
            if _PROPS_SUFFIX not in body:
                continue
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            for key, block in data.items():
                if key.endswith(_PROPS_SUFFIX) and isinstance(block, dict):
                    cards = (block.get('content') or {}).get('cards')
                    if isinstance(cards, list):
                        return cards
        return []

    # ──────────────────────────────────────────────────────────────────────
    # Parseo de tarjetas
    # ──────────────────────────────────────────────────────────────────────

    def _parse_cards(self, cards: List[Dict], today: Optional[date] = None) -> List[Dict]:
        today = today or datetime.now().date()
        promotions: List[Dict] = []
        for index, card in enumerate(cards):
            if not isinstance(card, dict) or not card.get('active'):
                continue
            promo = self._parse_card(card, index)
            label = self._clean(card.get('__editorItemTitle')) or f'card {index}'
            if not promo:
                print(f"   ⏭️ {label}: sin beneficio identificable, se omite")
                continue
            if promo.get('valid_until') and promo['valid_until'] < today.isoformat():
                # Día a veces deja publicada la tarjeta con el legal vencido.
                print(f"   ⌛ {label}: vencida el {promo['valid_until']}, se omite")
                continue
            print(f"      {promo['title']}")
            promotions.append(promo)

        seen: Dict[str, int] = {}
        for promo in promotions:
            seen[promo['title']] = seen.get(promo['title'], 0) + 1
        for promo in promotions:
            if seen[promo['title']] > 1:
                promo['title'] += f" #{promo['source_id'].rsplit('-', 1)[-1]}"
        return promotions

    def _parse_card(self, card: Dict, index: int) -> Optional[Dict]:
        editor_title = self._clean(card.get('__editorItemTitle'))
        terms = self._clean(card.get('terms'))
        image = ((card.get('displayData') or {}).get('cardImage') or '')
        facts = next((f for asset, f in _IMAGE_FACTS.items() if asset in image), {})
        text = terms.upper()

        banks = [self._clean(b.get('__editorItemTitle')) for b in card.get('associatedBanks') or []
                 if isinstance(b, dict)]
        bank, wallet, entity_label, brands = self._resolve_entity(banks, editor_title, text)

        discount, plan = self._discount(editor_title, text, facts)
        if not discount:
            image_percent = _percent_from_image(image)
            if image_percent:
                facts = {**facts, 'percent': image_percent}
                discount, plan = self._discount(editor_title, text, facts)
        if not discount:
            # Antes se descartaba en silencio: una tarjeta activa sin % en el
            # legal (sólo en la imagen) desaparecía de la web sin que nadie lo note.
            print(f"   ⚠️ Tarjeta activa sin beneficio legible, se omite: {editor_title!r} ({image})")
            return None

        # Naranja X publica una tarjeta por plan con el mismo legal: el tope
        # sale del tramo cuyo porcentaje coincide con el de la tarjeta.
        tope = facts.get('tope') or self._plan_tope(text, discount) or self._extract_tope(text)

        if bank and not wallet and re.search(r'\bMODO\b', f"{text} {editor_title.upper()}"):
            wallet = 'MODO'

        valid_days = self._valid_days(card.get('daysToShow') or {})
        valid_from, valid_until = self._validity(text)
        valid_from = facts.get('valid_from') or valid_from
        valid_until = facts.get('valid_until') or valid_until

        store_types = self._store_types(card.get('availableOn') or {}, text, bank)
        card_type = facts.get('card_type') or self._card_type(text, discount)
        payment_method = self._payment_method(text, wallet, brands, card_type, bank)
        min_purchase = self._min_purchase(text)

        requirements: List[str] = []
        tiers = re.findall(r'\$\s?([\d.]+)\s+HASTA\s+(\d{1,2})\s+CUOTAS', text)
        if tiers:
            requirements.append('; '.join(
                f"{n} cuotas sin interés desde {self._format_amount(a)}" for a, n in tiers))
        if re.search(r'JUBILAD', text):
            requirements.append('Exclusivo jubilados (según legal)')
        if plan == 'Plan Z':
            requirements.append('Comprando en Plan Z')
        elif plan:
            requirements.append(f'Para clientes {plan}')
        extra = re.search(r'ADICIONALMENTE.*?\.(?=\s|$)', text)
        if extra:
            requirements.append(extra.group(0).capitalize())
        if 'PRIMERA TRANSACCI' in text:
            requirements.append('Aplica sólo a la primera transacción del día')
        if re.search(r'NFC|SIN CONTACTO', text) and wallet == 'Cuenta DNI':
            requirements.append('Pago sin contacto (NFC) con Cuenta DNI')
        if re.search(r'PAGO CLAVE DNI', text):
            requirements.append('Pago con Clave DNI desde la app Cuenta DNI')

        exclusions = ''
        excl = re.search(r'(?:NO APLICA|EXCLUYE|NO PARTICIPAN).*?\.(?=\s|$)', text)
        if excl:
            exclusions = excl.group(0).capitalize()

        title_entity = entity_label if not (bank and wallet and wallet != 'Cuenta DNI') else f"{entity_label} + {wallet}"
        title = f"{title_entity} {discount}"
        qualifier = plan or self._card_qualifier(editor_title, entity_label)
        if qualifier:
            title += f" ({qualifier})"
        title += f" - {valid_days or 'Todos los días'}"
        if store_types == 'Online':
            title += ' - Online'
        elif store_types.startswith('Tiendas') and store_types != 'Online, Tiendas':
            title += f" - {store_types}"

        source_key = re.search(r'images/([0-9a-f-]{36})', image)
        return {
            'title': title,
            'discount': discount,
            'bank': bank,
            'wallet': wallet,
            'card_type': card_type,
            'payment_method': payment_method,
            'store_types': store_types,
            'valid_days': valid_days or 'Todos los días',
            'valid_from': valid_from,
            'valid_until': valid_until,
            'tope': tope,
            'min_purchase': min_purchase,
            'url': self.base_url,
            'image_url': image,
            'terms_raw': terms,
            'exclusions': exclusions,
            'requirements': ' | '.join(requirements),
            'source_id': f"dia-{source_key.group(1) if source_key else index}",
        }

    @staticmethod
    def _clean(value: Any) -> str:
        return re.sub(r'\s+', ' ', str(value or '')).strip()

    @staticmethod
    def _resolve_entity(banks: List[str], editor_title: str, text: str) -> Tuple:
        brands = [name for pattern, name in _CARD_BRANDS
                  if any(re.search(pattern, b, re.I) for b in banks)]
        candidates = [b for b in banks if b] + [editor_title]
        # "5% BNA MODO" asocia [Modo, BNA]: el banco manda y MODO es billetera.
        for candidate in sorted(candidates, key=lambda c: bool(re.match(r'^modo$', c, re.I))):
            for pattern, entity in _ENTITIES:
                if re.search(pattern, candidate, re.I):
                    return entity + (brands,)
        if brands:
            # "3CSI TC": tarjetas de crédito de todas las marcas, sin banco.
            return (None, None, 'Tarjetas de crédito', brands)
        return (None, None, editor_title, brands)

    @staticmethod
    def _card_qualifier(editor_title: str, entity_label: str) -> str:
        # "Sidecreer BLACK", "Cuenta Dni Visa": la variante va en el título.
        extra = re.sub(r'\b\d{2}-\d{2}\b', ' ', editor_title)  # "Prex 05-10" (fecha)
        extra = re.sub(r'\d{1,3}\s*%|\b\d*\s*C?SI\b|\bCI\b|de reintegro|[-+]', ' ', extra, flags=re.I)
        for word in re.split(r'\s+', entity_label):
            extra = re.sub(rf'\b{re.escape(word)}\b', ' ', extra, flags=re.I)
        extra = re.sub(r'\b(dni|cuenta|banco|naranja|tc|modo|bna)\b', ' ', extra, flags=re.I)
        extra = re.sub(r'\s+', ' ', extra).strip()
        return extra.title() if extra else ''

    def _discount(self, editor_title: str, text: str, facts: Dict) -> Tuple[str, str]:
        """Devuelve (beneficio, plan). El rótulo de la tarjeta manda sobre el legal."""
        plan = ''
        percent = facts.get('percent')
        title_pct = re.search(r'(\d{1,3})\s*%', editor_title)
        if not percent and title_pct:
            percent = int(title_pct.group(1))
        if not percent:
            # Porcentajes del legal ignorando tasas (TNA/TEA/CFT 0,00%).
            values = [int(v) for v in re.findall(r'(?<![\d,])(\d{1,2})\s?%', text) if int(v) > 0]
            percent = max(values) if values else None
        if not percent:
            percent = self._percent_from_example(text)

        cuotas = [int(n) for n in re.findall(r'(\d{1,2})\s+CUOTAS\s+SIN\s+INTER', text)]
        title_cuotas = re.search(r'\b(\d{1,2})\s*C(?:S)?I\b', editor_title, re.I)
        if title_cuotas:
            cuotas.append(int(title_cuotas.group(1)))
        cuotas_label = ''
        if cuotas:
            top = max(cuotas)
            tiered = len(set(cuotas)) > 1 or re.search(rf'HASTA\s+{top}\s+CUOTAS', text)
            cuotas_label = f"{'Hasta ' if tiered else ''}{top} cuotas sin interés"
            if re.search(r'PLAN Z', text):
                plan = 'Plan Z'
        if re.search(r'PLAN\s+(INICIAL|TURBO|[ÉE]PICO)', text) and percent:
            tier = re.search(rf'PLAN\s+(INICIAL|TURBO|[ÉE]PICO):\s*{percent}%', text)
            if tier:
                plan = 'Plan ' + tier.group(1).capitalize().replace('Epico', 'Épico')

        if percent:
            kind = 'reintegro' if re.search(r'REINTEGRO|CASHBACK|BONIFICACI', text) or facts else 'descuento'
            label = f"{percent}% {kind}"
            if cuotas_label and cuotas_label.endswith('sin interés'):
                label += f" + {cuotas_label.replace('Hasta ', 'hasta ')}"
            return label, plan
        return cuotas_label, plan

    @staticmethod
    def _percent_from_example(text: str) -> Optional[int]:
        """'En un consumo de $60.000 recibirá un reintegro de $15.000' → 25."""
        match = re.search(
            r'(?:CONSUMO|COMPRA)\s+DE\s+\$\s?([\d.]+).{0,40}?REINTEGRO\s+DE\s+\$\s?([\d.]+)', text)
        if not match:
            return None
        base, back = (int(re.sub(r'\D', '', v)) for v in match.groups())
        if not base:
            return None
        ratio = back * 100 / base
        return int(ratio) if ratio.is_integer() and 0 < ratio < 100 else None

    @staticmethod
    def _format_amount(raw: str) -> str:
        digits = re.sub(r'[.,]\d{2}$', '', raw.strip().rstrip('.-,'))
        digits = re.sub(r'\D', '', digits)
        return f"${int(digits):,}".replace(',', '.') if digits else ''

    def _plan_tope(self, text: str, discount: str) -> Optional[str]:
        pct = re.match(r'(\d{1,3})%', discount)
        if not pct:
            return None
        match = re.search(
            rf'PLAN\s+[A-ZÉ]+:\s*{pct.group(1)}%[^.;()]*?TOPE\s+DE\s+\$\s?([\d.,]+)\s+POR\s+SEMANA', text)
        return f"{self._format_amount(match.group(1))} semanal" if match else None

    def _extract_tope(self, text: str) -> Optional[str]:
        if not text:
            return None
        amounts = []
        for match in re.finditer(
            r'(?:TOPE|L[ÍI]MITE)\s+(?:M[ÁA]XIMO\s+)?(?:DE\s+)?(?:REINTEGRO\s+|DEVOLUCI[ÓO]N\s*|DESCUENTO\s+DEL\s+BENEFICIO\s+ES\s+)?'
            r'(?:UNIFICADO\s+)?(?:DE\s+)?:?\s*(?:HASTA\s+)?(?:PESOS\s+[A-Z ]+)?\(?\$\s?(\d[\d.,]*)([^$]{0,70})',
            text,
        ):
            value = int(re.sub(r'\D', '', re.sub(r'[.,]\d{2}$', '', match.group(1).rstrip('.-,'))) or 0)
            if not value:
                continue
            if value >= 1_000_000:
                # "Límite de $ 9999999 por usuario": en la práctica sin tope.
                return 'Sin tope'
            tail = re.split(r'\.\s', match.group(2), maxsplit=1)[0]
            period = ''
            if re.search(r'SEMANA', tail):
                period = ' semanal'
            elif re.search(r'\bMES\b|MENSUAL', tail):
                period = ' mensual'
            elif re.search(r'TRANSACCI', tail):
                period = ' por transacción'
            amounts.append((self._format_amount(match.group(1)), period))
        if amounts:
            amount, period = amounts[0]
            # "(CON TOPE DE $5.000,00)" ... "TOPE DE PESOS CINCO MIL ($5.000,00) POR TRANSACCIÓN"
            period = period or next((p for a, p in amounts if a == amount and p), '')
            return f"{amount}{period}"
        if re.search(r'SIN\s+(?:TOPE|L[ÍI]MITE)', text):
            return 'Sin tope'
        return None

    @staticmethod
    def _min_purchase(text: str) -> Optional[str]:
        match = re.search(
            r'(?:M[ÍI]NIMO\s+DE\s+(?:COMPRA\s*:?\s*(?:DE\s+)?)?|MONTO\s+MAYOR\s+O\s+IGUAL\s+A\s+|'
            r'COMPRAS?\s+MAYOR(?:ES)?\s+O\s+IGUAL(?:ES)?\s+A\s+|COMPRAS\s+DESDE\s+)\$\s?(\d[\d.]*)',
            text,
        )
        if not match:
            return None
        return DiaScraper._format_amount(match.group(1))

    @staticmethod
    def _valid_days(days: Dict) -> Optional[str]:
        names = [name for key, name in _DAY_KEYS if days.get(key)]
        if not names or len(names) == 7:
            return 'Todos los días' if names else None
        return ', '.join(names)

    @staticmethod
    def _validity(text: str) -> Tuple[Optional[str], Optional[str]]:
        def iso(d, m, y) -> Optional[str]:
            y = int(y)
            y += 2000 if y < 100 else 0
            try:
                return date(y, int(m), int(d)).isoformat()
            except ValueError:
                return None

        # "DEL 01/10/2026 AL 31/10/2026", "DESDE EL 01/10/2026 HASTA EL 31/03/2027"
        match = re.search(
            r'(\d{1,2})/(\d{1,2})/(\d{2,4})(?:\s+\d{1,2}:\d{2})?\s+(?:AL|HASTA(?:\s+EL)?|Y\s+EL)\s+'
            r'(\d{1,2})/(\d{1,2})/(\d{2,4})', text)
        if match:
            g = match.groups()
            return iso(*g[:3]), iso(*g[3:])
        # "ENTRE EL 1 DE OCTUBRE Y EL 31 DE DICIEMBRE DE 2026"
        match = re.search(
            rf'(\d{{1,2}})\s+DE\s+({_MONTH_RE.upper()})(?:\s+DE\s+(\d{{4}}))?\s+(?:Y\s+EL|AL|HASTA\s+EL)\s+'
            rf'(\d{{1,2}})\s+DE\s+({_MONTH_RE.upper()})\s+DE(?:L)?\s+(\d{{4}})', text)
        if match:
            d1, m1, y1, d2, m2, y2 = match.groups()
            return iso(d1, _MONTHS[m1.lower()], y1 or y2), iso(d2, _MONTHS[m2.lower()], y2)
        # "LOS MARTES DEL MES DE OCTUBRE DE 2026", "LOS MIÉRCOLES DE OCTUBRE, NOVIEMBRE Y DICIEMBRE DE 2026"
        match = re.search(
            rf'(?:DEL\s+MES\s+DE\s+|\bDE\s+)((?:(?:{_MONTH_RE.upper()})(?:\s*,\s*|\s+Y\s+)?)+)\s+DE(?:L)?\s+(\d{{4}})',
            text)
        if match:
            months = [_MONTHS[m.lower()] for m in re.findall(_MONTH_RE.upper(), match.group(1))]
            year = int(match.group(2))
            last = date(year + (months[-1] == 12), months[-1] % 12 + 1, 1)
            from datetime import timedelta
            return date(year, months[0], 1).isoformat(), (last - timedelta(days=1)).isoformat()
        # Fecha puntual: "EL DÍA LUNES 05/10/2026"
        match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
        if match:
            single = iso(*match.groups())
            return single, single
        return None, None

    @staticmethod
    def _store_types(available: Dict, text: str, bank: Optional[str]) -> str:
        channels = []
        if available.get('online'):
            channels.append('Online')
        if available.get('store'):
            region = _REGIONAL_ENTITIES.get(bank or '')
            province = re.search(r'TIENDAS D[ÍI]A ADHERIDAS:\s*SOLO LAS LOCALIZADAS EN LA PROVINCIA DE ([A-ZÁÉÍÓÚ ]+?)\.', text)
            if province:
                region = province.group(1).title().replace('Rios', 'Ríos')
            channels.append(f"Tiendas de {region}" if region else 'Tiendas')
        return ', '.join(channels) or 'Online, Tiendas'

    @staticmethod
    def _card_type(text: str, discount: str) -> Optional[str]:
        positive = DiaScraper._positive_text(text)
        types = []
        if re.search(r'CR[ÉE]DITO', positive):
            types.append('Crédito')
        if re.search(r'D[ÉE]BITO', positive):
            types.append('Débito')
        if not types and 'cuotas' in discount:
            types.append('Crédito')
        return ', '.join(types) or None

    @staticmethod
    def _payment_method(text: str, wallet: Optional[str], brands: List[str],
                        card_type: Optional[str], bank: Optional[str] = None) -> Optional[str]:
        if brands:
            return ', '.join(dict.fromkeys(brands))
        positive = DiaScraper._positive_text(text)
        text_brands = [name for pattern, name in _CARD_BRANDS if re.search(pattern, positive, re.I)]
        if wallet == 'MODO':
            return ' - '.join(['QR MODO'] + ([', '.join(text_brands)] if bank and text_brands else []))
        if wallet == 'Cuenta DNI':
            return 'Cuenta DNI (Clave DNI)' if 'CLAVE DNI' in text else 'Cuenta DNI (NFC)' if 'NFC' in text else 'Cuenta DNI'
        if wallet == 'Mercado Pago':
            return 'QR Mercado Pago' if re.search(r'\bQR\b', text) else 'Mercado Pago'
        if wallet:
            return wallet
        if 'CIUDADAN' in text:
            return 'Tarjeta Ciudadanía Porteña'
        if bank and text_brands:
            return ', '.join(text_brands) + (f" ({card_type})" if card_type else '')
        return card_type

    @staticmethod
    def _positive_text(text: str) -> str:
        # Las frases de exclusión ("no aplica a ... tarjeta de crédito") no
        # definen el medio de pago de la promo.
        return ' '.join(s for s in re.split(r'(?<=\.)\s+', text)
                        if not re.search(r'NO APLICA|NO PARTICIPAN|EXCLU|NI LAS', s))


async def main():
    scraper = DiaScraper()
    promotions = await scraper.scrape()
    print(f"\n{'='*100}")
    for i, promo in enumerate(promotions, 1):
        print(f"{i:2d}. {promo['title']}")
        print(f"    💰 {promo['discount']} | 🏦 {promo.get('bank')} / {promo.get('wallet')} | "
              f"💳 {promo.get('card_type')} · {promo.get('payment_method')} | 🏪 {promo['store_types']} | "
              f"📅 {promo.get('valid_days')} {promo.get('valid_from')}→{promo.get('valid_until')} | "
              f"🧢 {promo.get('tope')} | 🛒 {promo.get('min_purchase')}")
        if promo.get('requirements'):
            print(f"    ✅ {promo['requirements']}")


if __name__ == "__main__":
    asyncio.run(main())
