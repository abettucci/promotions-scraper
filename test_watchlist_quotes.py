import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from prices.history import PriceHistory
from prices.watchlist_quotes import WatchlistQuotes, category_for

NOW = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)


def alert(key="title:leche", id=1):
    return {"id": id, "product_key": key, "product_name": "Leche X 1 L", "query": "leche X", "category": "", "baseline_price": 0}


def group(key="title:leche", price=100):
    return {"key": key, "offers": [{"store": "coto", "price": price, "final_price": 1,
            "url": "https://www.coto.com.ar/producto", "promo": {"entity": "secret-profile"}}]}


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.history = PriceHistory(Path(self.temp.name)/"prices.db")
        self.quotes = WatchlistQuotes(self.history)

    def tearDown(self):
        self.temp.cleanup()

    def test_snapshot_is_private_and_stores_only_published_price(self):
        self.quotes.save(1, "title:leche", group(), NOW)
        first = self.quotes.enrich(1, [alert()], NOW)[0]
        second = self.quotes.enrich(2, [alert()], NOW)[0]
        self.assertEqual(first["best_offer"]["price"], 100)
        self.assertNotIn("promo", first["best_offer"])
        self.assertIsNone(second["best_offer"])

    def test_zero_negative_nan_and_unsafe_urls_are_not_quotes(self):
        for price in (0, -1, float("nan"), float("inf")):
            self.quotes.save(1, "title:leche", group(price=price), NOW)
            self.assertIsNone(self.quotes.enrich(1, [alert()], NOW)[0]["best_offer"])
        unsafe = group()
        unsafe["offers"][0]["url"] = "javascript:alert(1)"
        self.assertFalse(self.quotes.save(1, "title:leche", unsafe, NOW)["offers"])

    def test_stale_and_future_quotes_are_not_recommended(self):
        for checked in (NOW-timedelta(days=4), NOW+timedelta(hours=1)):
            self.quotes.save(1, "title:leche", group(), checked)
            self.assertIsNone(self.quotes.enrich(1, [alert()], NOW)[0]["best_offer"])

    def test_exact_key_is_required_and_recent_results_are_reused(self):
        search = unittest.mock.Mock(return_value={"groups": [group("title:otra leche")]})
        result = self.quotes.refresh(1, [alert()], now=NOW, search=search)
        self.assertEqual(result[0]["status"], "missing")
        self.assertIsNone(self.quotes.enrich(1, [alert()], NOW)[0]["best_offer"])
        self.quotes.refresh(1, [alert()], now=NOW+timedelta(minutes=10), search=search)
        self.assertEqual(search.call_count, 1)

    def test_transport_failure_does_not_clear_or_redate_previous_prices(self):
        self.quotes.save(1, "title:leche", group(), NOW-timedelta(hours=2))
        result = self.quotes.refresh(1, [alert()], now=NOW,
                                    search=lambda *a, **k: {"groups": [], "failed_stores": ["Coto"]})
        self.assertEqual(result[0]["status"], "error")
        self.assertEqual(self.quotes.load(1, "title:leche")["checked_at"], NOW-timedelta(hours=2))

    def test_groups_legacy_uncategorized_products_from_their_names(self):
        for name, expected in (("Vino Saint Felicien Malbec 750 ml", "Bebidas"),
                               ("Mostaza Natura 250 cc", "Almacén"),
                               ("Crema La Serenísima Culinaria 330 ml", "Lácteos"),
                               ("Hummus Kyros clásico 230 g", "Almacén"),
                               ("Nachos Macritas Original 150 g", "Almacén")):
            self.assertEqual(category_for({"product_name": name})[0], expected, name)


class WatchlistApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import config
        from database import Database, UserDatabase
        cls.temp = tempfile.TemporaryDirectory()
        cls.config_patch = patch.multiple(config, DATABASE_PATH=Path(cls.temp.name)/"promos.db",
            USERS_DB_PATH=Path(cls.temp.name)/"users.db", PRICES_DB_PATH=Path(cls.temp.name)/"prices.db")
        cls.config_patch.start()
        cls.env_patch = patch.dict(os.environ, {"ENABLE_SCRAPER":"false", "ENABLE_PRICES_JOB":"false", "ENABLE_EXTERNAL_SOURCES_JOB":"false"})
        cls.env_patch.start()
        import api
        from fastapi.testclient import TestClient
        cls.api = api
        Database(config.DATABASE_PATH)
        cls.db = UserDatabase(config.USERS_DB_PATH)
        cls.db_patch = patch.object(api, "_db", cls.db)
        cls.db_patch.start()
        cls.uid = cls.db.create_user("watchlist1@example.test", "test-hash")
        cls.other = cls.db.create_user("watchlist2@example.test", "test-hash")
        cls.owned = cls.db.add_price_alert(cls.uid, "title:leche", "Leche X 1 L", "leche X", 0)
        cls.foreign = cls.db.add_price_alert(cls.other, "title:leche", "Leche X 1 L", "leche X", 0)
        cls.client = TestClient(api.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.db_patch.stop()
        cls.config_patch.stop()
        cls.env_patch.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.overrides = self.api.app.dependency_overrides.copy()
        self.api.app.dependency_overrides[self.api.get_current_user] = lambda: {"id": self.uid}

    def tearDown(self):
        self.api.app.dependency_overrides.clear()
        self.api.app.dependency_overrides.update(self.overrides)

    def test_anonymous_requests_cannot_read_or_refresh_a_private_basket(self):
        self.api.app.dependency_overrides.pop(self.api.get_current_user)
        with patch("prices.watchlist_quotes.WatchlistQuotes.refresh") as fetch:
            self.assertNotEqual(self.client.get("/api/auth/me/watchlist/basket").status_code, 200)
            self.assertNotEqual(self.client.post("/api/auth/me/watchlist/refresh-prices", json={"alert_ids":[self.owned]}).status_code, 200)
            fetch.assert_not_called()

    def test_spoofing_owner_foreign_ids_and_oversized_batches_are_rejected(self):
        with patch("prices.watchlist_quotes.WatchlistQuotes.refresh") as fetch:
            for payload in ({"alert_ids": [self.foreign]}, {"alert_ids": [999999]}):
                self.assertEqual(self.client.post("/api/auth/me/watchlist/refresh-prices", json=payload).status_code, 404)
            for payload in ({"alert_ids":[self.owned], "user_id":self.other}, {"alert_ids":[1,2,3,4]},
                            {"alert_ids":[True]}, {"alert_ids":["1"]}, {"alert_ids":[]}, {"alert_ids":[self.owned,self.owned]}):
                self.assertEqual(self.client.post("/api/auth/me/watchlist/refresh-prices", json=payload).status_code, 422, payload)
            fetch.assert_not_called()

    def test_refresh_to_grouped_list_and_basket_without_scraping_on_get(self):
        with patch("prices.search.search_prices", return_value={"groups":[group(price=180)]}) as fetch:
            result = self.client.post("/api/auth/me/watchlist/refresh-prices", json={"alert_ids":[self.owned]})
            self.assertEqual(result.status_code, 200, result.text)
            data = self.client.get("/api/auth/me/watchlist").json()
            self.assertEqual(data["products"][0]["category_path"][0], "Lácteos")
            self.assertEqual(data["products"][0]["best_offer"]["price"], 180)
            plan = self.client.get("/api/auth/me/watchlist/basket").json()
            self.assertEqual(plan["reference"]["total"], 180)
            self.assertFalse(plan["shipping_included"])
            self.assertEqual(fetch.call_count, 1)

    def test_quote_failure_keeps_saved_list_visible_and_rate_limit_fails_closed(self):
        with patch("prices.watchlist_quotes.WatchlistQuotes.enrich", side_effect=sqlite3.OperationalError("sensitive-db-path")):
            result = self.client.get("/api/auth/me/watchlist")
            self.assertEqual(result.status_code, 200)
            self.assertFalse(result.json()["prices_available"])
            self.assertTrue(result.json()["products"])
            self.assertNotIn("sensitive-db-path", result.text)
        with patch.object(self.db, "consume_public_assistant_quota", return_value=3600):
            result = self.client.post("/api/auth/me/watchlist/refresh-prices", json={"alert_ids":[self.owned]})
            self.assertEqual(result.status_code, 429)


if __name__ == "__main__":
    unittest.main()
