import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from prices.barcodes import valid_gtin
from prices.basket import run_basket
from prices.catalog import Catalog
from prices.history import PriceHistory
from prices.trends import trends


def product(key="ean:4006381333931", price=100, store="dia", category="/Almacén/Azúcar/", stock=True):
    return {"key": key, "name": "Azúcar X 1 kg", "brand": "X", "ean": key[4:], "category": category,
            "offers": [{"store": store, "store_name": store.title(), "price": price,
                        "final_price": 1, "promo": {"entity": "No persistir"},
                        "url": "https://example.test/product", "in_stock": stock}]}


class BarcodeTests(unittest.TestCase):
    def test_gtin_checksums_and_leading_zeroes(self):
        for code in ("4006381333931", "04006381333931", "036000291452", "96385074"):
            self.assertTrue(valid_gtin(code), code)
        for code in ("4006381333932", "00000000", "abc", "https://x.test/", "４００６３８１３３３９３１"):
            self.assertFalse(valid_gtin(code), code)


class CatalogFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = PriceHistory(Path(self.tmp.name)/"prices.db")
        self.catalog = Catalog(self.history)
        self.today = date(2026, 10, 31)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, groups, days=0):
        return self.history.record_groups(groups, "azucar", self.today+timedelta(days=days))


class CatalogTests(CatalogFixture, unittest.TestCase):
    def test_confirmation_updates_without_history_growth_or_personalized_price(self):
        self.assertEqual(self.record([product()], -1), 1)
        self.assertEqual(self.record([product()]), 0)
        data = self.catalog.browse(today=self.today)
        self.assertEqual(data["products"][0]["observed_at"], self.today.isoformat())
        self.assertEqual(data["products"][0]["price"], 100)
        detail = self.catalog.product("ean:4006381333931", today=self.today)
        self.assertEqual(detail["offers"][0]["final_price"], 100)
        self.assertIsNone(detail["offers"][0]["promo"])

    def test_exact_barcode_lookup_and_no_fuzzy_fallback(self):
        self.record([product()])
        self.assertEqual(self.catalog.browse(ean="04006381333931", today=self.today)["total"], 1)
        self.assertEqual(self.catalog.browse(ean="96385074", today=self.today)["total"], 0)

    def test_stale_out_of_stock_and_unsafe_urls_not_listed(self):
        self.record([product("ean:1")], -4)
        self.record([product("ean:2", stock=False)])
        unsafe = product("ean:3")
        unsafe["offers"][0]["url"] = "javascript:alert(1)"
        self.record([unsafe])
        self.assertEqual(self.catalog.browse(today=self.today)["total"], 0)
        self.assertIsNone(self.catalog.product("ean:1", today=self.today))

    def test_facets_pagination_sort_and_accent_search(self):
        self.record([product("ean:1", 300), product("ean:2", 100),
                     product("ean:3", 200, category="/Bebidas/Gaseosas/")])
        page = self.catalog.browse(q="azucar", sort="price_asc", rubric="Almacén", page_size=1,
                                   today=self.today)
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["products"][0]["key"], "ean:2")
        self.assertEqual(len(page["facets"]), 2)
        self.assertEqual(self.catalog.browse(page=99, rubric="Almacén", today=self.today)["total"], 2)
        for query in ("%", "' OR 1=1 --", "_"):
            # norm removes punctuation; SQL binding still protects all inputs.
            self.catalog.browse(q=query, today=self.today)
        self.assertIsNotNone(self.history.product("ean:1"))

    def test_late_backfill_does_not_replace_latest_offer(self):
        self.record([product(price=200)])
        self.record([product(price=100)], -1)
        self.assertEqual(self.catalog.browse(today=self.today)["products"][0]["price"], 200)

    def test_other_facet_includes_products_with_missing_category(self):
        self.record([product(category="")])
        self.assertEqual(self.catalog.browse(rubric="Otros", today=self.today)["total"], 1)

    def test_basket_keeps_more_groups_without_additional_search_calls(self):
        calls = []
        def search(query, **kwargs):
            calls.append(kwargs)
            return {"groups": [product("ean:"+str(i)) for i in range(12)]}
        stats = run_basket(self.history, basket=[{"query": "azucar"}], pause=0, search=search, log=lambda _: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["max_groups"], 12)
        self.assertEqual(stats["products"], 12)

    def test_empty_basket_does_not_claim_success(self):
        run_basket(self.history, basket=[{"query": "nada"}], search=lambda *a, **k: {"groups": []}, pause=0, log=lambda _: None)
        self.assertIsNone(self.history.get_meta("basket_last_run"))

    def test_partial_manual_collection_does_not_delay_scheduled_full_run(self):
        run_basket(self.history, basket=[{"query": "azucar"}], search=lambda *a, **k: {"groups": [product()]},
                   pause=0, log=lambda _: None, mark_complete=False)
        self.assertIsNone(self.history.get_meta("basket_last_run"))


