import unittest

from scrapers.mobility_scraper import MobilityScraper


CARD = {
    "benefit": {
        "name": "50% en Transporte",
        "publication": {"slug": "transporte-master", "description": "Reintegro en transporte"},
        "conditions": {
            "schedule": {"days_of_week": ["monday", "tuesday"], "start_date": "2026-10-01", "stop_date": "2026-10-31"},
            "payment_methods": {"methods": [{"type": "credit_card"}, {"type": "debit_card"}]},
            "payment_flow": {"flows": ["instore_nfc"]},
        },
    },
    "card": {"participating_bank": "Banco Galicia"},
    "offer": {"outcomes": {"cashback": {"amount": 50, "amount_type": "percent"}}, "limits": {"period_cap": {"amount_by_period": 15000}}},
}


class MobilityScraperTests(unittest.TestCase):
    def test_public_transit_keeps_payment_and_coverage(self):
        promo = MobilityScraper().parse_card(CARD, {
            "terms_and_conditions": "Promoción válida en AMBA en colectivos, subtes y trenes adheridos. No aplica a pagos en efectivo.",
        })
        self.assertEqual(promo["merchant_category"], "mobility")
        self.assertEqual(promo["mobility_kind"], "public_transit")
        self.assertEqual(promo["merchant_brands"], ["Transporte público"])
        self.assertEqual(promo["card_type"], "Crédito, Débito")
        self.assertIn("AMBA", promo["coverage"])
        self.assertIn("No aplica", promo["exclusions"][0])

    def test_ride_app_is_classified_without_guessing_coverage(self):
        card = dict(CARD)
        card["benefit"] = dict(CARD["benefit"], name="30% en Uber")
        promo = MobilityScraper().parse_card(card, {"terms_and_conditions": "Válido para viajes realizados desde la app Uber."})
        self.assertEqual(promo["merchant_brands"], ["Uber"])
        self.assertEqual(promo["mobility_kind"], "ride_hailing")
        self.assertIsNone(promo["coverage"])

    def test_private_campaign_is_not_published(self):
        self.assertIsNone(MobilityScraper().parse_card(CARD, {
            "terms_and_conditions": "Exclusivo para usuarios invitados por MODO.",
        }))


if __name__ == "__main__":
    unittest.main()
