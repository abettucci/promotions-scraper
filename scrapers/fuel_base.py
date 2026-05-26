"""
Scraper genérico para estaciones de servicio usando Claude Vision.

Las páginas de combustibles tienen layouts muy variados (tabs por día, cards,
URLs numeradas, etc.) — usar Claude Vision permite extraer los datos sin tener
que escribir selectores específicos para cada una.
"""
import asyncio
import os
from typing import List, Dict
from playwright.async_api import async_playwright


# Prompt específico para combustibles
FUEL_SYSTEM_PROMPT = """Eres un experto en extraer información de promociones bancarias de estaciones de servicio (combustible) en Argentina.

Tu tarea es analizar la imagen de una página web de promociones de combustibles y extraer TODAS las promociones bancarias visibles.

Para cada promoción, extrae la siguiente información en formato JSON:
- title: Título o descripción principal de la promoción (ej: "20% de descuento en YPF con Banco Galicia")
- merchant_brands: Lista de marcas de estaciones de servicio donde aplica el descuento (ej: ["YPF"], ["Shell"], ["Axion"], ["Puma"], ["YPF", "Shell"]). Si la promo aplica a "todas las estaciones" o no especifica marca, devolvé []. NUNCA pongas el nombre de un banco acá — solo marcas de combustible (YPF, Shell, Axion, Puma, Total, Refinor, Voy).
- discount: Descuento (ej: "20%", "$50/L", "30% reintegro")
- bank: Nombre del banco (ej: "Banco Galicia", "Santander", "BBVA", "Macro", "Banco Nación", "Banco Patagonia"). null si no hay banco específico.
- wallet: Billetera digital si aplica (ej: "Mercado Pago", "Modo", "Naranja X", "Personal Pay", "YPF App", "Shell Box"). null si no aplica.
- card_type: Tipo de tarjeta (ej: "Crédito", "Débito", "Crédito y Débito"). null si no se especifica.
- payment_method: Método de pago específico si se menciona
- valid_days: Días de validez (ej: "Lunes", "Lunes y Martes", "Todos los días", "Viernes y Sábados")
- valid_from: Fecha de inicio en formato YYYY-MM-DD si está visible
- valid_until: Fecha de fin en formato YYYY-MM-DD si está visible
- terms_raw: Términos y condiciones visibles (texto resumido)
- tope: Tope de reintegro/descuento (ej: "$10000 mensual", "$5000 por transacción", "Sin tope")
- min_purchase: Compra mínima si se menciona
- exclusions: Lista de exclusiones (ej: "No acumulable con otras promos")
- requirements: Lista de requisitos (ej: "Pagando con QR", "App YPF", "Cuenta Sueldo")

IMPORTANTE:
- Extrae TODAS las promociones visibles, incluso si están en tabs o secciones colapsables
- Si una promo aplica a múltiples bancos/billeteras, crear UNA entrada por cada banco/billetera
- merchant_brands DEBE contener solo marcas de gasolineras (YPF/Shell/Axion/Puma/Total/Refinor/Voy), NO bancos
- Los descuentos pueden ser % o $/litro
- Si no se menciona un banco/billetera identificable, NO incluyas la promo (descartá info institucional genérica)
- Presta atención a los días — son críticos
- Si la imagen no muestra promociones bancarias claras, devolvé "promotions": []

Responde ÚNICAMENTE con un JSON válido:
{
    "promotions": [
        {"title": "...", "discount": "...", "bank": "...", ...},
        ...
    ],
    "extraction_notes": "Notas sobre la extracción"
}"""


