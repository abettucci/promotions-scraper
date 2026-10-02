import json
import unittest
from pathlib import Path

from scrapers.modo_scraper import ModoScraper

FIXTURES = Path(__file__).parent / 'tests_fixtures' / 'modo'


class ModoScraperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cards = json.loads((FIXTURES / 'filter.json').read_text())['cards']
        details = json.loads((FIXTURES / 'details.json').read_text())
        cls.promos = ModoScraper().parse_cards(cards, details)
        cls.by_bank = {}
        for p in cls.promos:
            cls.by_bank.setdefault(p['bank'], []).append(p)

    def test_filters_private_benefits(self):
        slugs = ' '.join(p['source_id'] for p in self.promos)
        self.assertNotIn('beneficio-telefilms', slugs)   # corporativo
        self.assertNotIn('senaf', slugs)                 # cliente seleccionado
        self.assertNotIn('seguros-auto', slugs)          # exclusivo seguros de auto
        self.assertEqual(len(self.promos), 5)

    def test_macro_selecta_levels_are_grouped(self):
        (macro,) = self.by_bank['Banco Macro']
        self.assertEqual(macro['title'], 'Macro Selecta 30% en YPF vía MODO - Miércoles')
        self.assertEqual(macro['merchant_brands'], ['YPF'])
        self.assertEqual(macro['merchant_category'], 'fuel')
        self.assertEqual(macro['wallet'], 'MODO')
        self.assertEqual(macro['tope'], 'Nivel 1: $15.000 / Nivel 4: $90.000 mensual')
        self.assertEqual(macro['valid_from'], '2026-06-01')
        self.assertEqual(macro['valid_until'], '2027-03-31')
        self.assertEqual(macro['discount'], '30% reintegro')

    def test_comafi_segments_share_one_promo(self):
        (comafi,) = self.by_bank['Banco Comafi']
        self.assertEqual(comafi['title'], 'Banco Comafi 20% en YPF vía MODO - Sábado')
        self.assertEqual(comafi['tope'], 'Ahorro, Global o Classic: $6.000 / Único Black: $10.000 semanal')
        self.assertEqual(comafi['card_type'], 'Crédito, Débito')

    def test_generic_place_uses_description_brands_or_all_stations(self):
        (ciudad,) = self.by_bank['Banco Ciudad']
        self.assertEqual(ciudad['merchant_brands'], ['YPF', 'Shell', 'Axion'])
        self.assertEqual(ciudad['valid_days'], 'Domingo')
        (credicoop,) = self.by_bank['Banco Credicoop']
        self.assertEqual(credicoop['merchant_brands'], ['YPF', 'Shell', 'Axion', 'Puma Energy'])
        self.assertEqual(credicoop['title'],
                         'Banco Credicoop 5% extra en estaciones de servicio vía MODO - Viernes (Plan Sueldo)')
        self.assertEqual(credicoop['tope'], '$1.500 semanal')

    def test_modo_own_promo_without_bank(self):
        (wico,) = self.by_bank[None]
        self.assertEqual(wico['title'], 'MODO 15% en WICO - Jueves')
        self.assertEqual(wico['merchant_brands'], ['WICO'])
        self.assertIsNone(wico['tope'])


if __name__ == '__main__':
    unittest.main()
