"""
Scraper de Carrefour usando Scrapling - Adaptive Web Scraping
Usa StealthyFetcher para bypass de anti-bot y adaptive scraping para
resistir cambios en la estructura del sitio.

Strategy:
1. Try extracting structured promo data from VTEX __RUNTIME__ JSON first
2. Fall back to targeted CSS selectors with parent-child dedup
3. Last resort: full-text regex extraction (with <template> tags stripped)
"""
import json
import re
import os
import unicodedata
from typing import List, Dict, Optional


class CarrefourScraplingError(Exception):
    """Error específico del scraper de Carrefour con Scrapling"""
    pass


class CarrefourScraplingScraper:
    def __init__(self, use_adaptive: bool = False, headless: bool = True):
        """
        Args:
            use_adaptive: Adaptive mode is OFF by default for Carrefour because
                         the VTEX page has too many similar generic elements.
            headless: Si True, ejecuta el browser sin interfaz gráfica
        """
        self.name = 'Carrefour'
        self.url = 'https://www.carrefour.com.ar/descuentos-bancarios'
        self.use_adaptive = use_adaptive
        self.headless = headless
        
        self._banks = {
            'galicia': 'Banco Galicia',
            'santander': 'Santander',
            'bbva': 'BBVA',
            'macro': 'Macro',
            'icbc': 'ICBC',
            'hsbc': 'HSBC',
            'ciudad': 'Banco Ciudad',
            'nacion': 'Banco Nación',
            'provincia': 'Banco Provincia',
            'patagonia': 'Banco Patagonia',
            'credicoop': 'Credicoop',
            'supervielle': 'Supervielle',
            'frances': 'Banco Francés',
            'itau': 'Itaú',
            'comafi': 'Banco Comafi',
            'carrefour banco': 'Carrefour Banco',
        }

        self._wallets = {
            'cuenta dni': 'Cuenta DNI',
            'mercado pago': 'Mercado Pago',
            'ualá': 'Ualá',
            'uala': 'Ualá',
            'naranja x': 'Naranja X',
            'modo': 'MODO',
            'personal pay': 'Personal Pay',
            'club la nacion': 'Club La Nación',
            'mi carrefour': 'Mi Carrefour',
        }

    # Carrefour only renders promos for the selected day.  We iterate
    # through each day filter to capture ALL promotions for the month.
    _DAY_URLS = [
        ('Lunes', 'https://www.carrefour.com.ar/descuentos-bancarios?filtro=dia&dia=Lunes'),
        ('Martes', 'https://www.carrefour.com.ar/descuentos-bancarios?filtro=dia&dia=Martes'),
        ('Miércoles', 'https://www.carrefour.com.ar/descuentos-bancarios?filtro=dia&dia=Mi%C3%A9rcoles'),
        ('Jueves', 'https://www.carrefour.com.ar/descuentos-bancarios?filtro=dia&dia=Jueves'),
        ('Viernes', 'https://www.carrefour.com.ar/descuentos-bancarios?filtro=dia&dia=Viernes'),
        ('Sábado', 'https://www.carrefour.com.ar/descuentos-bancarios?filtro=dia&dia=S%C3%A1bado'),
        ('Domingo', 'https://www.carrefour.com.ar/descuentos-bancarios?filtro=dia&dia=Domingo'),
    ]

    def scrape(self) -> List[Dict]:
        """
        Scrape ALL Carrefour promos by iterating each day filter.
        The Carrefour page only renders the current day's promos by default.
        """
        try:
            from scrapling.fetchers import StealthyFetcher
        except ImportError:
            raise CarrefourScraplingError(
                "Scrapling no está instalado. Ejecuta: pip install 'scrapling[fetchers]' && scrapling install"
            )

        all_promotions: List[Dict] = []

        try:
            print(f"🔍 Scraping {self.name} con Scrapling (all days)...")

            for day_name, day_url in self._DAY_URLS:
                try:
                    print(f"   📅 {day_name}: {day_url}")
                    page = StealthyFetcher.fetch(
                        day_url,
                        headless=self.headless,
                        network_idle=True,
                        timeout=30000,
                    )

                    if os.environ.get('DEBUG_SCRAPER'):
                        debug_path = f'debug_carrefour_{day_name.lower()}.html'
                        with open(debug_path, 'w', encoding='utf-8') as f:
                            f.write(str(page.html_content))

                    day_promos = self._extract_promotions(page)
                    print(f"      ✅ {len(day_promos)} promos para {day_name}")
                    all_promotions.extend(day_promos)

                except Exception as e:
                    print(f"      ⚠️ Error en {day_name}: {e}")

            # Global dedup across all days
            all_promotions = self._deduplicate(all_promotions)
            print(f"✅ {self.name}: {len(all_promotions)} promociones únicas (all days)")
            return all_promotions

        except Exception as e:
            print(f"❌ Error en {self.name} (Scrapling): {e}")
            import traceback
            traceback.print_exc()
            return []

    async def scrape_async(self) -> List[Dict]:
        """
        Scrape asíncrono de promociones de Carrefour usando Scrapling.
        Útil para integración con el sistema existente que usa async.
        Corre el fetch sync en un thread para evitar conflictos con el event loop.
        """
        import asyncio
        print(f"🔍 Scraping {self.name} con Scrapling (async)...")
        return await asyncio.to_thread(self.scrape)

    # ------------------------------------------------------------------
    # Extraction pipeline
    # ------------------------------------------------------------------

    def _extract_promotions(self, page) -> List[Dict]:
        """
        Three-stage extraction pipeline:
        1. VTEX __RUNTIME__ JSON  (structured, most reliable)
        2. Targeted CSS selectors (with parent-child dedup)
        3. Full-text regex        (last resort)
        """
        # --- Stage 1: VTEX structured JSON ---
        promotions = self._extract_from_vtex_json(page)
        if promotions:
            print(f"   📊 {len(promotions)} promos extraídas desde __RUNTIME__ JSON")
            return self._deduplicate(promotions)

        # --- Stage 2: CSS selectors ---
        promotions = self._extract_from_css(page)
        if promotions:
            print(f"   📊 {len(promotions)} promos extraídas desde CSS selectors")
            return self._deduplicate(promotions)

        # --- Stage 3: full-text fallback ---
        print(f"   🔄 Intentando extracción por texto completo...")
        promotions = self._extract_from_full_text(page)
        print(f"   📊 {len(promotions)} promos extraídas desde texto completo")
        return self._deduplicate(promotions)

    def _deduplicate(self, promotions: List[Dict]) -> List[Dict]:
        """
        Dedup using (entity, discount, valid_days, has_online) as composite
        key so that distinct promos for the same bank (e.g. in-store vs
        online) are preserved.
        """
        seen: dict = {}
        for promo in promotions:
            entity = (promo.get('bank') or promo.get('wallet') or '').strip()
            if not entity and promo.get('title', '').lower().startswith('promoción carrefour'):
                continue
            stores = (promo.get('store_types') or '').lower()
            has_online = 'carrefour.com' in stores or 'online' in stores
            key = (
                entity.lower(),
                promo.get('discount', ''),
                (promo.get('valid_days') or '').lower()[:40],
                has_online,
            )
            existing = seen.get(key)
            if existing is None or len(promo.get('terms_raw') or '') > len(existing.get('terms_raw') or ''):
                seen[key] = promo
        return list(seen.values())

    # ------------------------------------------------------------------
    # Stage 1 – VTEX __RUNTIME__ JSON
    # ------------------------------------------------------------------

    def _extract_from_vtex_json(self, page) -> List[Dict]:
        """
        VTEX/Next.js pages embed all data in <template data-varname="__RUNTIME__">
        or <script id="__NEXT_DATA__"> tags. Extract promo data directly from
        the structured JSON instead of parsing rendered DOM.
        """
        promotions = []
        html = str(page.html_content)

        json_blobs = []

        # __NEXT_DATA__ (Next.js standard)
        next_matches = re.finditer(
            r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        )
        for m in next_matches:
            try:
                json_blobs.append(json.loads(m.group(1)))
            except (json.JSONDecodeError, ValueError):
                pass

        # VTEX __RUNTIME__ inside <template> tags
        runtime_matches = re.finditer(
            r'<template\s+[^>]*data-varname="__RUNTIME__"[^>]*>\s*<script[^>]*>(.*?)</script>\s*</template>',
            html, re.DOTALL | re.IGNORECASE,
        )
        for m in runtime_matches:
            try:
                json_blobs.append(json.loads(m.group(1)))
            except (json.JSONDecodeError, ValueError):
                pass

        if not json_blobs:
            print(f"   ℹ️ No se encontró __NEXT_DATA__ ni __RUNTIME__ JSON")
            return []

        print(f"   🔍 Encontrados {len(json_blobs)} blobs JSON embebidos")

        promo_texts = set()
        self._walk_json_for_promos(json_blobs, promo_texts)

        print(f"   🔍 {len(promo_texts)} fragmentos de promo en JSON")

        for text in promo_texts:
            promo = self._promo_from_text(text)
            if promo:
                promotions.append(promo)

        return promotions

    def _walk_json_for_promos(self, obj, results: set, depth: int = 0):
        """Recursively walk JSON looking for string values that look like promos."""
        if depth > 20:
            return
        if isinstance(obj, str):
            has_offer = bool(re.search(r'\d+\s*%|cuotas?\s*sin\s*inter', obj, re.IGNORECASE))
            if len(obj) > 40 and has_offer and self._is_promo_text(obj):
                results.add(obj[:3000])
        elif isinstance(obj, dict):
            for v in obj.values():
                self._walk_json_for_promos(v, results, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                self._walk_json_for_promos(item, results, depth + 1)

    def _is_promo_text(self, text: str) -> bool:
        text_lower = text.lower()
        has_bank = any(b in text_lower for b in self._banks)
        has_wallet = any(w in text_lower for w in self._wallets)
        has_keyword = any(k in text_lower for k in ['descuento', 'promoción', 'oferta'])
        return has_bank or has_wallet or has_keyword

    # ------------------------------------------------------------------
    # Stage 2 – CSS selectors with parent-child dedup
    # ------------------------------------------------------------------

    def _extract_from_css(self, page) -> List[Dict]:
        """
        Use specific CSS selectors (avoiding overly broad ones like
        div[class*="card"] or plain 'article' that match hundreds of
        VTEX framework elements).
        """
        promo_selectors = [
            'div[class*="promo"]',
            'div[class*="descuento"]',
            'div[class*="BanksPromotions"]',
            'div[class*="dynamicTabs"]',
            'section[class*="promo"]',
            'section[class*="descuento"]',
        ]

        promo_elements = []
        seen_texts = set()

        for selector in promo_selectors:
            try:
                elements = page.css(selector)
                if not elements:
                    continue

                for el in elements:
                    text = el.text or ''
                    if not self._is_promo_element(text):
                        continue

                    text_hash = hash(text.strip()[:500])
                    if text_hash in seen_texts:
                        continue
                    seen_texts.add(text_hash)

                    is_child_of_existing = False
                    is_parent_of_existing = False
                    kept = []
                    for existing_el, existing_text in promo_elements:
                        et = existing_text.strip()[:500]
                        ct = text.strip()[:500]
                        if ct in et:
                            is_child_of_existing = True
                            break
                        if et in ct:
                            is_parent_of_existing = True
                            continue
                        kept.append((existing_el, existing_text))

                    if is_child_of_existing:
                        continue

                    if is_parent_of_existing:
                        promo_elements = kept

                    promo_elements.append((el, text))
            except Exception:
                continue

        print(f"   📊 Encontrados {len(promo_elements)} elementos de promoción (post-dedup)")

        promotions = []
        for el, _ in promo_elements:
            try:
                promo = self._parse_promo_element(el)
                if promo:
                    promotions.append(promo)
            except Exception as e:
                print(f"   ⚠️ Error procesando elemento: {e}")

        return promotions

    def _is_promo_element(self, text: str) -> bool:
        """Determina si un texto corresponde a una promoción"""
        if not text or len(text) < 50:
            return False
        
        text_lower = text.lower()
        
        has_discount = bool(re.search(r'\d+\s*%', text))
        has_bank_info = any(bank in text_lower for bank in self._banks.keys())
        has_wallet_info = any(wallet in text_lower for wallet in self._wallets.keys())
        has_promo_keywords = any(kw in text_lower for kw in ['descuento', 'promoción', 'oferta', 'ahorro'])
        
        return has_discount and (has_bank_info or has_wallet_info or has_promo_keywords)

    def _parse_promo_element(self, element) -> Optional[Dict]:
        """Parsea un elemento de promoción y extrae datos estructurados"""
        try:
            full_text = element.text or ''
            if not full_text or len(full_text) < 30:
                return None
            
            title = ''
            title_el = element.css('h1, h2, h3, h4, h5, h6, [class*="title"], [class*="titulo"]')
            if title_el:
                title = title_el[0].text or ''
            
            if not title:
                title_match = re.search(r'(\d+%\s*(?:de\s*)?descuento[^.\n]{0,100})', full_text, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
            
            if not title:
                title = f"Promoción Carrefour"
            
            discount = self._extract_discount(full_text)
            bank = self._extract_bank(full_text)
            wallet = self._extract_wallet(full_text)
            
            terms = self._extract_terms(full_text)
            
            store_types = self._extract_store_types(full_text)
            valid_days = self._extract_valid_days(full_text)
            dates = self._extract_dates(full_text)
            
            payment_method = self._extract_payment_method(full_text)
            exclusions = self._extract_exclusions(full_text)
            requirements = self._extract_requirements(full_text)
            
            img_el = element.css('img')
            image_url = ''
            if img_el:
                image_url = img_el[0].attrib.get('src', '') or img_el[0].attrib.get('data-src', '')
            
            return {
                'title': self._clean_text(title),
                'discount': discount,
                'bank': bank,
                'wallet': wallet,
                'card_type': None,
                'payment_method': payment_method,
                'store_types': ', '.join(store_types) if store_types else None,
                'valid_days': valid_days,
                'url': self.url,
                'image_url': image_url,
                'terms_raw': self._clean_text(terms),
                'exclusions': '; '.join(exclusions[:10]) if exclusions else None,
                'requirements': '; '.join(requirements[:5]) if requirements else None,
                'valid_from': dates.get('valid_from'),
                'valid_until': dates.get('valid_until'),
            }
            
        except Exception as e:
            print(f"   ⚠️ Error parseando elemento: {e}")
            return None

    # ------------------------------------------------------------------
    # Stage 3 – legal-block extraction (splits on PROMOCIÓN VÁLIDA)
    # ------------------------------------------------------------------

    def _strip_html_to_text(self, page) -> str:
        """Strip scripts/templates/styles from page HTML, return clean text."""
        html_content = str(page.html_content)
        html_content = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<template[^>]*>[\s\S]*?</template>', ' ', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<noscript[^>]*>[\s\S]*?</noscript>', ' ', html_content, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html_content)
        return re.sub(r'\s+', ' ', text).strip()

    def _extract_from_full_text(self, page) -> List[Dict]:
        """
        Split the page text at PROMOCIÓN VÁLIDA boundaries.
        Each legal block corresponds to exactly one promotion, avoiding
        the cross-contamination caused by overlapping context windows.
        """
        promotions = []

        try:
            text = self._strip_html_to_text(page)

            # Carrefour legal blocks start with various patterns:
            # "DESCUENTO EXCLUSIVO...", "BENEFICIO VÁLIDO...",
            # "PROMOCIÓN VÁLIDA...", "*FINANCIACIÓN EXCLUSIVA..."
            legal_pattern = re.compile(
                r'\*?\s*(?:'
                r'DESCUENTO\s+EXCLUSIVO|'
                r'BENEFICIO\s+V[AÁ]LID|'
                r'PROMOCI[OÓ]N\s+V[AÁ]LIDA|'
                r'FINANCIACI[OÓ]N\s+EXCLUSIV'
                r')',
                re.IGNORECASE,
            )
            legal_starts = [m.start() for m in legal_pattern.finditer(text)]

            if not legal_starts:
                print(f"   ⚠️ No legal blocks found, trying discount-pattern fallback")
                return self._extract_from_full_text_legacy(text)

            print(f"   🔍 Found {len(legal_starts)} PROMOCIÓN VÁLIDA blocks")

            prev_legal_end = 0
            for i, start in enumerate(legal_starts):
                # Card text: everything between previous legal block end and this one
                card_start = max(prev_legal_end, start - 600)
                card_text = text[card_start:start].strip()

                raw_end = legal_starts[i + 1] if i + 1 < len(legal_starts) else min(start + 5000, len(text))
                block = text[start:raw_end]

                # Legal text ends at the next card header ("Ver legal" button,
                # "Comprando en:", "Todos los", etc.)
                boundary = re.search(
                    r'(?:Ver\s+legal|Comprando\s+en|Todos\s+los\s+\w)',
                    block[150:],
                )
                if boundary:
                    legal_text = block[:150 + boundary.start()].strip()
                    prev_legal_end = start + 150 + boundary.start()
                else:
                    legal_text = block[:2500].strip()
                    prev_legal_end = start + len(legal_text)

                promo = self._promo_from_legal_block(legal_text, card_text)
                if promo:
                    promotions.append(promo)

        except Exception as e:
            print(f"   ❌ Error en extracción por texto: {e}")

        return promotions

    def _extract_from_full_text_legacy(self, text: str) -> List[Dict]:
        """Fallback when no PROMOCIÓN VÁLIDA blocks exist: small context windows."""
        promotions = []
        patterns = [
            (r'(\d+)\s*%\s*(?:de\s*)?(?:descuento|ahorro)', 'percent'),
            (r'(?:hasta\s+)?(\d+)\s*cuotas?\s*sin\s*inter[eé]s', 'cuotas'),
        ]

        all_matches = []
        for pattern, kind in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                all_matches.append((m.start(), m, kind))
        all_matches.sort(key=lambda x: x[0])

        for _, match, kind in all_matches:
            start = max(0, match.start() - 300)
            end = min(len(text), match.end() + 600)
            context = text[start:end]
            promo = self._promo_from_text(context, kind=kind)
            if promo:
                promotions.append(promo)

        return promotions

    # ------------------------------------------------------------------
    # Promo builders
    # ------------------------------------------------------------------

    def _promo_from_legal_block(self, legal_text: str, card_text: str) -> Optional[Dict]:
        """Build a promo from one PROMOCIÓN VÁLIDA block and its preceding card text."""
        bank = self._extract_bank(legal_text) or self._extract_bank(card_text)
        wallet = self._extract_wallet(legal_text) or self._extract_wallet(card_text)
        if not bank and not wallet:
            return None

        discount = self._extract_discount_from_legal(legal_text)
        if not discount:
            discount = self._extract_discount(legal_text) or self._extract_discount(card_text)
        if not discount:
            return None

        title = self._build_title_from_card(card_text, discount, bank, wallet)

        dates = self._extract_dates(legal_text)
        if not dates.get('valid_from') and not dates.get('valid_until'):
            dates = self._extract_dates(card_text)

        store_types = self._extract_store_types(legal_text) or self._extract_store_types(card_text)
        valid_days = self._extract_valid_days(legal_text) or self._extract_valid_days(card_text)
        payment_method = self._extract_payment_method(legal_text)

        return {
            'title': self._clean_text(title),
            'discount': discount,
            'bank': bank,
            'wallet': wallet,
            'card_type': None,
            'payment_method': payment_method,
            'store_types': ', '.join(store_types) if store_types else None,
            'valid_days': valid_days,
            'url': self.url,
            'image_url': '',
            'terms_raw': self._clean_text(legal_text[:3000]),
            'exclusions': None,
            'requirements': None,
            'valid_from': dates.get('valid_from'),
            'valid_until': dates.get('valid_until'),
        }

    def _promo_from_text(self, context: str, kind: str = 'percent') -> Optional[Dict]:
        """Build a promo dict from a raw text fragment (legacy fallback)."""
        bank = self._extract_bank(context)
        wallet = self._extract_wallet(context)
        if not bank and not wallet:
            return None

        if kind == 'cuotas':
            cuotas_match = re.search(
                r'(?:hasta\s+)?(\d+)\s*cuotas?\s*sin\s*inter[eé]s([^.!?\n]{0,120})',
                context, re.IGNORECASE,
            )
            if not cuotas_match:
                return None
            discount = f"{cuotas_match.group(1)} cuotas sin interés"
            title_tail = cuotas_match.group(2).strip()
            title = f"{discount} {title_tail}".strip() if title_tail else discount
        else:
            discount = self._extract_discount(context)
            if not discount:
                return None
            title_match = re.search(r'(\d+%\s*(?:de\s*)?descuento[^.!?\n]{10,150})', context, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else f"{discount} de descuento"

        entity = bank or wallet
        if entity and entity.lower() not in title.lower():
            title = f"{title} con {entity}"

        store_types = self._extract_store_types(context)
        terms = self._extract_terms(context)
        valid_days = self._extract_valid_days(context)
        dates = self._extract_dates(context)
        payment_method = self._extract_payment_method(context)

        return {
            'title': self._clean_text(title),
            'discount': discount,
            'bank': bank,
            'wallet': wallet,
            'card_type': None,
            'payment_method': payment_method,
            'store_types': ', '.join(store_types) if store_types else None,
            'valid_days': valid_days,
            'url': self.url,
            'image_url': '',
            'terms_raw': self._clean_text(terms),
            'exclusions': None,
            'requirements': None,
            'valid_from': dates.get('valid_from'),
            'valid_until': dates.get('valid_until'),
        }

    def _build_title_from_card(self, card_text: str, discount: str, bank: Optional[str], wallet: Optional[str]) -> str:
        """Extract a human-readable title from the visible card text."""
        entity = bank or wallet or ''

        if 'cuotas' in discount.lower():
            m = re.search(r'(\d+\s*cuotas?\s*sin\s*inter[eé]s[^.!?\n]{0,120})', card_text, re.IGNORECASE)
            title = m.group(1).strip() if m else discount
        else:
            # Prefer descriptive sentence ("30% de descuento en un pago con...")
            # over the badge text ("30% de Ahorro")
            descriptive = re.search(
                r'(\d+%\s*(?:de\s*)?(?:descuento|ahorro)\s+(?:en|con|si|pagando)[^.!?\n]{5,150})',
                card_text, re.IGNORECASE,
            )
            if descriptive:
                title = descriptive.group(1).strip()
            else:
                m = re.search(r'(\d+%\s*(?:de\s*)?(?:descuento|ahorro)[^.!?\n]{5,150})', card_text, re.IGNORECASE)
                title = m.group(1).strip() if m else f"{discount} de descuento"

        if entity and entity.lower() not in title.lower():
            title = f"{title} con {entity}"

        return title

    def _extract_discount_from_legal(self, legal_text: str) -> Optional[str]:
        """
        Extract discount from legal text patterns:
        'BENEFICIO DEL 30%', '10% DE DESCUENTO', '3 CUOTAS SIN INTERÉS',
        '10% DE REINTEGRO', 'DESCUENTO EXCLUSIVO ... 15%'.
        """
        # Cuotas pattern first (higher priority)
        m = re.search(r'(?:hasta\s+)?(\d+)\s*CUOTAS?\s*SIN\s*INTER[EÉ]S', legal_text, re.IGNORECASE)
        if m:
            return f"{m.group(1)} cuotas sin interés"
        m = re.search(r'BENEFICIO\s+DEL\s+(\d+)\s*%', legal_text, re.IGNORECASE)
        if m:
            return f"{m.group(1)}%"
        m = re.search(
            r'(\d+)\s*%\s*(?:DE\s+)?(?:DESCUENTO|AHORRO|REINTEGRO|DEVOLUCI[OÓ]N|BONIFICACI[OÓ]N)',
            legal_text, re.IGNORECASE,
        )
        if m:
            return f"{m.group(1)}%"
        # Generic fallback: any N% in the legal text
        m = re.search(r'(\d+)\s*%', legal_text)
        if m:
            return f"{m.group(1)}%"
        return None

    def _extract_discount(self, text: str) -> str:
        """Extrae porcentaje de descuento o cuotas sin interés"""
        if not text:
            return ""

        cuotas_match = re.search(r'(?:hasta\s+)?(\d+)\s*cuotas?\s*sin\s*inter[eé]s', text, re.IGNORECASE)
        if cuotas_match:
            return f"{cuotas_match.group(1)} cuotas sin interés"

        percent_match = re.search(r'(\d+)\s*%', text)
        if percent_match:
            return f"{percent_match.group(1)}%"

        return ""

    @staticmethod
    def _strip_accents(text: str) -> str:
        """Remove diacritics so 'nación' matches 'nacion'."""
        return ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )

    _bank_abbreviations = {
        'bna': 'Banco Nación',
        'bbva': 'BBVA',
        'icbc': 'ICBC',
        'hsbc': 'HSBC',
    }

    def _extract_bank(self, text: str) -> Optional[str]:
        """Extrae banco del texto (accent-insensitive, handles abbreviations)"""
        if not text:
            return None
        normalized = self._strip_accents(text.lower())
        for key, value in self._banks.items():
            if key in normalized:
                return value
        # Check abbreviations with word boundaries to avoid false positives
        for abbr, value in self._bank_abbreviations.items():
            if re.search(r'\b' + abbr + r'\b', normalized):
                return value
        return None

    def _extract_wallet(self, text: str) -> Optional[str]:
        """Extrae billetera digital del texto (accent-insensitive)"""
        if not text:
            return None
        normalized = self._strip_accents(text.lower())
        for key, value in self._wallets.items():
            if key in normalized:
                return value
        return None

    def _extract_terms(self, text: str) -> str:
        """Extrae términos y condiciones"""
        if not text:
            return ""
        
        terms_match = re.search(r'(PROMOCIÓN[A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{200,3000})', text, re.IGNORECASE)
        if terms_match:
            return terms_match.group(1)
        
        upper_matches = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{100,}', text)
        if upper_matches:
            return ' '.join(upper_matches[:3])
        
        return ""

    def _extract_store_types(self, text: str) -> List[str]:
        """Extrae tipos de tienda, respecting negations like 'NO VÁLIDO PARA'."""
        store_types = []

        # Detect explicit online exclusion
        online_excluded = bool(re.search(
            r'NO\s+V[AÁ]LID[OA]\s+(?:PARA\s+)?(?:COMPRAS\s+(?:EN|POR)\s+)?(?:WWW\.)?CARREFOUR\.COM',
            text, re.IGNORECASE,
        ))

        if re.search(r'carrefour\s*market', text, re.IGNORECASE):
            store_types.append('Carrefour Market')
        if re.search(r'carrefour\s*express', text, re.IGNORECASE):
            store_types.append('Carrefour Express')
        if re.search(r'carrefour\s*maxi', text, re.IGNORECASE):
            store_types.append('Carrefour Maxi')
        if re.search(r'hipermercado', text, re.IGNORECASE):
            store_types.append('Hipermercado Carrefour')
        if not online_excluded and re.search(r'carrefour\.com', text, re.IGNORECASE):
            store_types.append('Carrefour.com.ar')

        return store_types

    def _extract_valid_days(self, text: str) -> Optional[str]:
        """Extrae días válidos de la promoción"""
        days_match = re.search(
            r'(?:todos\s+los|los)\s+(?:d[ií]as?\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)(?:\s+(?:y\s+)?(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo))?(?:\s+de\s+\w+)?',
            text, re.IGNORECASE
        )
        if days_match:
            return self._clean_text(days_match.group(0))
        return None

    def _extract_dates(self, text: str) -> Dict[str, Optional[str]]:
        """Extrae fechas de validez"""
        dates = {'valid_from': None, 'valid_until': None}

        if not text:
            return dates

        month_map = {
            'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
            'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
            'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12',
        }

        # DD/MM/YYYY format (e.g. "HASTA EL 30/04/2026")
        m = re.search(r'hasta\s+(?:el\s+)?(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', text, re.IGNORECASE)
        if m:
            dates['valid_until'] = f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
            return dates

        # "desde DD al DD de MES de YYYY"
        m = re.search(
            r'(?:desde|del)\s+(?:el\s+)?(\d{1,2})\s+(?:al|hasta)\s+(?:el\s+)?(\d{1,2})\s+(?:de\s+)?('
            + '|'.join(month_map) + r')(?:\s+de\s+)?(\d{4})?',
            text, re.IGNORECASE,
        )
        if m:
            month = month_map.get(m.group(3).lower(), '01')
            year = m.group(4) or '2026'
            dates['valid_from'] = f"{year}-{month}-{m.group(1).zfill(2)}"
            dates['valid_until'] = f"{year}-{month}-{m.group(2).zfill(2)}"
            return dates

        # "hasta el DD de MES de YYYY"
        m = re.search(
            r'hasta\s+(?:el\s+)?(\d{1,2})\s+de\s+(' + '|'.join(month_map) + r')(?:\s+de\s+)?(\d{4})?',
            text, re.IGNORECASE,
        )
        if m:
            month = month_map.get(m.group(2).lower(), '01')
            year = m.group(3) or '2026'
            dates['valid_until'] = f"{year}-{month}-{m.group(1).zfill(2)}"
            return dates

        # "de MES de YYYY" (whole month)
        m = re.search(r'de\s+(' + '|'.join(month_map) + r')\s+(?:de\s+)?(\d{4})', text, re.IGNORECASE)
        if m:
            month = month_map.get(m.group(1).lower(), '01')
            year = m.group(2)
            dates['valid_from'] = f"{year}-{month}-01"
            last = 30 if int(month) in (4, 6, 9, 11) else 28 if int(month) == 2 else 31
            dates['valid_until'] = f"{year}-{month}-{last:02d}"

        return dates

    def _extract_payment_method(self, text: str) -> Optional[str]:
        """Extrae método de pago"""
        payment_match = re.search(
            r'(?:con|mediante|usando|través de|a través)\s+([^\n.]{5,80}(?:dni|pago|tarjeta|visa|master|amex|cuenta)[^\n.]{0,30})',
            text, re.IGNORECASE
        )
        if payment_match:
            return self._clean_text(payment_match.group(1))
        return None

    def _extract_exclusions(self, text: str) -> List[str]:
        """Extrae exclusiones de la promoción"""
        if not text:
            return []
        
        exclusions = []
        patterns = [
            r'se\s+excluyen?\s+(?:de\s+la\s+promoción\s+)?([^.]+)',
            r'exclu(?:ye|ído)(?:s)?\s+([^.]+)',
            r'no\s+(?:incluye|aplica|válid[oa])\s+(?:para|en)\s+([^.]+)',
            r'excepto\s+([^.]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                exclusion_text = match.group(1).strip()
                items = re.split(r'[,y]', exclusion_text)
                for item in items:
                    item = item.strip()
                    if item and 3 < len(item) < 100:
                        exclusions.append(item.capitalize())
        
        return list(set(exclusions))

    def _extract_requirements(self, text: str) -> List[str]:
        """Extrae requisitos de la promoción"""
        if not text:
            return []
        
        requirements = []
        patterns = [
            r'(?:solo|únicamente|exclusivamente)\s+(?:para|con)\s+([^.]{5,80})',
            r'(?:válid[oa]|aplicable)\s+(?:solo|únicamente)\s+(?:para|con)\s+([^.]{5,80})',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                req = match.group(1).strip()
                if 5 < len(req) < 100:
                    requirements.append(req.capitalize())
        
        nivel_match = re.search(r'nivel\s+(\d+|[a-z]+)', text.lower())
        if nivel_match:
            requirements.append(f"Nivel {nivel_match.group(1)}")
        
        card_types = ['black', 'platinum', 'signature', 'gold', 'infinite']
        for card_type in card_types:
            if card_type in text.lower():
                requirements.append(f"Tarjeta {card_type.title()}")
        
        return list(set(requirements))

    def _clean_text(self, text: str) -> str:
        """Limpia y normaliza texto"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        return text.strip()
