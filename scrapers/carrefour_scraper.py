"""
Carrefour scraper — Descuentos Bancarios

Usa Crawl4AI para esperar el render del componente VTEX antes de capturar el HTML.
Esto reemplaza los asyncio.sleep() y retry loops del approach anterior con una
condición determinística: wait_for='css:[vtex-card-selector]'.

Flujo:
  1. Crawl4AI navega a la URL y espera hasta que los cardBox VTEX aparezcan en el DOM
  2. js_code expande todos los "Ver Legal" antes de la captura
  3. delay_before_return_html da 1.5s para que el contenido se estabilice
  4. result.html se parsea con BeautifulSoup (lógica existente sin cambios)
"""
from typing import List, Dict, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import os


_VTEX_CARD = '[class*="valtech-carrefourar-bank-promotions"][class*="cardBox"]'

_JS_EXPAND_LEGAL = (
    'document.querySelectorAll(\'[class*="legalHeader"]\')'
    ".forEach(b => { try { b.click(); } catch(e) {} });"
)


class CarrefourScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Carrefour',
            url='https://www.carrefour.com.ar/descuentos-bancarios'
        )

    async def scrape(self, page=None) -> List[Dict]:
        """
        page aceptado para compatibilidad con BaseScraper pero no se usa.
        Carrefour crea su propio browser via Crawl4AI (standalone).
        """
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
        except ImportError:
            print("   ⚠️ crawl4ai no instalado — instalá con: pip install crawl4ai && crawl4ai-setup")
            return []

        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.url}")

        browser_cfg = BrowserConfig(headless=True, verbose=False)
        run_cfg = CrawlerRunConfig(
            wait_for=f"css:{_VTEX_CARD}",
            js_code=_JS_EXPAND_LEGAL,
            delay_before_return_html=1.5,
            page_timeout=60000,
            cache_mode=CacheMode.BYPASS,
        )

        try:
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                result = await crawler.arun(self.url, config=run_cfg)
        except Exception as e:
            print(f"❌ Error en {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return []

        if not result.success:
            print(f"   ❌ Crawl4AI falló: {result.error_message}")
            return []

        if os.environ.get('DEBUG_SCRAPER'):
            with open('debug_carrefour.html', 'w', encoding='utf-8') as f:
                f.write(result.html)
            print("   📄 HTML guardado: debug_carrefour.html")

        print(f"   ✅ Página renderizada — parseando VTEX cards...")
        promos = self._extract_vtex_cards(result.html)
        print(f"✅ {self.name}: {len(promos)} promociones encontradas")
        return promos

    # ──────────────────────────────────────────────────────────
    # Parsing VTEX (sin cambios respecto a la versión anterior)
    # ──────────────────────────────────────────────────────────

    def _extract_vtex_cards(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        card_boxes = soup.find_all('div', class_=re.compile(r'valtech-carrefourar-bank-promotions.*cardBox'))
        print(f"   🔍 VTEX cardBox encontradas: {len(card_boxes)}")

        promotions = []
        for card in card_boxes:
            try:
                promo = self._parse_vtex_card(card)
                if promo and promo.get('discount'):
                    promotions.append(promo)
            except Exception:
                pass

        # Dedup por (entidad, descuento, días)
        seen: set = set()
        unique: List[Dict] = []
        for p in promotions:
            entity = (p.get('bank') or p.get('wallet') or p.get('card_type') or '').lower()
            key = (entity, p.get('discount', ''), (p.get('valid_days') or '').lower())
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

    def _parse_vtex_card(self, card) -> Optional[Dict]:
        # Días válidos
        date_elem = card.find('span', class_=re.compile(r'dateText'))
        valid_days = date_elem.get_text(strip=True) if date_elem else None

        # Tipos de tienda
        store_types: List[str] = []
        for icon in card.find_all('div', class_=re.compile(r'logoIcon')):
            cls = ' '.join(icon.get('class', []))
            if 'logoMain' in cls:     store_types.append('Hipermercado')
            elif 'logoMarket' in cls: store_types.append('Market')
            elif 'logoExpress' in cls: store_types.append('Express')
            elif 'logoMaxi' in cls:   store_types.append('Maxi')
            elif 'logoOnline' in cls:  store_types.append('Online')

        # Descuento
        pct = card.find('span', class_=re.compile(r'ColLeftPercentage'))
        sym = card.find('span', class_=re.compile(r'ColLeftPercentageSymbol'))
        discount = ''
        if pct and sym:
            discount = f"{pct.get_text(strip=True)}{sym.get_text(strip=True)}"
        elif pct:
            discount = pct.get_text(strip=True)

        # Imagen para identificar banco
        img_elem = card.find('img', class_=re.compile(r'valtech-carrefourar-bank-promotions.*Image'))
        image_url = ''
        if img_elem:
            src = img_elem.get('src', '') or img_elem.get('data-src', '') or ''
            image_url = src if src.startswith('http') else f"https://www.carrefour.com.ar{src}"

        # Título
        title_parts: List[str] = []
        t = card.find('span', class_=re.compile(r'ColRightTittle'))
        d = card.find('span', class_=re.compile(r'ColRightText'))
        if t: title_parts.append(t.get_text(strip=True))
        if d:
            dt = d.get_text(strip=True)
            if dt: title_parts.append(dt)
        title = ' '.join(title_parts) or None

        # Términos y condiciones
        footer = card.find('div', class_=re.compile(r'cardFooter'))
        terms_raw = ''
        if footer:
            paras = [p.get_text(' ', strip=True) for p in footer.find_all('p') if len(p.get_text(strip=True)) > 50]
            terms_raw = ' '.join(paras)
        if not terms_raw:
            upper = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{200,}', card.get_text(' ', strip=True))
            if upper:
                terms_raw = max(upper, key=len)

        # Banco / billetera desde URL de imagen
        bank: Optional[str] = None
        wallet: Optional[str] = None
        card_type: Optional[str] = None
        img_lower = image_url.lower()
        if 'cuenta_dni' in img_lower or 'cuentadni' in img_lower:
            bank = 'Banco Provincia'; wallet = 'Cuenta DNI'
        elif 'mercadopago' in img_lower or 'mercado_pago' in img_lower or 'mercado-pago' in img_lower:
            wallet = 'Mercado Pago'
        elif 'carrefour' in img_lower and 'credito' in img_lower:
            bank = 'Carrefour Banco'; card_type = 'Tarjeta Mi Carrefour Crédito'
        elif 'carrefour' in img_lower and 'prepaga' in img_lower:
            bank = 'Carrefour Banco'; card_type = 'Tarjeta Mi Carrefour Prepaga'
        elif 'bna' in img_lower or 'nacion' in img_lower:
            bank = 'Banco Nación'
        elif 'naranja' in img_lower:
            card_type = 'Naranja'
        elif 'modo' in img_lower:
            wallet = 'MODO'

        # Fallback a texto
        all_text = card.get_text(' ', strip=True)
        if not bank and not wallet and not card_type:
            bank = self.extract_bank(all_text)
            wallet = self.extract_wallet(all_text)

        if not discount:
            discount = self.extract_discount(all_text)
        if not title:
            entity = bank or wallet or card_type
            title = f"{discount} con {entity}" if (discount and entity) else entity
        if not title:
            return None

        return {
            'title':          self.clean_text(title),
            'discount':       discount,
            'bank':           bank,
            'wallet':         wallet,
            'card_type':      card_type,
            'payment_method': None,
            'store_types':    ', '.join(store_types) if store_types else None,
            'valid_days':     valid_days,
            'url':            self.url,
            'image_url':      image_url,
            'terms_raw':      self.clean_text(terms_raw),
            'exclusions':     None,
            'requirements':   None,
            'valid_from':     None,
            'valid_until':    None,
        }
