"""
Scraper genérico para estaciones de servicio.
Comparte la lógica de extracción de promociones — cada estación define su URL y selectores específicos.
"""
import asyncio
import re
from typing import List, Dict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


# Diccionarios reutilizables
WALLET_PATTERNS = [
    (r'\bMODO\b', 'MODO'),
    (r'MERCADO\s*PAGO', 'Mercado Pago'),
    (r'PERSONAL\s*PAY', 'Personal Pay'),
    (r'CUENTA\s*DNI', 'Cuenta DNI'),
    (r'\bUAL[AÁ]\b', 'Ualá'),
    (r'NARANJA\s*X', 'Naranja X'),
    (r'YPF\s*APP|APP\s*YPF', 'YPF App'),
    (r'SHELL\s*BOX', 'Shell Box'),
]

BANK_PATTERNS = [
    (r'GALICIA', 'Banco Galicia'),
    (r'MACRO', 'Banco Macro'),
    (r'NACI[OÓ]N|\bBNA\b', 'Banco Nación'),
    (r'BANCO\s*CIUDAD', 'Banco Ciudad'),
    (r'BANCO\s*PROVINCIA|BAPRO', 'Banco Provincia'),
    (r'SANTANDER', 'Banco Santander'),
    (r'BANCO\s*PATAGONIA|\bPATAGONIA\b', 'Banco Patagonia'),
    (r'SUPERVIELLE', 'Supervielle'),
    (r'CREDICOOP', 'Banco Credicoop'),
    (r'\bHSBC\b', 'HSBC'),
    (r'\bBBVA\b', 'BBVA'),
    (r'\bICBC\b', 'ICBC'),
    (r'COMAFI', 'Banco Comafi'),
    (r'BANCO\s*COLUMBIA', 'Banco Columbia'),
]

DAYS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def identify_bank_and_wallet(text: str) -> tuple:
    """Devuelve (bank, wallet) detectados en el texto."""
    text_upper = text.upper()
    bank, wallet = None, None
    for pattern, name in WALLET_PATTERNS:
        if re.search(pattern, text_upper):
            wallet = name
            break
    for pattern, name in BANK_PATTERNS:
        if re.search(pattern, text_upper):
            bank = name
            break
    if not bank and wallet in ['Mercado Pago', 'Ualá', 'Naranja X', 'Personal Pay', 'Cuenta DNI']:
        bank, wallet = wallet, None
    return bank or '', wallet


def extract_discount(text: str) -> str:
    """Extrae el descuento principal del texto."""
    # Reintegro
    m = re.search(r'(\d+)\s*%\s*(?:de\s+)?reintegro', text, re.I)
    if m and int(m.group(1)) > 0:
        return f"{m.group(1)}% reintegro"
    # Descuento explícito
    for pattern in [
        r'(\d+)\s*%\s*(?:de\s+)?(?:descuento|dto|off|ahorro)',
        r'\$\s*(\d+)\s*(?:por\s+litro|/L|por\s+L)',  # $X por litro
        r'(\d+)\s*%\s*OFF',
    ]:
        m = re.search(pattern, text, re.I)
        if m:
            val = int(m.group(1))
            if val > 0:
                return f"{val}%" if "%" in pattern else f"${val}/L"
    return ''


def extract_valid_days(text: str) -> str:
    """Detecta días en el texto."""
    text_lower = text.lower()
    if re.search(r'todos\s+los\s+d[ií]as|toda\s+la\s+semana', text_lower):
        return 'Todos los días'
    found = set()
    for day in DAYS_ES:
        if re.search(rf'\b{day}s?\b', text_lower):
            found.add(day.capitalize())
    if len(found) == 7:
        return 'Todos los días'
    if found:
        order = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        return ', '.join(sorted(found, key=lambda x: order.index(x) if x in order else 99))
    return ''


def extract_tope(text: str) -> str:
    """Extrae tope/máximo del texto."""
    for pattern in [
        r'[Tt]ope[:\s]*\$?\s*([\d.,]+)',
        r'[Mm][aá]ximo[:\s]*\$?\s*([\d.,]+)',
        r'[Hh]asta\s+\$?\s*([\d.,]+)\s+(?:de\s+)?(?:reintegro|descuento)',
    ]:
        m = re.search(pattern, text, re.I)
        if m:
            try:
                amount = float(m.group(1).replace('.', '').replace(',', '.'))
                return f"${amount:,.0f}".replace(',', '.')
            except Exception:
                return f"${m.group(1)}"
    return ''


async def fetch_html(url: str, scroll: bool = True, wait_selector: str = None) -> str:
    """Trae el HTML completo de una página con Playwright."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            await page.goto(url, wait_until='networkidle', timeout=60000)
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    pass
            if scroll:
                for _ in range(5):
                    await page.evaluate('window.scrollBy(0, 600)')
                    await asyncio.sleep(0.4)
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(1)
            return await page.content()
        finally:
            await browser.close()


def parse_promo_cards(html: str, station_name: str, url: str) -> List[Dict]:
    """Encuentra cards de promociones genéricas (descuento + banco/billetera)."""
    soup = BeautifulSoup(html, 'html.parser')
    promos = []
    seen = set()

    for div in soup.find_all('div'):
        text = div.get_text(' ', strip=True)
        if not (50 < len(text) < 2000):
            continue

        has_discount = bool(re.search(r'\d+\s*%|cuotas?\s*sin\s*inter|reintegro|\$\s*\d+\s*(?:por\s+litro|/L)', text, re.I))
        has_bank = bool(re.search(
            r'banco|santander|galicia|bbva|macro|naci[oó]n|provincia|patagonia|credicoop|hsbc|icbc|'
            r'mercado pago|cuenta dni|naranja|ual[aá]|modo|personal pay|comafi|columbia|supervielle',
            text, re.I
        ))
        if not (has_discount and has_bank):
            continue

        # Solo tomar leaf nodes
        child_divs = div.find_all('div', recursive=False)
        is_parent = any(re.search(r'\d+\s*%', c.get_text(' ', strip=True))
                        and len(c.get_text(' ', strip=True)) > 40
                        for c in child_divs)
        if is_parent:
            continue

        key = re.sub(r'\s+', ' ', text[:120])
        if key in seen:
            continue
        seen.add(key)

        bank, wallet = identify_bank_and_wallet(text)
        discount = extract_discount(text)
        if not discount:
            continue

        valid_days = extract_valid_days(text)
        tope = extract_tope(text)

        title_parts = []
        if bank:
            title_parts.append(bank)
        if wallet:
            title_parts.append(f"(vía {wallet})")
        if discount:
            title_parts.append(discount)
        if valid_days:
            title_parts.append(f"- {valid_days}")
        title = ' '.join(title_parts) or text[:80]

        promos.append({
            'supermarket': station_name,
            'title': title,
            'discount': discount,
            'bank': bank,
            'wallet': wallet,
            'valid_days': valid_days,
            'tope': tope,
            'url': url,
            'terms_raw': text[:3000],
        })

    return promos
