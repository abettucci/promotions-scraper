import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import Database, UserDatabase
from promotion_history import capture_promotion, bootstrap_history
from purchases import PurchaseBody, PurchaseStore

DAY = date(2026, 10, 26)  # lunes


def body(**changes):
    return PurchaseBody.model_validate({"request_id": str(uuid4()), "purchased_on": DAY.isoformat(),
        "merchant": "Coto Digital", "amount": "1000.50", **changes})


class PurchaseFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name)/"promos.db")
        self.users = UserDatabase(Path(self.tmp.name)/"users.db")
        self.uid = self.users.create_user("purchase1@example.test", "test-hash")
        self.other = self.users.create_user("purchase2@example.test", "test-hash")
        self.store = PurchaseStore(self.users)
        self.sid = self.db.insert_supermarket("Coto Digital", "https://example.test")
        self.clock = patch("purchases.today", return_value=date(2026, 11, 30))
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.tmp.cleanup()

    def promo(self, day=DAY, evidence="scrape", **changes):
        value = {"title": "Banco Galicia 30%", "bank": "Banco Galicia", "discount": "30%",
            "valid_from": "2026-10-01", "valid_until": "2026-10-31", "valid_days": "Lunes",
            "store_types": "Online", "card_type": "Crédito", "source": "coto", **changes}
        identifier = self.db.insert_promotion(self.sid, value)
        self.assertIsNotNone(identifier)
        self.observe(identifier, day, evidence)
        return identifier

    def observe(self, identifier, day=DAY, evidence="scrape"):
        conn = self.db.get_connection()
        try:
            capture_promotion(conn, identifier, observed_at=datetime.combine(day, datetime.min.time(), timezone.utc).replace(hour=12), provenance=evidence)
            conn.commit()
        finally:
            conn.close()

    def report(self):
        self.store.sync(self.db.db_path)
        return self.store.report(self.uid, DAY, DAY)


