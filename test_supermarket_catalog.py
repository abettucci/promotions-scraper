import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from prices.catalog import Catalog
from prices.catalog_crawl import _new_state, crawl_step
from prices.history import PriceHistory
from prices.matching import group_key
from prices.models import Offer
from prices.registry import STORES
from prices.search import search_prices
from prices.sources import coto, vtex

STORES_BY_KEY = {store.key: store for store in STORES}


def offer(store="coto", source_id="123", ean="", price=100):
    return Offer(store=store, store_name=store.title(), merchant=None, title="Arroz marca propia",
                 price=price, url="https://example.test/product", source_id=source_id, ean=ean)


class CrawlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = PriceHistory(Path(self.tmp.name) / "prices.db")
        self.now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def test_coto_resumes_after_failure_and_records_store_sku_without_ean(self):
        store = STORES_BY_KEY["coto"]
        calls = []

        def page(_store, offset, limit):
            calls.append(offset)
            if len(calls) == 2:
                raise TimeoutError("temporal")
            return {"count": 1, "total": 2, "offers": [offer(source_id=str(offset + 1))]}

        self.assertEqual(crawl_step(self.history, store, now=self.now, fetch=page)["status"], "page")
        with self.assertRaises(TimeoutError):
            crawl_step(self.history, store, now=self.now, fetch=page)
        result = crawl_step(PriceHistory(self.history.db_path), store, now=self.now, fetch=page)
        self.assertEqual(calls, [0, 1, 1])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(Catalog(self.history).browse(today=self.now.date())["total"], 2)
        self.assertIsNotNone(self.history.product("store:coto:1"))
        self.assertEqual(crawl_step(self.history, store, now=self.now + timedelta(hours=1), fetch=page)["status"], "waiting")

    def test_large_vtex_range_is_split_and_continues_through_every_page(self):
        store = STORES_BY_KEY["carrefour"]
        state = _new_state(store, self.now)
        state["pending"] = [{"low": 1, "high": 1000, "offset": 0}]
        self.history.set_meta("supermarket_catalog_v1:carrefour", json.dumps(state))
        calls = []

        def page(_store, offset, low, high, limit):
            calls.append((offset, low, high))
            if len(calls) == 1:
                return {"count": 1, "total": 3, "offers": []}
            if len(calls) <= 3:
                return {"count": 1, "total": 2, "offers": [offer("carrefour", str(offset + 1))]}
            return {"count": 0, "total": 0, "offers": []}

        with patch("prices.catalog_crawl.VTEX_PARTITION_LIMIT", 2):
            self.assertEqual(crawl_step(self.history, store, now=self.now, fetch=page)["status"], "partitioned")
            self.assertEqual(crawl_step(self.history, store, now=self.now, fetch=page)["status"], "page")
            self.assertEqual(crawl_step(self.history, store, now=self.now, fetch=page)["status"], "page")
            result = crawl_step(self.history, store, now=self.now, fetch=page)
        self.assertEqual(result["status"], "complete")
        self.assertEqual([call[0] for call in calls], [0, 0, 1, 0])
        self.assertEqual(result["state"]["records"], 2)

    def test_empty_page_before_total_is_an_error_and_does_not_finish(self):
        store = STORES_BY_KEY["coto"]
        page = lambda *_args, **_kwargs: {"count": 0, "total": 100, "offers": []}
        with self.assertRaises(ValueError):
            crawl_step(self.history, store, now=self.now, fetch=page)
        state = json.loads(self.history.get_meta("supermarket_catalog_v1:coto"))
        self.assertEqual(state["offset"], 0)
        self.assertIsNone(state["completed_at"])

    def test_unpageable_price_does_not_block_other_partitions_or_claim_completion(self):
        store = STORES_BY_KEY["carrefour"]
        state = {"started_at": self.now.isoformat(), "completed_at": None, "pages": 0,
                 "records": 0, "saved_offers": 0, "unidentified_offers": 0, "last_error_at": None,
                 "pending": [{"low": 3, "high": 4, "offset": 0}, {"low": 1, "high": 1, "offset": 0}],
                 "blocked": []}
        self.history.set_meta("supermarket_catalog_v1:carrefour", json.dumps(state))
        def page(_store, offset, low, high, limit):
            return {"count": 1 if low == 1 else 0, "total": 3 if low == 1 else 0, "offers": []}
        with patch("prices.catalog_crawl.VTEX_PARTITION_LIMIT", 2):
            self.assertEqual(crawl_step(self.history, store, now=self.now, fetch=page)["status"], "deferred")
            result = crawl_step(self.history, store, now=self.now, fetch=page)
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["state"]["completed_at"])
        self.assertEqual(len(result["state"]["blocked"]), 1)

    def test_unstable_name_is_not_used_as_a_product_identity(self):
        self.assertEqual(group_key("Arroz", "Marca", "0000000000000", "coto", "123"), "store:coto:123")
        self.assertEqual(group_key("Arroz", "Marca", "7791234567890", "coto", "123"), "ean:7791234567890")

    def test_live_search_and_catalog_use_the_same_store_sku_identity(self):
        item = offer(source_id="123")
        page = lambda *_args, **_kwargs: {"count": 1, "total": 1, "offers": [item]}
        crawl_step(self.history, STORES_BY_KEY["coto"], now=self.now, fetch=page)
        with patch("prices.search._fetch_offers", return_value=([item], [])), patch("prices.search.apply_best_promo"):
            result = search_prices("arroz coto")
        key = result["groups"][0]["key"]
        self.assertEqual(key, "store:coto:123")
        self.assertIsNotNone(Catalog(self.history).product(key, today=self.now.date()))


