import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from database import UserDatabase
from prices.alerts import check_alerts, create_alert, parse_alert_args
from prices.basket import due, load_basket, run_basket
from prices.history import PriceHistory


def group(key, price, store="dia", in_stock=True, name="Leche 1L"):
    return {"key": key, "name": name, "brand": "X", "ean": key.split(":")[-1], "image": "",
            "offers": [{"store": store, "store_name": store.title(), "price": price, "list_price": None,
                        "url": f"https://{store}.test/p", "in_stock": in_stock}]}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = PriceHistory(Path(self.tmp.name) / "prices.db")
        self.day = date(2026, 10, 1)

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_changes_and_heartbeats_are_recorded(self):
        record = lambda price, offset: self.history.record_groups(
            [group("ean:1", price)], "leche", self.day + timedelta(days=offset))
        self.assertEqual(record(100, 0), 1)
        self.assertEqual(record(100, 1), 0)      # mismo precio
        self.assertEqual(record(90, 2), 1)       # cambió
        self.assertEqual(record(90, 9), 1)       # latido a los 7 días
        self.assertEqual(record(90, 10), 0)

    def test_title_keys_and_out_of_stock_are_ignored(self):
        self.assertEqual(self.history.record_groups([group("title:leche sancor:1l", 100)], "q", self.day), 0)
        self.assertEqual(self.history.record_groups([group("ean:2", 100, in_stock=False)], "q", self.day), 0)

    def test_series_carries_prices_forward_and_drops_stale_stores(self):
        self.history.record_groups([group("ean:1", 100, "dia")], "q", self.day)
        self.history.record_groups([group("ean:1", 120, "jumbo")], "q", self.day + timedelta(days=1))
        series = self.history.series("ean:1", days=30, today=self.day + timedelta(days=3))
        by_date = {p["date"]: p for p in series["points"]}
        self.assertEqual(by_date["2026-10-02"]["min"], 100)
        self.assertEqual(by_date["2026-10-02"]["max"], 120)
        self.assertEqual(by_date["2026-10-02"]["stores"], 2)
        # Sin latidos, a los 12 días las tiendas ya no cuentan.
        late = self.history.series("ean:1", days=30, today=self.day + timedelta(days=12))
        self.assertEqual(late["current"], [])
        self.assertEqual(series["summary"]["lowest"], 100)

    def test_series_current_prices_are_sorted(self):
        self.history.record_groups([group("ean:1", 130, "jumbo"), group("ean:1", 100, "dia")], "q", self.day)
        series = self.history.series("ean:1", today=self.day)
        self.assertEqual(series["current"][0]["store"], "dia")


