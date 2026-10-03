import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from prices.effective import apply_best_promo, money
from prices.matching import group_key, model_code, norm
from prices.models import Offer
from prices.registry import STORES
from prices.search import _cache, search_prices
from prices.sources import vtex

FIXTURES = Path(__file__).parent / "tests_fixtures" / "prices"
STORE = {s.key: s for s in STORES}
SATURDAY = date(2026, 10, 3)


def offer(store, title, price, ean="", brand="", merchant=None):
    s = STORE[store]
    return Offer(store=s.key, store_name=s.name, merchant=merchant or s.merchant,
                 title=title, price=price, url=f"https://{s.host}/p", brand=brand, ean=ean)


class VtexParsingTests(unittest.TestCase):
    def test_price_includes_tax_published_separately(self):
        product = json.loads((FIXTURES / "vtex_fravega_product.json").read_text())
        parsed = vtex.parse_product(STORE["fravega"], product)
        commercial = product["items"][0]["sellers"][0]["commertialOffer"]
        self.assertAlmostEqual(parsed.price, commercial["Price"] + commercial["Tax"], places=2)
        self.assertTrue(parsed.ean)
        self.assertTrue(parsed.url.startswith("https://"))

    def test_query_spaces_are_percent_encoded(self):
        class Response:
            status_code = 206
            def json(self):
                return []
        with patch("prices.sources.vtex.requests.get", return_value=Response()) as get:
            vtex.search(STORE["carrefour"], "leche la serenisima 1l")
        self.assertIn("ft=leche%20la%20serenisima%201l", get.call_args.args[0])


class MatchingTests(unittest.TestCase):
    def test_sizes_are_normalized(self):
        self.assertIn("1.5l", norm("Aceite Cocinero 1,5 Lt."))
        self.assertIn("1l", norm("Leche 1 Litro"))

    def test_group_key_prefers_ean_then_model(self):
        self.assertEqual(group_key("Leche", "La Serenísima", "07790742348005"), "ean:7790742348005")
        self.assertEqual(model_code('Smart TV Samsung 50" UN50U8000FGCZB'), "un50u8000fgczb")
        self.assertTrue(group_key('TV Samsung UN50U8000FGCZB', "Samsung", "").startswith("model:"))

    def test_search_groups_same_ean_and_merges_same_model(self):
        offers = [
            offer("carrefour", "Leche La Serenisima 1L", 3119, ean="7790742358400", brand="La Serenisima"),
            offer("dia", "Leche La Serenísima Barista 1 L", 3000, ean="7790742358400", brand="La Serenisima"),
            offer("fravega", 'Smart TV Samsung 50" UN50U8000FG', 900000, ean="1189300000008", brand="Samsung"),
            offer("coppel", 'Smart TV Samsung 50" Crystal UN50U8000FGCZB', 750000, brand="Samsung"),
        ]
        _cache.clear()
        with patch("prices.search._fetch_offers", return_value=(offers, [])):
            milk = search_prices("leche la serenisima 1l")
            tv = search_prices("smart tv samsung 50")
        self.assertEqual(milk["groups"][0]["store_count"], 2)
        self.assertEqual(milk["groups"][0]["offers"][0]["store"], "dia")
        self.assertEqual(tv["groups"][0]["store_count"], 2)


class EffectivePriceTests(unittest.TestCase):
    PROMOS = [
        {"supermarket_name": "Supermercados Día", "title": "MODO 20% reintegro - Viernes, Sábado",
         "discount": "20% reintegro", "wallet": "MODO", "valid_days": "Viernes, Sábado",
         "tope": "$20.000 mensual", "min_purchase": "$35.000"},
        {"supermarket_name": "Supermercados Día", "title": "Naranja X 30% - Martes", "discount": "30%",
         "bank": "Naranja X", "valid_days": "Martes", "tope": "$12.000 semanal"},
        {"supermarket_name": "Jumbo (Cencosud)", "title": "CencoPay 25% en galletitas y bebidas - Sábado",
         "discount": "25%", "bank": "CencoPay", "valid_days": "Sábado"},
        {"supermarket_name": "Carrefour", "title": "Patagonia 30%", "discount": "30%",
         "bank": "Banco Patagonia", "valid_days": "Sábado", "tope": "$5.000"},
    ]

    def test_money_parsing(self):
        self.assertEqual(money("$10.000 semanal"), 10000)
        self.assertEqual(money("Sin tope"), float("inf"))

    def test_only_promos_valid_that_day_apply_and_min_purchase_is_flagged(self):
        result = apply_best_promo(offer("dia", "Aceite 1,5 L", 6925), self.PROMOS, SATURDAY)
        self.assertEqual(result.savings, 1385)
        self.assertEqual(result.promo["entity"], "MODO")
        self.assertTrue(result.promo["requires_min_purchase"])

    def test_cap_limits_savings(self):
        result = apply_best_promo(offer("carrefour", "Heladera Samsung", 1_000_000), self.PROMOS, SATURDAY)
        self.assertEqual(result.savings, 5000)
        self.assertEqual(result.final_price, 995_000)

    def test_category_scoped_promo_does_not_apply_to_other_products(self):
        result = apply_best_promo(offer("jumbo", "Heladera Samsung No Frost", 1_200_000), self.PROMOS, SATURDAY)
        self.assertIsNone(result.promo)
        self.assertEqual(result.final_price, 1_200_000)

    def test_payment_methods_filter(self):
        result = apply_best_promo(offer("dia", "Aceite", 6925), self.PROMOS, SATURDAY, [{"name": "Naranja X"}])
        self.assertIsNone(result.promo)


if __name__ == "__main__":
    unittest.main()