class HistoryTests(PurchaseFixture):
    def test_past_percentage_survives_update_of_current_promo(self):
        first = self.promo()
        second = self.promo(day=date(2026, 10, 27), discount="20%")
        self.assertEqual(first, second)
        self.store.create(self.uid, body())
        data = self.report()
        self.assertEqual(data["summary"]["promo_day_count"], 1)
        self.assertEqual(data["purchases"][0]["promotions"][0]["percentage"], 30)

    def test_unchanged_snapshots_do_not_duplicate_versions_or_daily_observations(self):
        identifier = self.promo()
        with self.db.get_connection() as conn:
            before = conn.execute("SELECT COUNT(*) FROM promotion_versions").fetchone()[0]
            capture_promotion(conn, identifier, observed_at=datetime(2026, 10, 26, 13, tzinfo=timezone.utc))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM promotion_versions").fetchone()[0], before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM promotion_observations WHERE observed_on=?", (DAY.isoformat(),)).fetchone()[0], 1)

    def test_persistent_copy_survives_replacement_of_promotions_database(self):
        self.promo()
        self.store.create(self.uid, body())
        self.store.sync(self.db.db_path)
        replacement = Database(Path(self.tmp.name)/"replacement.db")
        self.store.sync(replacement.db_path)
        self.assertEqual(self.store.report(self.uid, DAY, DAY)["summary"]["promo_day_count"], 1)

    def test_legacy_snapshot_is_not_verified_history_or_zero_discount(self):
        self.promo(evidence="legacy")
        self.store.create(self.uid, body())
        result = self.report()
        self.assertEqual(result["summary"]["with_history_count"], 0)
        self.assertIsNone(result["summary"]["promo_day_share_pct"])
        self.assertEqual(result["purchases"][0]["promotions"][0]["evidence"], "legacy")

    def test_bootstrap_does_not_create_observations_for_unseen_days(self):
        identifier = self.promo(day=date(2026, 10, 25))
        with self.db.get_connection() as conn:
            conn.execute("UPDATE promotions SET scraped_at='2026-10-25 12:00:00' WHERE id=?", (identifier,))
            bootstrap_history(conn)
        self.store.create(self.uid, body())
        self.assertEqual(self.report()["summary"]["without_history_count"], 1)

    def test_cache_verified_source_adds_daily_evidence_without_rewriting_promo(self):
        identifier = self.promo()
        self.db.observe_verified_source(self.sid, "coto")
        with self.db.get_connection() as conn:
            latest = conn.execute("SELECT MAX(observed_on) FROM promotion_observations WHERE provenance='scrape'").fetchone()[0]
        self.assertIsNotNone(latest)
        self.assertIsNotNone(identifier)

    def test_upsert_does_not_mix_previous_terms_with_new_promo(self):
        identifier = self.promo()
        self.db.insert_terms(identifier, {"max_discount": "$100", "exclusions": ["vinos"]})
        self.db.insert_promotion(self.sid, {"title": "Banco Galicia 30%", "bank": "Banco Galicia", "tope": "$500"})
        with self.db.get_connection() as conn:
            import json
            data = json.loads(conn.execute("SELECT payload FROM promotion_observations o JOIN promotion_versions v ON v.revision=o.revision ORDER BY observed_at DESC LIMIT 1").fetchone()[0])
        self.assertEqual(data["tope"], "$500")
        self.assertEqual(data["exclusions"], [])

    def test_external_hydration_retains_original_date_and_is_not_a_fresh_scrape(self):
        from external_sources import ExternalSourcesRunner
        promo = {"merchant_brands": ["Coto Digital"], "title": "Restaurada", "discount": "30%",
                 "bank": "Banco Galicia", "valid_from": "2026-10-01", "valid_until": "2026-10-31", "valid_days": "Lunes"}
        snapshot = {"sources": {"santander": {"updated_at": "2026-10-26T12:00:00+00:00", "promotions": [promo]}}}
        with patch("external_sources._read_json", return_value=snapshot):
            ExternalSourcesRunner(self.db).hydrate()
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT observed_on,provenance FROM promotion_observations").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("2026-10-26", "legacy")])

    def test_utc_observation_is_assigned_to_argentina_calendar_day(self):
        identifier = self.promo()
        with self.db.get_connection() as conn:
            capture_promotion(conn, identifier, observed_at=datetime(2026, 10, 27, 1, tzinfo=timezone.utc))
            conn.commit()
            row = conn.execute("SELECT observed_on FROM promotion_observations WHERE observed_at=?",
                               ("2026-10-27T01:00:00+00:00",)).fetchone()
        self.assertEqual(row[0], "2026-10-26")

    def test_later_legacy_hydration_cannot_downgrade_a_real_observation(self):
        identifier = self.promo()
        with self.db.get_connection() as conn:
            capture_promotion(conn, identifier, observed_at=datetime(2026, 10, 26, 14, tzinfo=timezone.utc), provenance="legacy")
            conn.commit()
            row = conn.execute("SELECT provenance FROM promotion_observations WHERE observed_on='2026-10-26'").fetchone()
        self.assertEqual(row[0], "scrape")
        self.store.create(self.uid, body())
        self.assertEqual(self.report()["summary"]["promo_day_count"], 1)


