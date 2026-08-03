#!/usr/bin/env python3
"""
Scraper de Cencosud (Jumbo) - Promociones Bancarias

Usa Crawl4AI con session_id para reutilizar el browser entre días:
  - Cada día tiene su propia URL (?type=por-dia&day=N), se navega normalmente
  - wait_for JS espera hasta que haya contenido con % o cuotas
  - js_code hace scroll + expande "Ver más" antes de capturar el HTML
  - Métodos de parsing sin cambios respecto a versión anterior
"""
import re
import os
from typing import List, Dict, Set


class CencosudScraper:
    def __init__(self):
        self.name = 'Jumbo (Cencosud)'
        self.base_url = 'https://www.jumbo.com.ar/descuentos-del-dia'
        self.dias = {
            'Lunes': '1', 'Martes': '2', 'Miercoles': '3',
            'Jueves': '4', 'Viernes': '5', 'Sabado': '6', 'Domingo': '0',
        }

    async def scrape(self) -> List[Dict]:
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
        except ImportError:
            print("   ⚠️ crawl4ai no instalado — instalá con: pip install crawl4ai && crawl4ai-setup")
            return []

        print(f"\n🔍 Scraping {self.name}...")
        print(f"   🌐 URL Base: {self.base_url}")

        all_promotions: List[Dict] = []
        seen_promos: Set[str] = set()
        SESSION = 'jumbo_session'

        browser_cfg = BrowserConfig(headless=True, verbose=False)

        # Scroll hasta el fondo + expandir "Ver más" antes de capturar
        _JS_SCROLL_EXPAND = """
            (async () => {
                let prev = 0;
                for (let i = 0; i < 12; i++) {
                    window.scrollTo(0, document.body.scrollHeight);
                    await new Promise(r => setTimeout(r, 350));
                    if (document.body.scrollHeight === prev) break;
                    prev = document.body.scrollHeight;
                }
                window.scrollTo(0, 0);
                document.querySelectorAll('button,span,a').forEach(el => {
                    if (/ver\\s*m[aá]s/i.test(el.textContent) && el.offsetParent !== null) {
                        try { el.click(); } catch(e) {}
                    }
                });
            })();
        """

        try:
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                first_day = True
                for dia_nombre, dia_valor in self.dias.items():
                    url = f"{self.base_url}?type=por-dia&day={dia_valor}"
                    print(f"\n      📆 {dia_nombre}  →  {url}")

                    run_cfg = CrawlerRunConfig(
                        session_id=SESSION,
                        wait_for="js:() => /\\d+\\s*%|cuotas?\\s+sin\\s+inter/i.test(document.body.innerText)",
                        js_code=_JS_SCROLL_EXPAND,
                        delay_before_return_html=1.5,
                        page_timeout=60000,
                        cache_mode=CacheMode.BYPASS,
                    )
                    result = await crawler.arun(url, config=run_cfg)

                    if not result.success:
                        print(f"         ⚠️ Error: {result.error_message}")
                        continue

                    if first_day and os.environ.get('DEBUG_SCRAPER'):
                        with open('debug_jumbo.html', 'w', encoding='utf-8') as f:
                            f.write(result.html)
                        print(f"         📄 HTML guardado: debug_jumbo.html")
                        first_day = False

                    promos = self._extract_promotions(result.html, dia_nombre, url)
                    new_count = 0
                    for promo in promos:
                        key = f"{promo.get('bank','')}-{promo.get('discount','')}-{promo.get('categories','')}"
                        if key not in seen_promos:
                            seen_promos.add(key)
                            all_promotions.append(promo)
                            new_count += 1
                    print(f"         ✅ {new_count} nuevas")

        except Exception as e:
            print(f"\n   ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print(f"\n✅ {self.name}: {len(all_promotions)} promociones únicas")
        return all_promotions

    # ──────────────────────────────────────────────────────────────────────────
    # Métodos de extracción/parsing — sin cambios respecto a versión anterior
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_promotions(self, html: str, dia_nombre: str, url: str) -> List[Dict]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        all_cards = []

        for div in soup.find_all('div'):
            imgs = div.find_all('img')
            if not imgs:
                continue
            # Si tiene 3+ imágenes en su subárbol, es un contenedor de múltiples tarjetas
            if len(imgs) > 2:
                continue
            text = div.get_text(' ', strip=True)
            has_discount = bool(re.search(
                r'\d+\s*%|\d+\s*cuotas?\s*sin\s*inter[eé]s|\d+\s*y\s*\d+\s*cuotas?|\d+\s*CSI',
                text, re.I))
            if not has_discount or not (30 < len(text) < 3500):
                continue
            child_cards = sum(
                1 for c in div.find_all('div', recursive=False)
                if c.find('img') and re.search(r'\d+\s*%|\d+\s*cuotas', c.get_text(' ', strip=True), re.I)
            )
            if child_cards > 1:
                continue
            all_cards.append(div)

        for selector in ['[class*="promo"]','[class*="card"]','[class*="oferta"]',
                          '[class*="descuento"]','[class*="bank"]','[class*="promotion"]']:
            for element in soup.select(selector):
                if not element.find('img'):
                    continue
                text = element.get_text(' ', strip=True)
                if re.search(r'\d+\s*%|\d+\s*cuotas', text, re.I) and 30 < len(text) < 8000:
                    if element not in all_cards:
                        all_cards.append(element)

        print(f"         🔍 Cards candidatas: {len(all_cards)}")

        seen_keys: Set[str] = set()
        unique: List = []
        for card in all_cards:
            text = card.get_text(' ', strip=True)
            dm = re.search(r'(\d+\s*%\s*(?:Dto\.?)?|\d+\s*(?:y\s*\d+\s*)?[Cc]uotas?\s*[Ss]in\s*[Ii]nter[eé]s)', text)
            if dm:
                pos = dm.end()
                key = f"{dm.group(1)}_{text[pos:pos+80]}"
            else:
                key = text[:120]
            key = re.sub(r'\s+', ' ', key).strip().lower()
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(card)

        print(f"         🔍 Cards únicas: {len(unique)}")

        promotions = []
        for card in unique:
            try:
                promo = self._parse_promo(card, dia_nombre, url)
                if promo and promo.get('discount'):
                    promotions.append(promo)
            except Exception as e:
                print(f"         ⚠️ Error parseando card: {e}")
        print(f"         🔍 Promociones extraídas: {len(promotions)}")
        return promotions

    def _parse_promo(self, card, dia_nombre: str, url: str) -> Dict:
        text = card.get_text(' ', strip=True)
        promo = {'url': url, 'supermarket': 'Jumbo', 'valid_days': dia_nombre, 'raw_text': text[:3000]}

        img = card.find('img')
        img_src = img_alt = ''
        if img:
            img_src = img.get('src', '') or img.get('data-src', '') or ''
            img_alt = img.get('alt', '') or ''
            promo['image_url'] = img_src

        promo['bank'] = self._identify_bank_from_image(img_src, img_alt) or self._identify_bank_from_text(text)

        dm = re.search(r'(\d+)\s*%\s*(?:Dto\.?|[Dd]escuento)?', text)
        if dm:
            promo['discount'] = f"{dm.group(1)}%"

        for pattern in [
            r'(\d+)\s*,?\s*(\d+)?\s*y?\s*(\d+)?\s*[Cc]uotas?\s*[Ss]in\s*[Ii]nter[eé]s',
            r'(\d+)\s*[Cc]uotas?\s*[Ss]in\s*[Ii]nter[eé]s',
            r'(\d+)\s*[Cc]SI',
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                groups = [g for g in m.groups() if g]
                promo['cuotas'] = (
                    f"{', '.join(groups[:-1])} y {groups[-1]} cuotas sin interés"
                    if len(groups) > 1 else f"{groups[0]} cuotas sin interés"
                )
                if not promo.get('discount'):
                    promo['discount'] = promo['cuotas']
                break

        for pattern in [
            r'(?:entre\s+(?:el\s+)?|del\s+|desde\s+(?:el\s+)?)(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*(?:y\s+(?:el\s+)?|al\s+|hasta\s+(?:el\s+)?)(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
            r'(?:del|desde)\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+(?:al|hasta)\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                g = m.groups()
                if len(g) == 6:
                    if g[1].isdigit():
                        promo['valid_from'] = f"{g[0]}/{g[1]}/{g[2]}"
                        promo['valid_until'] = f"{g[3]}/{g[4]}/{g[5]}"
                    else:
                        promo['valid_from'] = f"{g[0]} de {g[1]} de {g[2]}"
                        promo['valid_until'] = f"{g[3]} de {g[4]} de {g[5]}"
                break

        for pattern in [
            r'(?:TOPE|REEMBOLSO\s+M[AÁ]XIMO|M[AÁ]XIMO|Tope\s+(?:m[aá]ximo\s+)?(?:de\s+)?(?:reintegro)?)[:\s]*\$?\s*([\d.,]+)',
            r'\$\s*([\d.,]+)\s*(?:de\s+)?(?:tope|m[aá]ximo)',
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                amt = m.group(1).replace('.', '').replace(',', '.')
                try:
                    promo['tope'] = f"${float(amt):,.0f}".replace(',', '.')
                except Exception:
                    promo['tope'] = f"${m.group(1)}"
                break

        tarjetas = []
        for kw, name in [('VISA','Visa'),('MASTERCARD','Mastercard'),('CABAL','Cabal'),
                          ('AMERICAN EXPRESS|AMEX','American Express'),('NARANJA','Naranja')]:
            if re.search(kw, text, re.I): tarjetas.append(name)
        if tarjetas: promo['card_types'] = ', '.join(tarjetas)

        pt = []
        if re.search(r'TARJETAS?\s+DE\s+CR[EÉ]DITO|CR[EÉ]DITO', text, re.I): pt.append('Crédito')
        if re.search(r'TARJETAS?\s+DE\s+D[EÉ]BITO|D[EÉ]BITO', text, re.I):  pt.append('Débito')
        if pt: promo['payment_type'] = ', '.join(pt)

        for pattern in [
            r'(?:cuotas?\s+sin\s+inter[eé]s\s+)?en\s+([A-Za-záéíóúñÁÉÍÓÚÑ\s,]+?)(?:\s+Para\s+compras|\s+Promoci[oó]n|\s+V[aá]lida|\s+Abonando|\s+PROMOCIONES|\.|$)',
            r'Dto\.?\s+(?:en\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ\s,]+?)(?:\s+Para|\s+Promoci[oó]n|\.|$)',
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                cat = re.sub(r'\s+', ' ', m.group(1).strip())
                invalid = ['Para','Con','El','La','Los','Las','Desde','Del','Válido','Exclusivo']
                if 2 < len(cat) < 100 and not any(cat.startswith(w) for w in invalid):
                    promo['categories'] = cat
                    break

        excl = []
        nv = re.search(r'NO\s+V[AÁ]LIDO\s+(?:EL\s+)?(\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', text, re.I)
        if nv: excl.append(f"No válido el {nv.group(1)}")
        for m in re.findall(r'[Nn]o\s+aplica\s+(?:para\s+)?([^.]+?)(?:\.|V[aá]lido|$)', text):
            if len(m.strip()) > 5: excl.append(f"No aplica {m.strip()[:200]}")
        if excl: promo['exclusions'] = ' | '.join(excl)[:500]

        if re.search(r'no\s+(?:es\s+)?acumulable|no\s+acumula', text, re.I): promo['acumulable'] = 'No'
        elif re.search(r'\bacumulable\b', text, re.I): promo['acumulable'] = 'Sí'

        if re.search(r'EXCLUSIVO\s+ONLINE|COMPRAS?\s+ONLINE|JUMBO\.COM', text, re.I): promo['validez'] = 'Online'
        elif re.search(r'V[AÁ]LIDO\s+PRESENCIAL|EN\s+(?:LOS\s+)?(?:LOCALES|COMERCIOS)', text, re.I): promo['validez'] = 'Presencial'

        for attr, pat in [('tna', r'(?:TNA|TASA\s+NOMINAL\s+ANUAL)[:\s]*(\d+[,.]?\d*)\s*%'),
                           ('tea', r'(?:TEA|TASA\s+EFECTIVA\s+ANUAL)[:\s]*(\d+[,.]?\d*)\s*%'),
                           ('cft', r'(?:CFTEA?|COSTO\s+FINANCIERO\s+TOTAL)[^:]*[:\s]*(\d+[,.]?\d*)\s*%')]:
            m = re.search(pat, text, re.I)
            if m: promo[attr] = f"{m.group(1)}%"

        if promo.get('bank') == 'MODO':
            pm = re.search(r'[Pp]articipan\s+(.+?)(?:\.\s*[A-Z]|$)', text)
            if pm:
                bl = re.findall(r'Banco\s+[\w\s]+|Billetera\s+\w+|\bICBC\b|\bBBVA\b|\bHSBC\b', pm.group(1), re.I)
                if bl:
                    promo['bancos_participantes'] = ', '.join(
                        b.strip().rstrip(',y').strip() for b in bl if len(b.strip()) > 3
                    )[:15 * 20]

        title_parts = []
        if promo.get('bank'):       title_parts.append(promo['bank'])
        if promo.get('discount'):   title_parts.append(promo['discount'])
        if promo.get('categories'): title_parts.append(f"en {promo['categories']}")
        if promo.get('validez') == 'Online': title_parts.append('(Online)')
        title_parts.append(f"- {dia_nombre}")
        promo['title'] = ' '.join(title_parts) if title_parts else text[:80]

        return promo

    def _identify_bank_from_image(self, img_src: str, img_alt: str) -> str:
        if not img_src and not img_alt:
            return ''
        combined = f"{img_src} {img_alt}".lower()
        for pattern, name in [
            (r'hipotecario', 'Banco Hipotecario'), (r'supervielle', 'Supervielle'),
            (r'galicia', 'Banco Galicia'),          (r'macro', 'Banco Macro'),
            (r'nacion|bna[^c]|banco.?nacion', 'Banco Nación'), (r'ciudad', 'Banco Ciudad'),
            (r'provincia|bapro', 'Banco Provincia'),(r'santander', 'Banco Santander'),
            (r'patagonia', 'Banco Patagonia'),      (r'comafi', 'Banco Comafi'),
            (r'c[oó]rdoba|bancor', 'Bancor'),       (r'columbia', 'Banco Columbia'),
            (r'hsbc', 'HSBC'),                      (r'bbva|franc[eé]s', 'BBVA'),
            (r'icbc', 'ICBC'),                      (r'credicoop', 'Banco Credicoop'),
            (r'modo', 'MODO'),                      (r'mercado[-_]?pago|mp[-_]logo', 'Mercado Pago'),
            (r'prex', 'Prex'),                      (r'personal[-_]?pay', 'Personal Pay'),
            (r'cuenta[-_]?dni', 'Cuenta DNI'),      (r'ual[aá]', 'Ualá'),
            (r'cencopay|cencosud|cencop', 'CencoPay'),
            (r'naranja', 'Naranja X'),              (r'clarin|365', 'Clarín 365'),
            (r'tarjeta.?sol|sol.?tarjeta', 'Tarjeta Sol'), (r'amex|american', 'American Express'),
            (r'visa[-_]?master|master[-_]?visa', 'Visa/Mastercard'),
            (r'visa', 'Visa'),                      (r'mastercard|master', 'Mastercard'),
        ]:
            if re.search(pattern, combined):
                return name
        return ''

    def _identify_bank_from_text(self, text: str) -> str:
        text_upper = text.upper()

        if 'TRAVÉS DE MODO' in text_upper or 'CON MODO' in text_upper:
            m = re.search(
                r'(?:CLIENTES?\s+(?:DE\s+)?|TARJETAS?\s+(?:DE\s+)?|EMITIDAS?\s+POR\s+)'
                r'(BANCO\s+\w+|SUPERVIELLE|HIPOTECARIO|GALICIA|MACRO|SANTANDER)', text_upper)
            if m:
                return self._normalize_bank_name(m.group(1))
            if re.search(r'PAGANDO\s+CON\s+MODO', text_upper) and re.search(r'PARTICIPAN\s+BANCO', text_upper):
                return 'MODO'

        banco_patterns = [
            (r'BANCO\s+HIPOTECARIO', 'Banco Hipotecario'), (r'SUPERVIELLE', 'Supervielle'),
            (r'BANCO\s+(?:DE\s+)?GALICIA', 'Banco Galicia'), (r'BANCO\s+MACRO', 'Banco Macro'),
            (r'BANCO\s+(?:DE\s+LA\s+)?NACI[OÓ]N', 'Banco Nación'), (r'BANCO\s+CIUDAD', 'Banco Ciudad'),
            (r'BANCO\s+(?:DE\s+LA\s+)?PROVINCIA', 'Banco Provincia'), (r'BANCO\s+SANTANDER', 'Banco Santander'),
            (r'BANCO\s+PATAGONIA', 'Banco Patagonia'), (r'BANCO\s+COMAFI', 'Banco Comafi'),
            (r'BANCOR|BANCO\s+(?:DE\s+)?C[OÓ]RDOBA', 'Banco Córdoba'),
            (r'\bHSBC\b', 'HSBC'), (r'\bBBVA\b', 'BBVA'), (r'\bICBC\b', 'ICBC'),
        ]

        mentions = {name: len(re.findall(p, text_upper)) for p, name in banco_patterns
                    if re.search(p, text_upper)}
        if len(mentions) == 1:
            return list(mentions.keys())[0]
        if len(mentions) > 1:
            for p, name in banco_patterns:
                if re.search(rf'(?:CLIENTES?\s+(?:DE\s+)?|TARJETAS?\s+(?:DE\s+)?){p}', text_upper):
                    return name

        for pattern, name in [
            (r'\bMODO\b', 'MODO'),             (r'MERCADO\s*PAGO', 'Mercado Pago'),
            (r'\bPREX\b', 'Prex'),             (r'PERSONAL\s+PAY', 'Personal Pay'),
            (r'CUENTA\s+DNI', 'Cuenta DNI'),   (r'\bUAL[AÁ]\b', 'Ualá'),
            (r'\bCENCOPAY\b', 'CencoPay'),     (r'NARANJA\s*X?|TARJETA\s+NARANJA', 'Naranja X'),
            (r'CLAR[IÍ]N\s*365', 'Clarín 365'),(r'TARJETA\s+SOL', 'Tarjeta Sol'),
        ]:
            if re.search(pattern, text_upper):
                return name
        return ''

    def _normalize_bank_name(self, banco_text: str) -> str:
        banco_upper = banco_text.upper().strip()
        return {
            'GALICIA': 'Banco Galicia',          'BANCO GALICIA': 'Banco Galicia',
            'BANCO DE GALICIA': 'Banco Galicia', 'MACRO': 'Banco Macro',
            'BANCO MACRO': 'Banco Macro',        'NACION': 'Banco Nación',
            'BANCO NACION': 'Banco Nación',      'BANCO DE LA NACION': 'Banco Nación',
            'CIUDAD': 'Banco Ciudad',            'BANCO CIUDAD': 'Banco Ciudad',
            'PROVINCIA': 'Banco Provincia',      'BANCO PROVINCIA': 'Banco Provincia',
            'BANCO DE LA PROVINCIA': 'Banco Provincia', 'SANTANDER': 'Banco Santander',
            'BANCO SANTANDER': 'Banco Santander','PATAGONIA': 'Banco Patagonia',
            'BANCO PATAGONIA': 'Banco Patagonia','SUPERVIELLE': 'Supervielle',
            'BANCO SUPERVIELLE': 'Supervielle',  'COMAFI': 'Banco Comafi',
            'BANCO COMAFI': 'Banco Comafi',      'HIPOTECARIO': 'Banco Hipotecario',
            'BANCO HIPOTECARIO': 'Banco Hipotecario', 'HSBC': 'HSBC',
            'BBVA': 'BBVA',                      'ICBC': 'ICBC',
            'BANCOR': 'Banco Córdoba',           'BANCO CORDOBA': 'Banco Córdoba',
        }.get(banco_upper, banco_text.title())
