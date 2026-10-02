import json
import unittest
from datetime import date
from pathlib import Path

from scrapers.galicia_scraper import GaliciaScraper, next_day

FIXTURE = Path(__file__).parent / 'tests_fixtures' / 'galicia' / 'model.json'


class GaliciaScraperTests(unittest.TestCase):
    def setUp(self):
        self.model = json.loads(FIXTURE.read_text())

    def test_parses_three_tiers_with_stale_legal_date(self):
        # El legal dice 10/09/2026; el 02/10 la próxima fecha es el sábado 10/10
        promos = GaliciaScraper().parse_model(self.model, today=date(2026, 10, 2))
        self.assertEqual([p['discount'] for p in promos], ['10%', '15%', '10% extra'])
        self.assertEqual([p['tope'] for p in promos], ['$10.000 mensual', '$15.000 mensual', '$5.000 mensual'])
        self.assertEqual(promos[1]['title'], 'Banco Galicia 15% en YPF, Shell, Axion y Puma - Día 10 (Éminent)')
        self.assertIn('Plan Sueldo', promos[2]['title'])
        for p in promos:
            self.assertEqual(p['valid_from'], '2026-10-10')
            self.assertEqual(p['valid_until'], '2026-10-10')
            self.assertEqual(p['valid_days'], 'Día 10 de cada mes (Sábado)')
            self.assertEqual(p['merchant_brands'], ['YPF', 'Shell', 'Axion', 'Puma Energy'])
            self.assertEqual(p['merchant_category'], 'fuel')
            self.assertIn('CARTERA DE CONSUMO', p['terms_raw'])
        self.assertEqual(len({p['title'] for p in promos}), 3)

    def test_legal_date_in_future_is_kept(self):
        promos = GaliciaScraper().parse_model(self.model, today=date(2026, 9, 3))
        self.assertEqual(promos[0]['valid_from'], '2026-09-10')
        self.assertEqual(promos[0]['valid_days'], 'Día 10 de cada mes (Jueves)')

    def test_next_day_rolls_over_month_and_year(self):
        self.assertEqual(next_day(10, date(2026, 10, 10)), date(2026, 10, 10))
        self.assertEqual(next_day(10, date(2026, 10, 11)), date(2026, 11, 10))
        self.assertEqual(next_day(10, date(2026, 12, 20)), date(2027, 1, 10))


if __name__ == '__main__':
    unittest.main()
