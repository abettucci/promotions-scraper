import unittest
from datetime import date
from pathlib import Path

from scrapers.dia_scraper import DiaScraper

FIXTURE = Path(__file__).parent / "tests_fixtures" / "dia" / "landing.html"


class DiaScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = DiaScraper()
        html = FIXTURE.read_text(encoding="utf-8")
        self.cards = self.scraper._extract_cards(html)
        promos = self.scraper._parse_cards(self.cards, today=date(2026, 10, 2))
        self.promos = {p["title"]: p for p in promos}

    def find(self, prefix):
        matches = [p for t, p in self.promos.items() if t.startswith(prefix)]
        self.assertEqual(len(matches), 1, f"{prefix}: {list(self.promos)}")
        return matches[0]

    def test_uses_content_cards_not_stale_props(self):
        self.assertEqual(len(self.cards), 12)
        self.assertNotIn("STALE", [c.get("__editorItemTitle") for c in self.cards])

    def test_inactive_and_expired_cards_are_dropped(self):
        # 12 cards: 1 inactiva (Banco Ciudad Modo) + 2 con legal vencido el 30/09.
        self.assertEqual(len(self.promos), 9)
        self.assertFalse(any("Ciudadanía" in t or "Nación" in t for t in self.promos))

    def test_prex_single_date_online(self):
        promo = self.find("Prex 30% reintegro")
        self.assertEqual((promo["valid_from"], promo["valid_until"]), ("2026-10-05", "2026-10-05"))
        self.assertEqual(promo["store_types"], "Online")
        self.assertEqual(promo["tope"], "$20.000")
        self.assertEqual(promo["valid_days"], "Lunes")
        self.assertIn("terms_raw", promo)
        self.assertNotIn("legal_text", promo)

    def test_credicoop_without_bank_class_and_percent_from_example(self):
        promo = self.find("Banco Credicoop + MODO 25% reintegro")
        self.assertEqual(promo["bank"], "Banco Credicoop")
        self.assertEqual(promo["valid_days"], "Miércoles")
        self.assertEqual((promo["valid_from"], promo["valid_until"]), ("2026-10-01", "2026-12-31"))
        self.assertEqual(self.scraper._percent_from_example(promo["terms_raw"].upper()), 25)

    def test_installments_never_become_zero_percent(self):
        promo = self.find("Tarjetas de crédito 3 cuotas sin interés")
        self.assertEqual(promo["discount"], "3 cuotas sin interés")
        self.assertEqual(promo["valid_days"], "Sábado")
        self.assertEqual(promo["payment_method"], "Visa, Mastercard, American Express, Cabal")
        plan_z = self.find("Naranja X 3 cuotas sin interés (Plan Z)")
        self.assertEqual(plan_z["valid_days"], "Todos los días")
        mp = self.find("Mercado Pago Hasta 3 cuotas sin interés")
        self.assertEqual(mp["min_purchase"], "$50.000")
        self.assertIn("3 cuotas sin interés desde $150.000", mp["requirements"])
        for promo in self.promos.values():
            self.assertNotRegex(promo["discount"], r"^0+%")
            self.assertNotIn(promo["tope"], ("$.", "$,", "$"))

    def test_naranja_plan_tope_matches_card_percentage(self):
        promo = self.find("Naranja X 25% reintegro (Plan Turbo)")
        self.assertEqual(promo["tope"], "$9.500 semanal")
        self.assertEqual((promo["valid_from"], promo["valid_until"]), ("2026-10-01", "2026-10-31"))

    def test_cuenta_dni_unified_tope_and_regional_stores(self):
        promo = self.find("Cuenta DNI 5% reintegro")
        self.assertEqual(promo["tope"], "$5.000 semanal")
        self.assertEqual(promo["store_types"], "Tiendas")
        self.assertEqual(promo["wallet"], "Cuenta DNI")
        corrientes = self.find("Banco de Corrientes 30% reintegro")
        self.assertEqual(corrientes["store_types"], "Tiendas de Corrientes")
        self.assertEqual(corrientes["tope"], "$20.000 mensual")
        sidecreer = self.find("Sidecreer 25% reintegro")
        self.assertEqual(sidecreer["store_types"], "Tiendas de Entre Ríos")
        self.assertEqual(sidecreer["tope"], "$5.000 por transacción")

    def test_missing_block_returns_no_cards(self):
        self.assertEqual(self.scraper._extract_cards("<html><script>{}</script></html>"), [])


if __name__ == "__main__":
    unittest.main()