class TrendTests(CatalogFixture, unittest.TestCase):
    def test_same_product_same_store_change_and_no_invented_history(self):
        for i in range(5):
            self.record([product("ean:"+str(i), 100)], -30)
            self.record([product("ean:"+str(i), 120)])
        row = trends(self.history, 30, self.today)["categories"][0]
        self.assertEqual(row["change_pct"], 20)
        self.assertEqual(row["coverage_pct"], 100)
        self.assertEqual(trends(self.history, 7, self.today)["categories"], [])

    def test_store_switch_and_low_coverage_do_not_create_an_index(self):
        for i in range(5):
            self.record([product("ean:"+str(i), 100)], -30)
            self.record([product("ean:"+str(i), 50, store="jumbo")])
        row = trends(self.history, 30, self.today)["categories"][0]
        self.assertIsNone(row["change_pct"])
        self.assertEqual(row["compared_products"], 0)

    def test_each_product_weights_the_same_regardless_of_store_count(self):
        for i in range(5):
            self.record([product("ean:"+str(i), 100)], -30)
            self.record([product("ean:"+str(i), 120 if i == 0 else 100)])
        self.record([product("ean:0", 100, "jumbo")], -30)
        self.record([product("ean:0", 120, "jumbo")])
        self.assertEqual(trends(self.history, 30, self.today)["categories"][0]["change_pct"], 4)

    def test_minimum_product_count_does_not_override_low_coverage(self):
        for i in range(10):
            self.record([product("ean:"+str(i), 100)], -30)
            if i < 5:
                self.record([product("ean:"+str(i), 110)])
        row = trends(self.history, 30, self.today)["categories"][0]
        self.assertEqual(row["compared_products"], 5)
        self.assertEqual(row["coverage_pct"], 50)
        self.assertIsNone(row["change_pct"])


class CatalogApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import config
        cls.tmp = tempfile.TemporaryDirectory()
        cls.config_patch = patch.multiple(config, DATABASE_PATH=Path(cls.tmp.name)/"promos.db",
                                         USERS_DB_PATH=Path(cls.tmp.name)/"users.db",
                                         PRICES_DB_PATH=Path(cls.tmp.name)/"prices.db")
        cls.config_patch.start()
        cls.env_patch = patch.dict(os.environ, {"ENABLE_SCRAPER": "false", "ENABLE_PRICES_JOB": "false", "ENABLE_EXTERNAL_SOURCES_JOB": "false"})
        cls.env_patch.start()
        import api
        from database import UserDatabase
        from fastapi.testclient import TestClient
        cls.api = api
        cls.db_patch = patch.object(api, "_db", UserDatabase(config.USERS_DB_PATH))
        cls.db_patch.start()
        cls.client = TestClient(api.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.db_patch.stop()
        cls.config_patch.stop()
        cls.env_patch.stop()
        cls.tmp.cleanup()

    def test_public_routes_and_schema_constraints(self):
        with patch.object(self.api, "_public_assistant_rate_key", return_value="test-hmac"):
            for route in ("/api/prices/catalog", "/api/prices/trends?days=7", "/api/prices/trends?days=30"):
                self.assertEqual(self.client.get(route).status_code, 200, route)
            for suffix in ("?page_size=999", "?sort=sql", "?ean=4006381333932", "?ean=https://x", "?rubric=../"):
                self.assertEqual(self.client.get("/api/prices/catalog"+suffix).status_code, 422, suffix)
            self.assertEqual(self.client.get("/api/prices/trends?days=10").status_code, 422)
            self.assertEqual(self.client.get("/api/prices/catalog/product?key=ean:123").status_code, 404)
            with patch.object(self.api._db, "consume_public_assistant_quota", return_value=3600):
                self.assertEqual(self.client.get("/api/prices/catalog").status_code, 429)
            with patch("prices.catalog.Catalog.browse", side_effect=__import__("sqlite3").OperationalError("secret-db-error")):
                response = self.client.get("/api/prices/catalog")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("secret-db-error", response.text)

    def test_catalog_selection_can_be_saved_and_appears_in_watchlist(self):
        import config
        from prices.models import Offer
        item = product()
        PriceHistory(config.PRICES_DB_PATH).record_groups([item], "Azúcar X 1 kg")
        user_id = self.api._db.create_user("catalog-test@example.test", "test-hash")
        old_overrides = self.api.app.dependency_overrides.copy()
        self.api.app.dependency_overrides[self.api.get_current_user] = lambda: {"id": user_id, "telegram_chat_id": None}
        try:
            with patch.object(self.api, "_public_assistant_rate_key", return_value="test-hmac"):
                catalog = self.client.get("/api/prices/catalog?ean=4006381333931").json()
                self.assertEqual(catalog["total"], 1)
                key = catalog["products"][0]["key"]
                self.assertEqual(self.client.get("/api/prices/catalog/product", params={"key": key}).status_code, 200)
                offer = Offer(store="dia", store_name="Día", merchant="Supermercados Día",
                              title=item["name"], price=100, url="https://example.test/product", ean=item["ean"])
                with patch("prices.search._fetch_offers", return_value=([offer], [])), \
                     patch.object(self.api, "_assistant_promotions", return_value=[]):
                    saved = self.client.post("/api/prices/alerts", json={"query": item["name"], "key": key})
                self.assertEqual(saved.status_code, 200, saved.text)
                listed = self.client.get("/api/auth/me/watchlist").json()
                self.assertIn(key, [p["product_key"] for p in listed["products"]])
        finally:
            self.api.app.dependency_overrides.clear()
            self.api.app.dependency_overrides.update(old_overrides)


if __name__ == "__main__":
    unittest.main()
