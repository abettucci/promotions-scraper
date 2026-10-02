import json
import unittest
from datetime import date
from pathlib import Path

from scrapers.masonline_scraper import MasOnlineScraper

FIXTURES = Path(__file__).parent / 'tests_fixtures' / 'masonline'
TODAY = date(2026, 10, 2)


def _flat(name):
    data = json.loads((FIXTURES / name).read_text())
    return [{f['key']: f['value'] for f in doc['fields']} for doc in data['data']['documents']]


class MasOnlineScraperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docs = _flat('get_promos.json')
        banks = {b['id']: b['name'] for b in _flat('get_banks.json')}
        cls.promos = MasOnlineScraper().parse_documents(docs, banks, today=TODAY)
        cls.by_code = {p['title'].rsplit('(', 1)[-1].rstrip(')'): p for p in cls.promos}

    def test_titles_and_source_ids_are_unique(self):
        titles = [p['title'] for p in self.promos]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(len(self.promos), len({p['source_id'] for p in self.promos}))
        for p in self.promos:
            self.assertNotIn(p['discount'], ('', '0%', '00%'))

    def test_specific_dates_go_to_validity_and_title(self):
        credicoop = self.by_code['C2']
        self.assertEqual(credicoop['valid_days'], 'Sábados 24/10, 28/11 y 26/12')
        self.assertEqual((credicoop['valid_from'], credicoop['valid_until']), ('2026-10-24', '2026-12-26'))
        modo = self.by_code['MD-29']
        self.assertEqual(modo['valid_days'], 'Lunes 05/10, 12/10, 19/10 y 26/10')
        self.assertEqual(modo['min_purchase'], '$75.000')
        icbc = self.by_code['IC1']
        self.assertEqual(icbc['valid_days'], 'Sábado 24/10 y Domingo 25/10')
        # El legal de YOY quedó copiado de la promo de jueves: manda la tarjeta.
        yoy = self.by_code['Y2']
        self.assertEqual((yoy['valid_from'], yoy['valid_until']), ('2026-10-24', '2026-10-25'))
        self.assertEqual(yoy['tope'], '$15.000 semanal')

    def test_wallets_qr_promos(self):
        bv = [p for p in self.promos if p['wallet'] == 'Billeteras virtuales (QR)']
        self.assertEqual(sorted(p['discount'] for p in bv), ['15%', '20%'])
        weekend = next(p for p in bv if p['discount'] == '15%')
        self.assertEqual(weekend['valid_days'], 'Viernes, Sábado, Domingo')
        self.assertIn('Mercado Pago', weekend['payment_method'])
        one_day = next(p for p in bv if p['discount'] == '20%')
        self.assertEqual((one_day['valid_from'], one_day['valid_until']), ('2026-10-02', '2026-10-02'))
        mp = self.by_code['MP']
        self.assertEqual((mp['wallet'], mp['valid_days']), ('Mercado Pago', 'Martes'))

    def test_validity_typos_and_month_scope(self):
        mp3 = self.by_code['MP3']  # legal "DEL 1/10/2026 AL 31/12/2025"; active_to 2027-01-01
        self.assertEqual((mp3['valid_from'], mp3['valid_until']), ('2026-10-01', '2026-12-31'))
        self.assertEqual(mp3['min_purchase'], '$150.000')
        cdni = self.by_code['CDNI']  # "LOS JUEVES DE OCTUBRE 2026"
        self.assertEqual((cdni['valid_from'], cdni['valid_until']), ('2026-10-01', '2026-10-31'))
        self.assertEqual((cdni['bank'], cdni['wallet']), ('Banco Provincia', 'Cuenta DNI'))
        nx = self.by_code['NX1']  # "MARTES DE MES DE SEPTIEMBRE Y OCTUBRE 2026"
        self.assertEqual(nx['valid_until'], '2026-10-31')

    def test_entities_card_types_and_topes(self):
        self.assertEqual(self.by_code['P365']['bank'], 'Banco del Chubut')
        self.assertEqual(self.by_code['4CB']['bank'], 'Bancor')
        self.assertEqual(self.by_code['S2']['bank'], 'Banco Supervielle')
        self.assertEqual(self.by_code['S2']['card_type'], 'Débito')
        self.assertEqual(self.by_code['H']['bank'], 'Banco Hipotecario')
        self.assertEqual(self.by_code['H']['card_type'], 'Débito')
        self.assertEqual(self.by_code['P1']['card_type'], 'Crédito')
        galicia = self.by_code['G4']
        self.assertEqual(galicia['bank'], 'Banco Galicia')
        self.assertEqual(galicia['valid_days'], 'Jueves, Viernes, Sábado, Domingo')
        self.assertEqual(galicia['store_types'], 'Tiendas')
        credicuotas = self.by_code['CD']
        self.assertEqual(credicuotas['tope'], '$8.000')
        self.assertIn('$6.000', credicuotas['requirements'])
        self.assertEqual(self.by_code['NX1']['tope'], '$3.000 semanal')

    def test_terms_are_kept(self):
        for p in self.promos:
            self.assertTrue(p['terms_raw'])
        self.assertEqual(self.by_code['C2']['acumulable'], None)
        self.assertEqual(self.by_code['MP']['store_types'], 'Online, Tiendas')


if __name__ == '__main__':
    unittest.main()
