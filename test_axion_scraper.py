"""Tests offline del scraper de Axion (HTML de Elementor en tests_fixtures/axion)."""
from pathlib import Path

from scrapers.axion_scraper import AxionScraper

FIXTURE = Path(__file__).parent / 'tests_fixtures' / 'axion' / 'page604.html'


def _promos():
    return AxionScraper().parse_html(FIXTURE.read_text(encoding='utf-8'))


def _one(promos, **kw):
    hits = [p for p in promos if all(v in (p.get(k) or '') for k, v in kw.items())]
    assert len(hits) == 1, (kw, [p['title'] for p in promos])
    return hits[0]


def test_unique_titles_and_source_ids():
    promos = _promos()
    assert len(promos) == 8  # ON, BNA, Brubank, Credicoop, Patagonia x2, Galicia x2
    assert len({p['title'] for p in promos}) == len(promos)
    assert len({p['source_id'] for p in promos}) == len(promos)


def test_on_program_is_wallet_not_bank():
    p = _one(_promos(), wallet='ON Axion')
    assert p['bank'] is None
    assert p['valid_days'] == 'Lunes, Viernes'
    assert (p['valid_from'], p['valid_until']) == ('2026-10-01', '2026-12-31')
    assert p['tope'].startswith('$7.000 mensual (niveles 1 y 2); $14.000 mensual')


def test_bna_tope_and_card():
    p = _one(_promos(), bank='Banco Nación')
    assert p['tope'] == '$10.000 mensual'
    assert p['card_type'] == 'Crédito'
    assert p['payment_method'] == 'MODO BNA+'
    assert (p['valid_from'], p['valid_until']) == ('2026-10-01', '2026-10-31')


def test_brubank_plan_ultra_dates_and_uses():
    p = _one(_promos(), bank='Brubank')
    assert p['discount'] == '30%'
    assert (p['valid_from'], p['valid_until']) == ('2026-09-01', '2026-09-30')
    assert p['tope'] == '$6.000 por compra (máx. 5 usos)'
    assert p['valid_days'] == 'Todos los días'


def test_credicoop_month_span():
    p = _one(_promos(), bank='Banco Credicoop')
    assert (p['valid_from'], p['valid_until']) == ('2026-10-01', '2026-10-31')
    assert p['tope'] == '$4.500 o $6.000 semanal'


def test_patagonia_and_galicia_split():
    promos = _promos()
    pat = sorted((p['discount'], p['card_type'], p['tope']) for p in promos if p['bank'] == 'Banco Patagonia')
    assert pat == [('20%', 'Débito', '$7.500 mensual'), ('25%', 'Crédito, Débito', '$15.000 mensual')]
    gal = sorted((p['discount'], p['tope']) for p in promos if p['bank'] == 'Banco Galicia')
    assert gal == [('10%', '$10.000 mensual'), ('15%', '$15.000 mensual')]
    assert all(p['valid_from'] == p['valid_until'] == '2026-10-10'
               for p in promos if p['bank'] == 'Banco Galicia')
