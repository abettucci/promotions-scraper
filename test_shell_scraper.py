"""Tests offline del scraper de Shell (modelo AEM guardado en tests_fixtures/shell)."""
import json
from pathlib import Path

from scrapers.shell_scraper import ShellScraper, parse_dates

FIXTURE = Path(__file__).parent / 'tests_fixtures' / 'shell' / 'model.json'


def _promos():
    return ShellScraper().parse_model(json.loads(FIXTURE.read_text(encoding='utf-8')))


def _by_title(promos, needle):
    hits = [p for p in promos if needle in p['title']]
    assert hits, f"no hay promo con {needle!r}: {[p['title'] for p in promos]}"
    return hits[0]


def test_parse_dates_variants():
    assert parse_dates('todos los días hasta el 30/09/2026.') == (None, '2026-09-30')
    assert parse_dates('Oferta válida hasta el 30/09/2026 a las 23:59 hs') == (None, '2026-09-30')
    assert parse_dates('Válido los viernes del mes de septiembre de 2026 en estaciones') == ('2026-09-01', '2026-09-30')
    assert parse_dates('Válida el jueves 10 de septiembre para compras', 2026) == ('2026-09-10', '2026-09-10')
    assert parse_dates('los domingos del 1 de septiembre al 30 de septiembre de 2026') == ('2026-09-01', '2026-09-30')
    assert parse_dates('los días lunes comprendidos desde el 07/09/26 al 26/10/26') == ('2026-09-07', '2026-10-26')


def test_titles_and_source_ids_are_unique():
    promos = _promos()
    assert len(promos) == 6  # Bancor, Ripio, Galicia x3, Comafi
    assert len({p['title'] for p in promos}) == len(promos)
    assert len({p['source_id'] for p in promos}) == len(promos)
    assert all(p['valid_until'] for p in promos)


def test_bancor_is_not_banco_provincia():
    p = _by_title(_promos(), 'Bancor')
    assert p['bank'] == 'Bancor'
    assert p['discount'] == '10% (15% Black/Bancor Premier)'
    assert p['tope'] == '$10.000 mensual'
    assert p['card_type'] == 'Crédito'
    assert p['valid_days'] == 'Lunes'
    assert (p['valid_from'], p['valid_until']) == ('2026-09-07', '2026-10-26')


def test_comafi_negated_mercadopago_and_tiers():
    p = _by_title(_promos(), 'Banco Comafi')
    assert p['wallet'] == 'MODO'
    assert p['discount'] == '20%'
    assert p['tope'] == '$6.000 semanal (Global/Classic/Premium/Platinum); $10.000 semanal (Único Black/Signature)'
    assert p['valid_until'] == '2026-09-30'


def test_ripio_promo_is_present():
    p = _by_title(_promos(), 'Ripio')
    assert p['wallet'] == 'Ripio'
    assert p['discount'] == '10% + 5% reintegro UXD'
    assert p['valid_days'] == 'Miércoles'


def test_galicia_split_per_legal():
    galicia = [p for p in _promos() if p['bank'] == 'Banco Galicia']
    assert sorted(p['discount'] for p in galicia) == ['10%', '10% extra Haberes', '15% Éminent']
    assert all(p['valid_from'] == p['valid_until'] == '2026-09-10' for p in galicia)