class BasketTests(unittest.TestCase):
    def test_basket_file_is_valid(self):
        basket = load_basket()
        self.assertGreater(len(basket), 50)
        self.assertTrue(all(e["query"] and e["category"] in {"supermarket", "electro"} for e in basket))

    def test_run_basket_records_and_survives_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = PriceHistory(Path(tmp) / "p.db")

            def fake_search(query, category=None, max_groups=3):
                if query == "falla":
                    raise RuntimeError("boom")
                return {"groups": [group("ean:9", 50)] if query == "ok" else []}

            stats = run_basket(history, basket=[{"query": "ok", "category": "supermarket"},
                                                {"query": "falla", "category": "supermarket"},
                                                {"query": "nada", "category": "electro"}],
                               pause=0, search=fake_search, log=lambda _: None, today=date(2026, 10, 1))
            self.assertEqual((stats["errors"], stats["empty"], stats["rows"], stats["products"]), (1, 1, 1, 1))
            self.assertFalse(due(history, 20))
            self.assertTrue(due(history, 20, now=datetime.now() + timedelta(hours=21)))


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = UserDatabase(Path(self.tmp.name) / "users.db")
        self.user = self.db.create_user("a@b.com", "hash")
        self.db.update_user_telegram(self.user, "555", notify_daily=True, notify_hour=9)
        self.sent = []

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))
        return True

    def search_for(self, price):
        return lambda query, max_groups=5, category=None: {"groups": [group("ean:1", price)]}

    def test_parse_alert_args(self):
        self.assertEqual(parse_alert_args("leche la serenisima 1l"), ("leche la serenisima 1l", None))
        self.assertEqual(parse_alert_args("heladera samsung a $1.000.000"), ("heladera samsung", 1000000.0))
        self.assertEqual(parse_alert_args("tv 50 menos de $700000"), ("tv 50", 700000.0))
        self.assertEqual(parse_alert_args("tv 50 $700.000,50")[1], 700000.5)

    def test_create_alert_and_limit(self):
        alert = create_alert(self.db, self.user, "leche", search=self.search_for(100))
        self.assertEqual((alert["key"], alert["price"]), ("ean:1", 100))
        self.assertIsNone(create_alert(self.db, self.user, "x", search=lambda *a, **k: {"groups": []}))
        self.db.MAX_PRICE_ALERTS_PER_USER = 1
        other = lambda *a, **k: {"groups": [group("ean:2", 5)]}
        self.assertEqual(create_alert(self.db, self.user, "otro", search=other), {"error": "limit"})

    def test_any_drop_notifies_once_then_tracks_the_new_price(self):
        create_alert(self.db, self.user, "leche", search=self.search_for(100))
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(100))["notified"], 0)
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(90))["notified"], 1)
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(90))["notified"], 0)
        self.assertIn("Bajó el precio", self.sent[0][1])
        self.assertIn("$90", self.sent[0][1])
        self.assertIn("antes $100", self.sent[0][1])

    def test_ignores_drops_under_one_percent(self):
        create_alert(self.db, self.user, "leche", search=self.search_for(1000))
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(995))["notified"], 0)

    def test_target_price_notifies_on_reaching_it_and_rearms(self):
        create_alert(self.db, self.user, "leche", target=80, search=self.search_for(100))
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(90))["notified"], 0)
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(79))["notified"], 1)
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(79))["notified"], 0)
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(95))["notified"], 0)  # rearma
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(79))["notified"], 1)
        self.assertIn("Llegó a tu precio", self.sent[0][1])

    def test_product_gone_is_reported_and_users_without_telegram_are_skipped(self):
        create_alert(self.db, self.user, "leche", search=self.search_for(100))
        gone = lambda *a, **k: {"groups": []}
        self.assertEqual(check_alerts(self.db, self.send, search=gone)["missing"], 1)
        silent = self.db.create_user("c@d.com", "hash")
        create_alert(self.db, silent, "leche", search=self.search_for(100))
        self.assertEqual(check_alerts(self.db, self.send, search=self.search_for(50))["checked"], 1)

    def test_alerts_are_scoped_to_their_owner(self):
        alert = create_alert(self.db, self.user, "leche", search=self.search_for(100))
        other = self.db.create_user("c@d.com", "hash")
        self.assertFalse(self.db.delete_price_alert(other, alert["id"]))
        self.assertTrue(self.db.delete_price_alert(self.user, alert["id"]))

    def test_message_does_not_alter_commas_in_names_or_urls(self):
        from prices.alerts import _message
        text = _message({"product_name": "Aceite, girasol", "target_price": None},
                        {"store_name": "Día", "price": 1234.6, "url": "https://x/a,b"}, 2000, False)
        self.assertIn("Aceite, girasol", text)
        self.assertIn("a,b", text)
        self.assertIn("$1.235", text)


class BotAlertCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = UserDatabase(Path(self.tmp.name) / "users.db")
        uid = self.db.create_user("a@b.com", "hash")
        self.db.update_user_telegram(uid, "555", notify_daily=True, notify_hour=9)

    def tearDown(self):
        self.tmp.cleanup()

    def test_requires_a_linked_account(self):
        from bot_handlers import cmd_alerta
        self.assertIn("Linkea", cmd_alerta("999", "leche", self.db)[0])

    def test_create_list_and_remove(self):
        from bot_handlers import cmd_alerta, cmd_alertas, cmd_quitar
        created = {"id": 1, "key": "ean:1", "name": "Leche 1L", "price": 100, "store_name": "Día", "target": 80}
        with patch("prices.alerts.create_alert", return_value=created) as create:
            text, _ = cmd_alerta("555", "leche la serenisima 1l a $80", self.db)
        self.assertEqual(create.call_args.kwargs["target"], 80)
        self.assertIn("Alerta #1", text)
        self.assertIn("/alerta leche", cmd_alerta("555", "", self.db)[0])   # sin producto: muestra el uso
        self.db.add_price_alert(1, "ean:1", "Leche 1L", "leche", 100, 80)
        self.assertIn("Leche 1L", cmd_alertas("555", "", self.db)[0])
        self.assertIn("borrada", cmd_quitar("555", "1", self.db)[0])
        self.assertIn("No tenés alertas", cmd_alertas("555", "", self.db)[0])


if __name__ == "__main__":
    unittest.main()
