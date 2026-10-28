import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from database import Database
from scrapers.clash_scraper import ClashScraper


def _clash_script(period="Octubre 2026"):
    payload = {
        "updatedAt": "2026-10-21T15:33:19.528Z",
        "meta": {"topbar": {"period": period}},
        "banks": [
            {"id": "credicoop", "name": "Credicoop"},
            {"id": "visa", "name": "Visa"},
        ],
        "merchants": [{"id": "changomas", "name": "ChangoMas"}],
        "P": [
            {
                "id": "b_123",
                "bk": "credicoop",
                "mc": "changomas",
                "d": 15,
                "cap": "$15.000",
                "fr": "por mes",
                "note": "Mínimo de compra $50.000 · Exclusivo online",
                "_ref": "Pagando con tarjeta Visa y NFC.",
                "cards": ["Visa Black.png"],
                "days": [0, 1, 0, 0, 0, 0, 0],
                "score": 50,
            },
            {
                "id": "b_456",
                "bk": "visa",
                "mc": "changomas",
                "inst": 3,
                "cap": "Sin tope",
                "fr": "",
                "note": "",
                "_ref": "Tres cuotas sin interés.",
                "cards": ["Visa.png"],
                "days": [1, 1, 1, 1, 1, 1, 1],
                "score": 20,
            },
        ],
    }
    return "window.__clashData = " + json.dumps(payload, ensure_ascii=False) + ";"


class ClashScraperTests(unittest.TestCase):
    def test_parses_discount_conditions_days_and_clash_detail_url(self):
        promos = ClashScraper.parse_data_js(
            _clash_script(), "supermarket", today=date(2026, 10, 23)
        )

        self.assertEqual(len(promos), 2)
        promo = promos[0]
        self.assertEqual(promo["merchant_brands"], ["Más Online (ChangoMás)"])
        self.assertEqual(promo["merchant_category"], "supermarket")
        self.assertEqual(promo["bank"], "Banco Credicoop")
        self.assertEqual(promo["discount"], "15%")
        self.assertEqual(promo["valid_days"], "Martes")
        self.assertEqual(promo["valid_from"], "2026-10-01")
        self.assertEqual(promo["valid_until"], "2026-10-31")
        self.assertEqual(promo["store_types"], "Online")
        self.assertEqual(promo["min_purchase"], "$50.000")
        self.assertEqual(promo["tope"], "Tope $15.000 por mes")
        self.assertIn("Visa Black", promo["card_type"])
        self.assertIn("Pagando con tarjeta Visa", promo["terms_raw"])
        self.assertIn("promos.clash.com.ar/supermercados/promocion/", promo["url"])

        installments = promos[1]
        self.assertEqual(installments["discount"], "3 cuotas sin interés")
        self.assertEqual(installments["payment_method"], "Tarjeta Visa")
        self.assertEqual(installments["valid_days"], "Todos los días")

    def test_rejects_snapshot_for_another_month(self):
        with self.assertRaisesRegex(ValueError, "fuera del mes vigente"):
            ClashScraper.parse_data_js(
                _clash_script("Septiembre 2026"), "supermarket", today=date(2026, 10, 23)
            )

    def test_rejects_changed_or_unexpected_data_js_shape(self):
        with self.assertRaisesRegex(ValueError, "no contiene window.__clashData"):
            ClashScraper.parse_data_js("window.clashData = {};", "fuel", today=date(2026, 10, 23))

    def test_same_bank_and_offer_on_different_days_get_distinct_database_titles(self):
        payload = json.loads(_clash_script().split("=", 1)[1].strip().rstrip(";"))
        second = dict(payload["P"][0])
        second["id"] = "b_789"
        second["days"] = [0, 0, 1, 0, 0, 0, 0]
        payload["P"].append(second)
        source = "window.__clashData = " + json.dumps(payload, ensure_ascii=False) + ";"

        promos = ClashScraper.parse_data_js(source, "supermarket", today=date(2026, 10, 23))

        self.assertNotEqual(promos[0]["title"], promos[-1]["title"])
        self.assertIn("Martes", promos[0]["title"])
        self.assertIn("Miércoles", promos[-1]["title"])

    def test_strict_duplicate_check_preserves_different_caps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(str(Path(temp_dir) / "promotions.db"))
            store_id = db.insert_supermarket("Carrefour", "https://example.test", "supermarket")
            db.insert_promotion(store_id, {
                "title": "20% en Carrefour",
                "discount": "20%",
                "bank": "Banco Galicia",
                "valid_days": "Miércoles",
                "tope": "Tope $10.000 por mes",
                "source": "carrefour",
            })
            incoming = {
                "title": "20% en Carrefour con Banco Galicia",
                "discount": "20%",
                "bank": "Banco Galicia",
                "valid_days": "Miércoles",
                "tope": "Tope $20.000 por mes",
            }

            self.assertTrue(db.has_equivalent_promotion(store_id, "clash", incoming))
            self.assertFalse(db.has_equivalent_promotion(store_id, "clash", incoming, strict=True))

    def test_strict_duplicate_check_keeps_offer_when_only_one_source_has_a_cap(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(str(Path(temp_dir) / "promotions.db"))
            store_id = db.insert_supermarket("Carrefour", "https://example.test", "supermarket")
            db.insert_promotion(store_id, {
                "title": "20% en Carrefour",
                "discount": "20%",
                "bank": "Banco Galicia",
                "valid_days": "Miércoles",
                "source": "carrefour",
            })
            incoming = {
                "title": "20% en Carrefour con Banco Galicia",
                "discount": "20%",
                "bank": "Banco Galicia",
                "valid_days": "Miércoles",
                "tope": "Tope $20.000 por mes",
            }

            self.assertFalse(db.has_equivalent_promotion(store_id, "clash", incoming, strict=True))

    def test_installment_count_is_not_a_percentage_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(str(Path(temp_dir) / "promotions.db"))
            store_id = db.insert_supermarket("Carrefour", "https://example.test", "supermarket")
            db.insert_promotion(store_id, {
                "title": "3 cuotas en Carrefour",
                "discount": "3 cuotas sin interés",
                "bank": "Banco Galicia",
                "valid_days": "Todos los días",
                "source": "carrefour",
            })
            incoming = {
                "title": "3% en Carrefour",
                "discount": "3%",
                "bank": "Banco Galicia",
                "valid_days": "Todos los días",
            }
            self.assertFalse(db.has_equivalent_promotion(store_id, "clash", incoming))


if __name__ == "__main__":
    unittest.main()
