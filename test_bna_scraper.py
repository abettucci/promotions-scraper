import unittest
from pathlib import Path

from scrapers.bna_scraper import BnaScraper

FIXTURE = Path(__file__).parent / 'tests_fixtures' / 'bna' / 'ypf.html'


class BnaScraperTests(unittest.TestCase):
    def test_parses_ypf_promo(self):
        promos = BnaScraper().parse_html(FIXTURE.read_text())
        self.assertEqual(len(promos), 1)
        p = promos[0]
        self.assertEqual(p['title'], 'Banco Nación 20% en YPF')
        self.assertEqual(p['discount'], '20%')
        self.assertEqual(p['bank'], 'Banco Nación')
        self.assertEqual(p['wallet'], 'MODO')
        self.assertEqual(p['card_type'], 'Crédito')
        self.assertEqual(p['valid_from'], '2026-03-01')
        self.assertEqual(p['valid_until'], '2026-09-30')
        self.assertEqual(p['tope'], '$10.000 mensual')
        self.assertEqual(p['merchant_brands'], ['YPF'])
        self.assertEqual(p['merchant_category'], 'fuel')
        self.assertIn('MODO BNA+', p['terms_raw'])

    def test_page_without_promo_returns_nothing(self):
        self.assertEqual(BnaScraper().parse_html('<html><h1>Descuentos</h1></html>'), [])


if __name__ == '__main__':
    unittest.main()
