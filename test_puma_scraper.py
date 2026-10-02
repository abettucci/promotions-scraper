"""Tests offline del scraper de Puma Energy."""
from pathlib import Path

from scrapers.puma_scraper import PumaScraper

FIXTURE = Path(__file__).parent / 'tests_fixtures' / 'puma' / 'promocion_21.html'


def test_comafi_page_parse():
    p = PumaScraper()._parse_promo_page(FIXTURE.read_text(encoding='utf-8'),
                                        'https://pumaenergyarg.com.ar/promocion/21')
    assert p['bank'] == 'Banco Comafi'
    assert p['wallet'] == 'MODO'
    assert p['title'] == 'Banco Comafi 20% - Viernes'
    assert p['card_type'] == 'Crédito, Débito'
    assert (p['valid_from'], p['valid_until']) == ('2026-05-01', '2026-10-31')
    assert p['tope'] == '$5.000 semanal (General); $8.000 semanal (Premium); $10.000 semanal (Único Black)'
    assert p['source_id'] == 'puma:21'


def test_bna_accent_and_title():
    p = PumaScraper().build_promo(
        'Promo BNA | 20% off',
        'Todos los viernes desde el 01/09/2026 al 31/01/2027, con tus tarjetas de crédito visa y '
        'mastercard del banco nación pagando exclusivamente con modo bna+ escaneando qr modo obtenes '
        'un 20% de descuento en tus compras. Tope de devolución: hasta $ 10.000 por cliente.',
        'https://pumaenergyarg.com.ar/promocion/42')
    assert p['bank'] == 'Banco Nación'
    assert p['title'] == 'Banco Nación 20% - Viernes'
    assert p['payment_method'] == 'MODO BNA+'
    assert p['tope'] == '$10.000'
    assert (p['valid_from'], p['valid_until']) == ('2026-09-01', '2027-01-31')


def test_visa_al2_and_pris():
    s = PumaScraper()
    al2 = s.build_promo(
        'Visa AL2',
        'Beneficio exclusivo todos los días pagando con Tarjeta de Crédito VISA AL2. Tope de Descuento '
        'por producto: Diesel (5% de descuento o 200lts o 3 transacciones), Ion Diesel (10% de descuento '
        'o 200lts o 3 transacciones). No acumulable con otras promociones. Válido hasta el 31/12/2026.',
        'https://pumaenergyarg.com.ar/promocion/25')
    assert al2['valid_until'] == '2026-12-31'
    assert al2['valid_days'] == 'Todos los días'
    assert al2['card_type'] == 'Crédito'
    assert al2['discount'].startswith('5%')
    pris = s.build_promo(
        'Puma PRIS',
        'Promoción válida todos los miércoles. 10% de descuento en la compra de Super, Premium e Ion '
        'Diesel pagando con Puma Pris en Estaciones Adheridas. Tope de reintegro: Hasta 50 litros por miércoles.',
        'https://pumaenergyarg.com.ar/promocion/6')
    assert pris['wallet'] == 'Puma Pris'
    assert pris['tope'] == '50 L por miércoles'
    assert pris['valid_days'] == 'Miércoles'


def test_patagonia_tiers_have_distinct_titles():
    s = PumaScraper()
    a = s.build_promo('PATAGONIA - SINGULAR', 'Promoción válida todos los jueves, abonando con Tarjeta de '
                      'Crédito Visa Banco Patagonia, obtenés un 20% de descuento con tope de $10.000 por cliente.',
                      'https://pumaenergyarg.com.ar/promocion/33')
    b = s.build_promo('PATAGONIA - SINGULAR PLAN SUELDO', 'Promoción válida todos los jueves, abonando con '
                      'Tarjeta de Débito o Crédito Visa Banco Patagonia, obtenés un 25% de descuento con tope de '
                      '$15.000 por cliente.', 'https://pumaenergyarg.com.ar/promocion/34')
    assert a['title'] == 'Banco Patagonia 20% Singular - Jueves'
    assert b['title'] == 'Banco Patagonia 25% Singular Plan Sueldo - Jueves'
    assert b['card_type'] == 'Crédito, Débito'
