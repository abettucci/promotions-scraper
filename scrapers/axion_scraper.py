"""
Scraper de Axion Energy — Beneficios y promociones

La página es WordPress + Elementor y el contenido está completo en la API REST:
  GET https://www.axionenergy.com/wp-json/wp/v2/pages/604  → content.rendered

Cada promo es un container de Elementor con:
  · widget image-box: logo (el nombre del archivo identifica al banco:
    promo-brubank.jpg, promo-modocomafi.png, Logo-Banco-Patagonia.png...),
    <h3> = titular ("VIERNES 20% DE DESCUENTO") y <p> = "HASTA EL 31/10/2026"
  · widget nested-accordion ("VER MÁS") con el legal completo (oculto en DOM)

Parseo determinístico (sin navegador ni IA). Si un legal agrupa varios
tramos con beneficios distintos (Patagonia Plus / Singular, Galicia /
Éminent) se emite una promo por tramo.

Nota: el servidor de Axion no envía el certificado intermedio; si la
verificación TLS falla se reintenta sin verificar (sitio público, sólo lectura).
"""
import asyncio
import re
from datetime import date
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from fuel_conditions import extract_fuel_conditions
from .shell_scraper import (
    _BANKS, _WEEKDAYS, _clean, _money, _period, _positive_sentences, parse_dates,
)


API_URL = 'https://www.axionenergy.com/wp-json/wp/v2/pages/604'
PAGE_URL = 'https://www.axionenergy.com/beneficios-y-promociones/'
_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json,text/html;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-AR,es;q=0.9',
}
_TIMEOUT = 30

# Marcadores de tramo dentro de un mismo legal
_SEGMENT_RE = re.compile(
    r'CARTERA\s+DE\s+CONSUMO\s*\(\d+\)\.?|CLIENTES\s+[A-ZÁÉÍÓÚ]+(?:\s+[A-ZÁÉÍÓÚ]+){0,3}\s+PLAN\s+SUELDO\s*:',
)
_NUM_WORDS = {'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
              'seis': 6, 'siete': 7, 'ocho': 8, 'diez': 10}


