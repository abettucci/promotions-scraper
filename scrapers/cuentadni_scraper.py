"""
Cuenta DNI (Banco Provincia) — Beneficios
URL: https://www.bancoprovincia.com.ar/cuentadni/contenidos/cdniBeneficios/

Sitio server-side rendered (ASP.NET MVC), sin JS necesario. Las cards activas
vienen completas en el HTML inicial. El detalle de cada card (tope, legales,
condiciones, vigencia) se obtiene con una request extra por beneficio a:
  GET /cuentadni/Home/GetBeneficioData2?idBeneficio={id}
"""
import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_BASE = 'https://www.bancoprovincia.com.ar'
_LIST_URL = f'{_BASE}/cuentadni/contenidos/cdniBeneficios/'
_DETAIL_URL = f'{_BASE}/cuentadni/Home/GetBeneficioData2'

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-AR,es;q=0.9',
}


class CuentaDniScraper(BaseScraper):
    def __init__(self):
        super().__init__(name='Cuenta DNI', url=_LIST_URL)

    async def scrape(self, page=None) -> List[Dict]:
        import requests
        from bs4 import BeautifulSoup

        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.url}")

        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(
                None, lambda: requests.get(self.url, headers=_HEADERS, timeout=30)
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"   ❌ Error fetching: {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.select('div.callModalCDNI.BEN_filterDiv')
        print(f"   🔍 {len(cards)} cards encontradas")

        promotions = []
        seen: set = set()

        for card in cards:
            base_promo = self._parse_card(card)
            if not base_promo:
                continue

            beneficio_id = base_promo.pop('_id')
            if beneficio_id in seen:
                continue
            seen.add(beneficio_id)

            detail = await loop.run_in_executor(None, lambda bid=beneficio_id: self._fetch_detail(bid))
            promo = self._merge_detail(base_promo, detail)
            promotions.append(promo)
            print(f"   + {promo.get('title', '')[:60]} ({promo.get('valid_days')})")

        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def _parse_card(self, card) -> Optional[Dict]:
        card_id = card.get('id', '')
        id_m = re.search(r'-(\d+)$', card_id)
        if not id_m:
            return None
        beneficio_id = id_m.group(1)

        titulo_el = card.find('div', class_='tituloBeneficio')
        title = titulo_el.get_text(strip=True) if titulo_el else ''

        dias_el = card.find('div', class_='BEN_CON_dias')
        valid_days = self.clean_text(dias_el.get_text(strip=True)) if dias_el else 'Todos los días'

        nro_el = card.find('div', class_='BEN_CON_nro')
        discount = f"{nro_el.get_text(strip=True)}%" if nro_el else ''

        img_el = card.find('img', class_='logo_recuadro')
        image_url = None
        if img_el and img_el.get('src'):
            src = img_el['src']
            image_url = src if src.startswith('http') else f"{_BASE}{src}"

        if not title and not discount:
            return None

        return {
            '_id':            beneficio_id,
            'title':          self.clean_text(title),
            'discount':       discount,
            'bank':           'Banco Provincia',
            'wallet':         'Cuenta DNI',
            'card_type':      None,
            'payment_method': 'Cuenta DNI',
            'store_types':    None,
            'valid_days':     valid_days,
            'url':            f"{self.url}#{card_id}",
            'image_url':      image_url,
            'terms_raw':      '',
            'tope':           None,
            'min_purchase':   None,
            'exclusions':     [],
            'requirements':   [],
            'valid_from':     None,
            'valid_until':    None,
        }

    def _fetch_detail(self, beneficio_id: str) -> Optional[Dict]:
        import requests
        try:
            resp = requests.get(
                _DETAIL_URL, params={'idBeneficio': beneficio_id},
                headers=_HEADERS, timeout=20,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"   ⚠️ No se pudo obtener detalle de {beneficio_id}: {e}")
            return None

    def _merge_detail(self, promo: Dict, detail: Optional[Dict]) -> Dict:
        if not detail:
            return promo

        entity = detail.get('Entity', {})
        beneficio = entity.get('Beneficio', {})

        bajada = beneficio.get('bajada', '') or ''
        tope_m = re.search(r'\$\s*([\d.,]+)', bajada)
        if tope_m:
            promo['tope'] = f"${tope_m.group(1)}"
        elif bajada and 'sin tope' not in bajada.lower():
            promo['tope'] = self.clean_text(bajada)

        promo['valid_from'] = self._parse_dotnet_date(beneficio.get('fecha_desde'))
        promo['valid_until'] = self._parse_dotnet_date(beneficio.get('fecha_hasta'))

        condiciones = entity.get('Condiciones', []) or []
        exclusions = []
        requirements = []
        for cond in condiciones:
            texto = self.clean_text(cond.get('texto', ''))
            if not texto:
                continue
            if re.search(r'no aplica|excluy|salvo|no incluye', texto, re.IGNORECASE):
                exclusions.append(texto)
            else:
                requirements.append(texto)
        promo['exclusions'] = exclusions
        promo['requirements'] = requirements

        legal = beneficio.get('legal', '') or ''
        promo['terms_raw'] = self.clean_text(legal[:800])

        rubros = entity.get('Rubros', []) or []
        if rubros:
            promo['store_types'] = ', '.join(r.get('nombre', '') for r in rubros if r.get('nombre'))

        botones = entity.get('Botones', []) or []
        for boton in botones:
            if boton.get('link'):
                promo['url'] = boton['link']
                break

        return promo

    @staticmethod
    def _parse_dotnet_date(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        m = re.search(r'/Date\((\d+)\)/', value)
        if not m:
            return None
        try:
            dt = datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc)
            return dt.strftime('%Y-%m-%d')
        except (ValueError, OSError):
            return None