async def scrape_fuel_station_with_ai(name: str, url: str, debug_name: str = None) -> List[Dict]:
    """
    Scrapea una estación de servicio usando Claude Vision.

    Si la página tiene tabs por día (Lunes/Martes/...), itera por cada tab
    y captura las promociones de cada día por separado.
    """
    try:
        from .ai_extractor import AIExtractor
    except ImportError:
        print(f"   ❌ anthropic no instalado — no se puede usar AI")
        return []

    if not os.getenv("GEMINI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print(f"   ❌ Configurá GEMINI_API_KEY (gratis) o ANTHROPIC_API_KEY")
        return []

    print(f"\n🔍 Scraping {name} con Claude Vision...")
    print(f"   🌐 {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            try:
                response = await page.goto(url, wait_until='networkidle', timeout=60000)
                print(f"   📡 Status: {response.status if response else '?'}")
            except Exception as e:
                print(f"   ⚠️ goto falló (sigo igual): {e}")

            await asyncio.sleep(3)

            extractor = AIExtractor()
            extractor.system_prompt = FUEL_SYSTEM_PROMPT

            # Detectar tabs por día. Si hay → iterar; si no → scrape único
            day_tabs = await _detect_day_tabs(page)

            all_promos: List[Dict] = []

            if day_tabs:
                print(f"   📅 Encontrados {len(day_tabs)} tabs de día: {[d[0] for d in day_tabs]}")
                for idx, (day_label, locator_fn) in enumerate(day_tabs):
                    print(f"\n   ── Tab {idx+1}/{len(day_tabs)}: {day_label} ──")
                    try:
                        # Re-localizar el tab por si el DOM cambió
                        tab_el = await locator_fn()
                        if not tab_el:
                            continue
                        await tab_el.click(timeout=3000)
                        await asyncio.sleep(1.5)

                        await _scroll_full_page(page)
                        await expand_all_details(page)
                        await _scroll_full_page(page)

                        if debug_name:
                            try:
                                await page.screenshot(
                                    path=f'debug_{debug_name}_{day_label}.png',
                                    full_page=True,
                                )
                            except Exception:
                                pass

                        promos = await extractor.extract_from_screenshot(
                            page, f"{name} ({day_label})", url, scroll_and_capture=True
                        )
                        # Anotar el día detectado en cada promo
                        for promo in promos:
                            if not promo.get('valid_days'):
                                promo['valid_days'] = day_label.capitalize()
                        all_promos.extend(promos)
                        print(f"   ✅ {day_label}: {len(promos)} promos")
                    except Exception as e:
                        print(f"   ❌ Error en tab {day_label}: {e}")
            else:
                # Sin tabs por día → scrape único de toda la página
                await _scroll_full_page(page)
                await expand_all_details(page)
                await _scroll_full_page(page)
                if debug_name:
                    try:
                        html = await page.content()
                        with open(f'debug_{debug_name}.html', 'w', encoding='utf-8') as f:
                            f.write(html)
                        await page.screenshot(path=f'debug_{debug_name}.png', full_page=True)
                    except Exception:
                        pass
                all_promos = await extractor.extract_from_screenshot(
                    page, name, url, scroll_and_capture=True
                )

            # Dedup por (bank/wallet, discount, valid_days)
            seen = set()
            unique = []
            for p in all_promos:
                key = (
                    (p.get('bank') or '').lower().strip(),
                    (p.get('wallet') or '').lower().strip(),
                    (p.get('discount') or '').lower().strip(),
                    (p.get('valid_days') or '').lower().strip(),
                )
                if key in seen:
                    continue
                seen.add(key)
                unique.append(p)

            # Normalizar para schema de DB
            normalized = []
            for p in unique:
                # merchant_brands puede venir como lista, string CSV, o vacío
                raw_brands = p.get('merchant_brands') or p.get('merchant_brand') or []
                if isinstance(raw_brands, str):
                    raw_brands = [b.strip() for b in raw_brands.replace(' y ', ',').split(',') if b.strip()]
                brands = [b.strip() for b in raw_brands if b and b.strip()]

                normalized.append({
                    'supermarket': name,
                    'merchant_brands': brands,  # lista de marcas (YPF/Shell/etc.)
                    'title': p.get('title') or '',
                    'discount': p.get('discount') or '',
                    'bank': p.get('bank') or '',
                    'wallet': p.get('wallet') or '',
                    'card_type': p.get('card_type') or '',
                    'payment_method': p.get('payment_method') or '',
                    'store_types': p.get('store_types') or '',
                    'valid_days': p.get('valid_days') or '',
                    'valid_from': p.get('valid_from'),
                    'valid_until': p.get('valid_until'),
                    'tope': p.get('tope') or '',
                    'min_purchase': p.get('min_purchase') or '',
                    'terms_raw': p.get('terms_raw') or '',
                    'exclusions': ', '.join(p.get('exclusions', []) if isinstance(p.get('exclusions'), list) else [p.get('exclusions')] if p.get('exclusions') else []),
                    'requirements': ', '.join(p.get('requirements', []) if isinstance(p.get('requirements'), list) else [p.get('requirements')] if p.get('requirements') else []),
                    'url': url,
                })
            print(f"\n✅ {name}: {len(normalized)} promociones únicas extraídas")
            return normalized

        finally:
            await browser.close()


async def expand_all_details(page) -> int:
    """
    Hace click en TODOS los botones tipo "Ver más", "Ver legal", "Ver detalle",
    "+ Ver más", "Ver términos", etc. para expandir el contenido oculto antes
    de tomar screenshots o leer el HTML.

    Reusable para supermercados y combustible.
    """
    selectors = [
        # Texto exacto (case-insensitive)
        'text=/^\\s*\\+?\\s*ver\\s+m[aá]s\\s*$/i',
        'text=/^\\s*ver\\s+legal\\s*$/i',
        'text=/^\\s*ver\\s+detalle?s?\\s*$/i',
        'text=/^\\s*ver\\s+t[eé]rminos\\s*$/i',
        'text=/^\\s*ver\\s+condiciones\\s*$/i',
        'text=/^\\s*leer\\s+m[aá]s\\s*$/i',
        # Clases comunes
        '[class*="ver-mas"]',
        '[class*="vermas"]',
        '[class*="ver-legal"]',
        '[class*="verLegal"]',
        '[class*="show-more"]',
        '[class*="showmore"]',
        '[class*="expand"]',
        '[class*="toggle"]',
        '[aria-expanded="false"]',
        # Buttons / links que contienen estos textos
        'button:has-text("Ver más")',
        'button:has-text("Ver Más")',
        'button:has-text("VER MÁS")',
        'button:has-text("Ver legal")',
        'button:has-text("Ver Legal")',
        'button:has-text("Ver detalle")',
        'a:has-text("Ver más")',
        'a:has-text("VER MÁS")',
        'a:has-text("+ VER MÁS")',
        'a:has-text("Ver legal")',
        'span:has-text("Ver más")',
        'span:has-text("Ver legal")',
        'div:has-text("+ ver más")',
    ]

    expanded = 0
    seen_handles = set()
    for selector in selectors:
        try:
            elements = page.locator(selector)
            count = await elements.count()
        except Exception:
            continue

        for i in range(min(count, 80)):
            try:
                el = elements.nth(i)
                # Evitar clickear el mismo elemento dos veces
                handle = await el.element_handle(timeout=300)
                if not handle:
                    continue
                if handle in seen_handles:
                    continue
                seen_handles.add(handle)

                if not await el.is_visible(timeout=300):
                    continue

                # Evitar links que naveguen fuera
                href = await el.get_attribute('href')
                if href and href not in ('#', '') and not href.startswith(('javascript:', '#')):
                    # Es un link de verdad (cambia URL) → no clickear
                    continue

                await el.click(timeout=1500)
                expanded += 1
                await asyncio.sleep(0.15)
            except Exception:
                continue

    if expanded:
        # Pequeña espera para que se renderice el contenido expandido
        await asyncio.sleep(1)
        print(f"   📖 Expandidos {expanded} botones 'Ver más/legal/detalle'")
    return expanded


async def _scroll_full_page(page):
    """Scroll completo en pasos para forzar carga lazy."""
    try:
        height = await page.evaluate('document.body.scrollHeight')
        for y in range(0, int(height), 600):
            await page.evaluate(f'window.scrollTo(0, {y})')
            await asyncio.sleep(0.3)
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(1)
        await page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(0.5)
    except Exception as e:
        print(f"   ⚠️ Scroll falló: {e}")


async def _detect_day_tabs(page):
    """
    Detecta tabs de día en la página y devuelve una lista
    [(label, async_fn_que_devuelve_locator), ...] para cada tab visible.

    También incluye tabs como "Todos los días" o "Lunes a viernes" si están
    estructuradas como las demás.
    """
    # Patrones de label que vamos a buscar como tabs (caso sensible al texto exacto del tab)
    label_patterns = [
        ('todos los dias', 'Todos los días'),
        ('lunes a viernes', 'Lunes a viernes'),
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miércoles', 'Miércoles'),
        ('miercoles', 'Miércoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sábado', 'Sábado'),
        ('sabado', 'Sábado'),
        ('domingo', 'Domingo'),
    ]

    found = []
    seen_labels = set()

    for needle, label in label_patterns:
        if label in seen_labels:
            continue

        # Probar varios selectores que sugieren un tab clickeable
        selectors = [
            f'[role="tab"]:has-text("{needle}")',
            f'button:has-text("{needle}")',
            f'a[href^="#tab"]:has-text("{needle}")',
            f'li:has-text("{needle}") >> nth=0',
        ]

        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if not await loc.is_visible(timeout=500):
                    continue

                # Verificar que el texto sea solo el día (no un párrafo más largo)
                text = (await loc.text_content() or '').strip().lower()
                if len(text) > 30:
                    continue
                if needle not in text:
                    continue

                # Capturar selector específico para re-localizar después
                _selector = selector
                async def _locator_fn(_sel=_selector, _l=loc):
                    return page.locator(_sel).first

                found.append((label, _locator_fn))
                seen_labels.add(label)
                break
            except Exception:
                continue

    return found
