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

    Toma screenshots de la página completa (con scroll) y los envía a Claude para extracción.
    """
    try:
        from .ai_extractor import AIExtractor
    except ImportError:
        print(f"   ❌ anthropic no instalado — no se puede usar AI")
        return []

    if not os.getenv("ANTHROPIC_API_KEY"):
        print(f"   ❌ ANTHROPIC_API_KEY no configurada")
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

            # Esperar a que cargue todo el JS
            await asyncio.sleep(3)

            # Si hay tabs (Lunes/Martes/...) — clickear cada una y capturar todo
            await _click_day_tabs_if_present(page)

            # Scroll completo para forzar carga lazy
            await _scroll_full_page(page)

            # Debug
            if debug_name:
                try:
                    html = await page.content()
                    with open(f'debug_{debug_name}.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    await page.screenshot(path=f'debug_{debug_name}.png', full_page=True)
                    print(f"   📸 Debug guardado: debug_{debug_name}.html/.png")
                except Exception as e:
                    print(f"   ⚠️ No se pudo guardar debug: {e}")

            # Usar AI con prompt específico para combustibles
            extractor = AIExtractor()
            extractor.system_prompt = FUEL_SYSTEM_PROMPT
            promos = await extractor.extract_from_screenshot(page, name, url, scroll_and_capture=True)

            # Normalizar para que coincida con el schema de DB
            normalized = []
            for p in promos:
                normalized.append({
                    'supermarket': name,
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
            print(f"✅ {name}: {len(normalized)} promociones extraídas con AI")
            return normalized

        finally:
            await browser.close()


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


async def _click_day_tabs_if_present(page):
    """Si la página tiene tabs por día (Lunes/Martes/...), los clickea para que carguen su contenido."""
    days = ['lunes', 'martes', 'miércoles', 'miercoles', 'jueves',
            'viernes', 'sábado', 'sabado', 'domingo']
    clicked = 0
    for day in days:
        # Buscar elementos clickeables que contengan ese día
        for selector in [
            f'a:has-text("{day}")',
            f'button:has-text("{day}")',
            f'[role="tab"]:has-text("{day}")',
            f'li:has-text("{day}")',
        ]:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=500):
                    await el.click(timeout=1500)
                    await asyncio.sleep(0.5)
                    clicked += 1
                    break
            except Exception:
                pass
    if clicked:
        print(f"   📅 Cliqueados {clicked} tabs de día")
