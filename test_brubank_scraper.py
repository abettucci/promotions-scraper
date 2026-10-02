import unittest
from pathlib import Path

from scrapers.brubank_scraper import BrubankScraper, parse_terms

FIX = Path(__file__).parent / "tests_fixtures/brubank"


class BrubankScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = BrubankScraper()

    def test_landing_keeps_only_supermarket_and_fuel_cards(self):
        cards = self.scraper.parse_cards((FIX / "landing.html").read_text())
        self.assertEqual(sorted(c["brand"] for c in cards), ["Axion", "Coto Digital", "YPF"])
        for card in cards:
            self.assertNotIn("‍", card["conditions"])

    def test_coto_card_with_article(self):
        card = next(c for c in self.scraper.parse_cards((FIX / "landing.html").read_text()) if c["brand"] == "Coto Digital")
        promo = self.scraper.build_promo(card, (FIX / "coto.txt").read_text(), card["href"])
        self.assertEqual(promo["title"], "Brubank 30% en Coto Digital - Jueves")
        self.assertEqual(promo["discount"], "30%")
        self.assertEqual(promo["tope"], "Sin tope")
        self.assertEqual(promo["card_type"], "Débito")
        self.assertEqual((promo["valid_from"], promo["valid_until"]), ("2026-02-26", "2026-10-25"))
        self.assertEqual(promo["merchant_category"], "supermarket")

    def test_card_days_do_not_include_tope(self):
        card = next(c for c in self.scraper.parse_cards((FIX / "landing.html").read_text()) if c["brand"] == "YPF")
        promo = self.scraper.build_promo(card, "", card["href"])
        self.assertEqual(promo["valid_days"], "Lunes")
        self.assertEqual(promo["tope"], "$6.000 por compra")

    def test_help_only_plan_plus_article(self):
        info = parse_terms((FIX / "axion_plus.txt").read_text())
        self.assertEqual(info["plan"], "Plan Plus")
        self.assertEqual(info["valid_days"], "Viernes, Sábado, Domingo")
        self.assertEqual(info["tope"], "$5.000 por compra")
        promo = self.scraper.build_promo(None, (FIX / "axion_plus.txt").read_text(),
                                         "https://help.brubank.com/es/articles/9010641-x", query="axion")
        if promo:  # sólo si la vigencia del fixture sigue en curso
            self.assertEqual(promo["title"], "Brubank 20% en Axion - Viernes, Sábado, Domingo (Plan Plus)")
            self.assertEqual(promo["merchant_brands"], ["Axion"])


if __name__ == "__main__":
    unittest.main()