class SourcePageTests(unittest.TestCase):
    def test_vtex_returns_every_sku_and_keeps_price_filter_encoding(self):
        item = lambda sku, ean: {"itemId": sku, "ean": ean, "nameComplete": "Producto " + sku,
                                 "sellers": [{"sellerDefault": True, "commertialOffer": {"Price": 100, "IsAvailable": True}}]}
        product = {"productName": "Producto", "link": "https://example.test/p", "items": [item("1", ""), item("2", "7791234567890")]}
        response = MagicMock(status_code=206, headers={"resources": "0-0/1"})
        response.json.return_value = [product]
        with patch.object(vtex.requests, "get", return_value=response) as get:
            result = vtex.catalog_page(STORES_BY_KEY["carrefour"], 0, 1, 100_000, limit=50)
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["offers"]), 2)
        self.assertEqual(result["offers"][0].source_id, "1")
        self.assertEqual(result["offers"][1].title, "Producto 2")
        self.assertIn("P:[0.01%20TO%201000.00]", get.call_args.args[0])
        with patch.object(vtex.requests, "get", return_value=response):
            with self.assertRaises(ValueError):
                vtex.catalog_page(STORES_BY_KEY["carrefour"], 50, 1, 100_000, limit=50)

    def test_coto_checks_offset_and_uses_page_total(self):
        results = {"@type": "Category_ResultsList", "totalNumRecs": 20, "firstRecNum": 6, "records": [
            {"records": [{"attributes": {"record.id": ["abc-200"], "product.displayName": ["Arroz"], "sku.activePrice": ["100"]}}]}]}
        response = MagicMock(status_code=200)
        response.json.return_value = {"contents": [results]}
        with patch.object(coto.requests, "get", return_value=response) as get:
            result = coto.catalog_page(STORES_BY_KEY["coto"], 5, limit=5)
            self.assertEqual(result["total"], 20)
            self.assertEqual(result["offers"][0].source_id, "abc-200")
            self.assertEqual(get.call_args.kwargs["params"]["No"], 5)
            with self.assertRaises(ValueError):
                coto.catalog_page(STORES_BY_KEY["coto"], 10, limit=5)


if __name__ == "__main__":
    unittest.main()