class MetricsTests(PurchaseFixture):
    def test_percent_on_purchase_day_is_not_an_actual_saving(self):
        self.promo()
        self.store.create(self.uid, body())
        result = self.report()
        self.assertEqual(result["summary"]["promo_day_share_pct"], 100)
        self.assertEqual(result["summary"]["declared_savings"], 0)
        self.assertIsNone(result["summary"]["declared_effective_pct"])
        self.assertEqual(result["summary"]["possible_payment_count"], 0)

    def test_wrong_weekday_and_expired_campaign_are_not_matched(self):
        self.promo(valid_days="Martes")
        self.promo(title="Otra", valid_until="2026-10-25")
        self.store.create(self.uid, body())
        self.assertEqual(self.report()["summary"]["promo_day_count"], 0)

    def test_unknown_validity_does_not_turn_into_known_zero(self):
        self.promo(valid_from="", valid_until="")
        self.store.create(self.uid, body())
        result = self.report()
        self.assertEqual(result["summary"]["without_history_count"], 1)
        self.assertIsNone(result["summary"]["promo_day_share_pct"])

    def test_missing_days_are_excluded_from_denominator(self):
        self.promo()
        self.store.create(self.uid, body())
        self.store.create(self.uid, body(purchased_on="2026-10-25"))
        self.store.sync(self.db.db_path)
        report = self.store.report(self.uid, date(2026, 10, 25), DAY)
        self.assertEqual(report["summary"]["purchase_count"], 2)
        self.assertEqual(report["summary"]["with_history_count"], 1)
        self.assertEqual(report["summary"]["promo_day_share_pct"], 100)

    def test_multiple_promos_count_one_purchase_without_picking_highest_percentage(self):
        self.promo()
        self.promo(title="Otra", discount="20%")
        self.store.create(self.uid, body())
        result = self.report()
        self.assertEqual(result["summary"]["promo_day_count"], 1)
        self.assertEqual(result["summary"]["by_published_percentage"], [{"label": "Varios porcentajes", "purchases": 1}])

    def test_installments_are_not_a_percentage_and_decimal_rate_is_preserved(self):
        self.promo(discount="3 cuotas sin interés")
        self.promo(title="Otra", discount="12,5%")
        self.store.create(self.uid, body())
        self.assertEqual(self.report()["summary"]["by_published_percentage"], [{"label": "12.5%", "purchases": 1}])

    def test_received_savings_use_cents_and_zero_is_distinct_from_missing(self):
        self.store.create(self.uid, body(amount="100.01", received_discount="12.50"))
        self.store.create(self.uid, body(amount="100.00", received_discount="0"))
        self.store.create(self.uid, body(amount="5000.00"))
        summary = self.report()["summary"]
        self.assertEqual(summary["declared_savings"], 12.5)
        self.assertEqual(summary["declared_savings_count"], 2)
        self.assertEqual(summary["declared_effective_pct"], 6.25)

    def test_up_to_rate_remains_a_maximum_not_a_guaranteed_percentage(self):
        self.promo(discount="Hasta 30%")
        self.store.create(self.uid, body())
        self.assertEqual(self.report()["summary"]["by_published_percentage"], [{"label": "Hasta 30%", "purchases": 1}])

    def test_payment_and_channel_do_not_assume_current_profile(self):
        self.promo()
        self.store.create(self.uid, body(bank="Banco Galicia", card_type="credit", modality="online"))
        self.store.create(self.uid, body(bank="Santander", card_type="credit", modality="online"))
        self.store.create(self.uid, body(bank="Banco Galicia", card_type="debit", modality="online"))
        self.store.create(self.uid, body(bank="Banco Galicia", card_type="credit", modality="in_store"))
        self.assertEqual(self.report()["summary"]["possible_payment_count"], 1)

    def test_idempotency_and_ownership(self):
        purchase = body()
        first = self.store.create(self.uid, purchase)
        self.assertEqual(self.store.create(self.uid, purchase)["id"], first["id"])
        with self.assertRaisesRegex(ValueError, "idempotency"):
            self.store.create(self.uid, body(request_id=str(purchase.request_id), amount="1"))
        self.assertFalse(self.store.delete(self.other, first["id"]))
        self.assertEqual(self.store.report(self.other, DAY, DAY)["total"], 0)
        self.assertTrue(self.store.delete(self.uid, first["id"]))


class PurchaseApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import config
        cls.tmp = tempfile.TemporaryDirectory()
        cls.config_patch = patch.multiple(config, DATABASE_PATH=Path(cls.tmp.name)/"promos.db",
            USERS_DB_PATH=Path(cls.tmp.name)/"users.db", PRICES_DB_PATH=Path(cls.tmp.name)/"prices.db",
            EXTERNAL_SOURCES_SNAPSHOT_PATH=Path(cls.tmp.name)/"missing.json")
        cls.config_patch.start()
        cls.env_patch = patch.dict(os.environ, {"ENABLE_SCRAPER":"false", "ENABLE_PRICES_JOB":"false", "ENABLE_EXTERNAL_SOURCES_JOB":"false"})
        cls.env_patch.start()
        import api
        from fastapi.testclient import TestClient
        cls.api = api
        cls.db = Database(config.DATABASE_PATH)
        cls.db.insert_supermarket("Coto Digital", "https://example.test")
        cls.users = UserDatabase(config.USERS_DB_PATH)
        cls.uid = cls.users.create_user("purchase-api@example.test", "test-hash")
        cls.other = cls.users.create_user("purchase-api-other@example.test", "test-hash")
        cls.db_patch = patch.object(api, "_db", cls.users)
        cls.db_patch.start()
        cls.client = TestClient(api.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close(); cls.db_patch.stop(); cls.config_patch.stop(); cls.env_patch.stop(); cls.tmp.cleanup()

    def setUp(self):
        self.previous = self.api.app.dependency_overrides.copy()
        self.api.app.dependency_overrides[self.api.get_current_user] = lambda: {"id": self.uid}

    def tearDown(self):
        self.api.app.dependency_overrides.clear(); self.api.app.dependency_overrides.update(self.previous)

    def payload(self, **changes):
        return {"request_id": str(uuid4()), "purchased_on": DAY.isoformat(), "merchant": "Coto Digital", "amount":"100.01", **changes}

    def test_anonymous_cannot_use_any_purchase_route(self):
        self.api.app.dependency_overrides.pop(self.api.get_current_user)
        for method, route in (("GET", "/api/auth/me/purchases"), ("GET", "/api/auth/me/purchases/options"),
                ("POST", "/api/auth/me/purchases"), ("POST", "/api/auth/me/purchases/refresh-history"),
                ("DELETE", "/api/auth/me/purchases/"+str(uuid4()))):
            self.assertNotEqual(self.client.request(method, route, json=self.payload() if method == "POST" else None).status_code, 200)

    def test_validation_rejects_owner_spoofing_and_invalid_financial_inputs(self):
        for changes in ({"user_id":self.other}, {"amount":True}, {"amount":"NaN"}, {"amount":"Infinity"},
                {"amount":"0"}, {"amount":"-1"}, {"amount":"1.001"}, {"amount":"1000000001"},
                {"received_discount":"100.02"}, {"purchased_on":"2026-02-30"}, {"purchased_on":"2099-01-01"},
                {"request_id":"not-uuid"}, {"merchant":"' OR 1=1 --"}, {"bank":"person@example.test"}):
            response = self.client.post("/api/auth/me/purchases", json=self.payload(**changes))
            self.assertEqual(response.status_code, 422, changes)

    def test_manual_flow_is_private_idempotent_and_get_does_not_sync_or_scrape(self):
        payload = self.payload()
        response = self.client.post("/api/auth/me/purchases", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.post("/api/auth/me/purchases", json=payload).json(), response.json())
        with patch("purchases.merge_history", side_effect=AssertionError("GET mutated history")):
            result = self.client.get("/api/auth/me/purchases?date_from=2026-10-01&date_to=2026-10-31")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotIn("user_id", result.text)
        self.assertNotIn("request_id", result.text)
        self.api.app.dependency_overrides[self.api.get_current_user] = lambda: {"id": self.other}
        self.assertEqual(self.client.delete("/api/auth/me/purchases/"+response.json()["id"]).status_code, 404)
        self.assertEqual(self.client.get("/api/auth/me/purchases?date_from=2026-10-01&date_to=2026-10-31").json()["total"], 0)

    def test_limits_errors_and_date_bounds(self):
        for suffix in ("?page=0", "?page_size=101", "?date_from=2000-01-01&date_to=2026-01-01", "?date_from=2026-10-31&date_to=2026-10-01"):
            self.assertEqual(self.client.get("/api/auth/me/purchases"+suffix).status_code, 422)
        with patch.object(self.users, "consume_public_assistant_quota", return_value=3600):
            self.assertEqual(self.client.post("/api/auth/me/purchases", json=self.payload()).status_code, 429)
        with patch("purchases.PurchaseStore.report", side_effect=sqlite3.OperationalError("secret-db-location")):
            response = self.client.get("/api/auth/me/purchases")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("secret-db-location", response.text)


if __name__ == "__main__":
    unittest.main()