class AxionScraper:
    def __init__(self):
        self.name = 'Axion'
        self.url = PAGE_URL

    async def scrape(self) -> List[Dict]:
        print(f"\n🔍 Scraping {self.name}...")
        print(f"   🌐 {API_URL}")
        html = await asyncio.to_thread(self._fetch_html)
        if not html:
            print(f"   ❌ {self.name}: no se pudo obtener la página — 0 promos")
            return []
        promos = self.parse_html(html)
        for p in promos:
            entity = p['bank'] or p['wallet'] or '?'
            print(f"      + {entity:18s} | {p['discount']:30s} | {p['valid_days'] or '—':24s} "
                  f"| {p['valid_from'] or '—'} → {p['valid_until'] or '—'} | tope: {p['tope'] or '—'}")
        print(f"\n✅ {self.name}: {len(promos)} promociones")
        return promos

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP
    # ─────────────────────────────────────────────────────────────────────────

    def _get(self, url: str) -> Optional[requests.Response]:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        except requests.exceptions.SSLError:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            print("   ⚠️ TLS incompleto en axionenergy.com — reintento sin verificar certificado")
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, verify=False)
        r.raise_for_status()
        return r

    def _fetch_html(self) -> str:
        try:
            data = self._get(API_URL).json()
            html = ((data or {}).get('content') or {}).get('rendered') or ''
            if 'image-box' in html:
                return html
            print("   ⚠️ API sin image-box — pruebo con el HTML de la página")
        except Exception as e:
            print(f"   ⚠️ Error en API WP ({e}) — pruebo con el HTML de la página")
        try:
            return self._get(PAGE_URL).text
        except Exception as e:
            print(f"   ❌ Error al obtener {PAGE_URL}: {e}")
            return ''

    # ─────────────────────────────────────────────────────────────────────────
    # Parseo
    # ─────────────────────────────────────────────────────────────────────────

    def parse_html(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        promos: List[Dict] = []
        titles: Dict[str, int] = {}
        for box in soup.select('.elementor-widget-image-box'):
            container = box.find_parent(attrs={'data-element_type': 'container'})
            legal_el = container.select_one('.elementor-widget-text-editor') if container else None
            legal = _clean(legal_el.get_text(' ', strip=True)) if legal_el else ''
            h3 = box.select_one('.elementor-image-box-title')
            desc = box.select_one('.elementor-image-box-description')
            img = box.find('img')
            card = {
                'id': box.get('data-id') or '',
                'headline': _clean(h3.get_text(' ', strip=True)) if h3 else '',
                'subtitle': _clean(desc.get_text(' ', strip=True)) if desc else '',
                'image': (img.get('src') or '') if img else '',
            }
            if not card['headline'] and not legal:
                continue
            for promo in self._parse_card(card, legal):
                base = promo['title']
                n = titles.get(base, 0)
                titles[base] = n + 1
                if n:
                    promo['title'] = f"{base} ({n + 1})"
                promos.append(promo)
        return promos

    def _parse_card(self, card: Dict, legal: str) -> List[Dict]:
        marks = list(_SEGMENT_RE.finditer(legal))
        if len(marks) >= 2:
            preamble = legal[:marks[0].start()]
            out = []
            for i, m in enumerate(marks):
                end = marks[i + 1].start() if i + 1 < len(marks) else len(legal)
                segment = legal[m.start():end].strip()
                promo = self._build(card, legal, segment, preamble, idx=i + 1, marker=m.group(0))
                if promo:
                    out.append(promo)
            if out:
                return out
        promo = self._build(card, legal, legal, '', idx=0, marker='')
        return [promo] if promo else []

    def _build(self, card: Dict, full_legal: str, segment: str, preamble: str,
               idx: int, marker: str) -> Optional[Dict]:
        headline, subtitle = card['headline'], card['subtitle']
        filename = re.sub(r'[-_.]+', ' ', card['image'].rsplit('/', 1)[-1])
        seg_pos = _positive_sentences(segment)
        legal_pos = _positive_sentences(full_legal)

        # ── Entidad ──────────────────────────────────────────────────────────
        bank = self._identify(_BANKS, filename) or self._identify(_BANKS, legal_pos)
        wallet = None
        if re.search(r'quantium|\bON\b', filename + ' ' + headline, re.I) or \
                re.search(r'usuarios\s+ON\b|programa\s+ON\b', full_legal, re.I):
            bank, wallet = None, 'ON Axion'
        elif re.search(r'\bMODO\b', legal_pos + ' ' + filename, re.I):
            wallet = 'MODO'
        payment_method = None
        if wallet == 'MODO':
            payment_method = 'MODO BNA+' if re.search(r'BNA\s*\+', full_legal, re.I) else 'QR MODO'

        # ── Beneficio ────────────────────────────────────────────────────────
        qualifier = self._qualifier(marker, segment)
        if idx:
            pct = self._pct(segment)
            discount = f"{pct}%" if pct else self._headline_discount(headline)
        else:
            discount = self._headline_discount(headline) or (f"{self._pct(segment)}%" if self._pct(segment) else '')
            extra = re.search(r'(?:adem[aá]s|adicional)[^.]{0,40}?para\s+clientes\s+(?:del\s+segmento\s+)?'
                              r'([^.,]{3,50}?)\s+con\b[^.]*?(\d{1,2})\s*%', segment, re.I) or \
                re.search(r'para\s+clientes\s+(?:del\s+segmento\s+)?([^.,]{3,50}?)\s+con\b[^.]*?'
                          r'se\s+adicionar[aá]\s+un\s+(\d{1,2})\s*%', segment, re.I)
            if extra and discount:
                discount += f" (+{extra.group(2)}% {self._clean_qual(extra.group(1))})"
        if not discount:
            return None

        # ── Vigencia y días ──────────────────────────────────────────────────
        valid_from, valid_until = parse_dates(f"{preamble} {segment}")
        if not (valid_from or valid_until):
            valid_from, valid_until = parse_dates(f"{subtitle} {headline}")
        _, sub_until = parse_dates(subtitle)
        if sub_until and not valid_until:
            valid_until = sub_until
        days = self._days(headline) or self._days(full_legal[:400])
        if not days and valid_from and valid_from == valid_until:
            days = _WEEKDAYS[date.fromisoformat(valid_from).weekday()]
        days = days or 'Todos los días'

        tope = self._tope(segment)
        card_type = self._card_type(seg_pos) or self._card_type(segment)

        entity = bank or wallet or 'Axion'
        title = f"{entity} {discount.split(' (')[0]}"
        if qualifier:
            title += f" {qualifier}"
        title += f" - {days}"

        requirements, exclusions = extract_fuel_conditions(segment)
        return {
            'supermarket':    self.name,
            'title':          title,
            'description':    f"{headline} — {subtitle}".strip(' —'),
            'discount':       discount,
            'bank':           bank,
            'wallet':         wallet,
            'card_type':      card_type,
            'payment_method': payment_method,
            'tope':           tope,
            'valid_days':     days,
            'valid_from':     valid_from,
            'valid_until':    valid_until,
            'exclusions':     ' | '.join(exclusions),
            'requirements':   ' | '.join(requirements + ([f"Clientes {qualifier}"] if qualifier else [])),
            'terms_raw':      (f"{preamble} {segment}".strip() if idx else full_legal) or headline,
            'image_url':      card['image'],
            'url':            self.url,
            'source_id':      f"axion:{card['id']}" + (f":{idx}" if idx else ''),
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
    def _pct(text: str) -> Optional[str]:
        m = re.search(r'(\d{1,2})\s*%\s*(?:\([^)]*\)\s*)?de\s+(?:descuento|ahorro|reintegro|bonificaci[oó]n)', text or '', re.I) \
            or re.search(r'(?:descuento|ahorro|reintegro)\s+del?\s+(\d{1,2})\s*%', text or '', re.I)
        return m.group(1) if m else None

    @staticmethod
    def _headline_discount(headline: str) -> str:
        h = headline or ''
        m = re.search(r'hasta\s+(\d{1,2})\s*%', h, re.I)
        if m:
            return f"Hasta {m.group(1)}%"
        pcts = re.findall(r'(\d{1,2})\s*%', h)
        if len(pcts) >= 2:
            return ' o '.join(f"{p}%" for p in pcts)
        return f"{pcts[0]}%" if pcts else ''

    @staticmethod
    def _clean_qual(q: str) -> str:
        q = re.sub(r'\s+(?:y|o)\s+', '/', (q or '').strip())
        return ' '.join(w if w.isupper() and len(w) <= 3 else w.capitalize() if w.isupper() else w
                        for w in q.split())

    def _qualifier(self, marker: str, segment: str) -> str:
        """'CLIENTES PATAGONIA PLUS EXCLUSIVO PLAN SUELDO:' → 'Plus Plan Sueldo'."""
        if marker:
            m = re.match(r'CLIENTES\s+(.+?)\s*:', marker)
            if m:
                words = [w for w in m.group(1).split() if w not in ('PATAGONIA', 'EXCLUSIVO')]
                return ' '.join(w.capitalize() for w in words)
            m = re.search(r'para\s+clientes\s+([ÉE]minent|Black|Singular|Plus|Haberes)\b', segment, re.I)
            return m.group(1).capitalize() if m else ''
        m = re.search(r'CLIENTES\s+(?:\w+\s+){0,2}?(PLAN\s+(?:ULTRA|PLUS))\b', segment, re.I)
        return m.group(1).title() if m else ''

    def _tope(self, text: str) -> Optional[str]:
        if re.search(r'sin\s+tope', text, re.I):
            return 'Sin tope'
        found: List[Tuple[int, str, str, str]] = []  # (pos, monto, periodo, calificador)
        for m in re.finditer(r'(?:tope|devoluci[oó]n)\b([^$]{0,70}?)\$\s*([\d.]+)', text, re.I):
            amount = _money(m.group(2))
            after = text[m.end():m.end() + 120]
            period = _period(m.group(1) + ' ' + after[:45])
            qual = ''
            q = re.match(r'[^.$]{0,40}?para\s+(?:clientes\s+)?([^.$]{3,60}?)(?=\.|\s+y\s+de\s+\$|$)', after, re.I)
            if q:
                qual = self._tier_qual(q.group(1))
            else:
                q = re.search(r'para\s+([^,.$]{3,30}?)\s+el\s+tope\s*$', text[max(0, m.start() - 40):m.start() + 4], re.I)
                if q:
                    qual = re.sub(r'[()]', '', q.group(1))
            found.append((m.start(), amount, period, qual))
        # "de $7.000 mensuales para niveles 1 y 2 y de $14.000 mensuales para ..."
        for m in re.finditer(r'\by\s+de\s+\$\s*([\d.]+)\s+(\w+)(?:\s+para\s+([^.$]{3,40}))?', text, re.I):
            found.append((m.start(), _money(m.group(1)), _period(m.group(2)), self._tier_qual(m.group(3) or '')))
        found.sort()

        if not found:
            # Credicoop: "reintegro de $4.500 o $6.000 ... Topes máximos por usuario/a por semana"
            m = re.search(r'reintegro\s+de\s+\$\s*([\d.]+)\s+o\s+\$\s*([\d.]+)', text, re.I)
            per = re.search(r'topes?\s+m[aá]xim\w*[^.]{0,40}', text, re.I)
            if m and per:
                return f"{_money(m.group(1))} o {_money(m.group(2))} {_period(per.group(0))}".strip()
            return None

        uniq = []
        for _, a, p, q in found:
            if a and (a, p, q) not in uniq and not (len(found) > 1 and (a, p, '') in uniq and not q):
                uniq.append((a, p, q))
        if len({(a, p) for a, p, _ in uniq}) == 1:
            uniq = uniq[:1]
        if len(uniq) == 1:
            tope = f"{uniq[0][0]} {uniq[0][1]}".strip()
        else:
            tope = '; '.join(f"{a} {p}".strip() + (f" ({q})" if q else '') for a, p, q in uniq)

        uses = re.search(r'L[IÍ]MITE\s+DE\s+(\w+)\s+PARTICIPACIONES(\s+MENSUALES)?', text, re.I)
        if uses:
            n = uses.group(1).lower()
            n = _NUM_WORDS.get(n, n)
            tope += f" (máx. {n} usos{' por mes' if uses.group(2) else ''})"
        return tope

    @staticmethod
    def _tier_qual(q: str) -> str:
        q = (q or '').strip()
        if re.match(r'niveles?\b', q, re.I):
            return q
        return re.sub(r'\s*(?:,|\by/o\b|\by\b|\bo\b)\s*', '/', q).strip('/')

    @staticmethod
    def _card_type(text: str) -> Optional[str]:
        # Estricto: "acreditado como un crédito en el resumen" no es tarjeta de crédito
        t = (text or '').lower()
        credit = bool(re.search(r'tarjetas?\s+(?:de\s+)?(?:\w+\s+){0,3}?cr[eé]dito|cr[eé]dito\s+(?:visa|master|brubank)', t))
        debit = bool(re.search(r'tarjetas?\s+(?:de\s+)?(?:\w+\s+){0,3}?d[eé]bito|d[eé]bito\s+(?:visa|master|patagonia)|visa\s+d[eé]bito', t))
        if credit and debit:
            return 'Crédito, Débito'
        if credit:
            return 'Crédito'
        if debit:
            return 'Débito'
        return None

    @staticmethod
    def _days(text: str) -> Optional[str]:
        low = (text or '').lower()
        if re.search(r'todos\s+los\s+d[ií]as(?!\s+(?:viernes|lunes|martes|mi[eé]rcoles|jueves|s[aá]bado|domingo))', low):
            return 'Todos los días'
        found = []
        for wd in _WEEKDAYS:
            stem = wd.lower().replace('é', '[eé]').replace('á', '[aá]')
            if re.search(r'\b' + stem, low):
                found.append(wd)
        return ', '.join(found) or None
