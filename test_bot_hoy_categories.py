import sys
import types
import unittest
from unittest.mock import patch

# notifier importa requests, que no hace falta para estos handlers unitarios.
sys.modules.setdefault("requests", types.ModuleType("requests"))

import bot_handlers


class DummyNotifier:
    def __init__(self):
        self.sent = []
        self.edited = []
        self.answered = []

    def send_message_to(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))

    def edit_message_text(self, chat_id, message_id, text, **kwargs):
        self.edited.append((chat_id, message_id, text, kwargs))

    def answer_callback_query(self, callback_id, text=""):
        self.answered.append((callback_id, text))


class DummyUserDb:
    def get_user_by_telegram_chat_id(self, chat_id):
        return {"id": 7, "notify_daily": False, "notify_hour": 9}

    def get_user_payment_methods(self, user_id):
        return [{"name": "Banco Credicoop", "type": "bank"}]


class BotHoyCategoriesTests(unittest.TestCase):
    def test_hoy_shows_a_category_selector_without_querying_promotions(self):
        notifier = DummyNotifier()
        with patch.object(bot_handlers, "_query_promotions") as query:
            bot_handlers.handle_message(
                {"message": {"chat": {"id": 123}, "text": "/hoy"}},
                user_db=object(),
                notifier=notifier,
            )

        self.assertFalse(query.called)
        self.assertEqual(len(notifier.sent), 1)
        markup = notifier.sent[0][2]["reply_markup"]
        buttons = markup["inline_keyboard"][0]
        self.assertEqual(buttons[0]["callback_data"], "hoycat:supermarket")
        self.assertEqual(buttons[1]["callback_data"], "hoycat:fuel")

    def test_category_callback_queries_only_the_selected_category(self):
        notifier = DummyNotifier()
        promo = {
            "supermarket_name": "YPF", "discount": "15%", "bank": "Banco Galicia",
            "wallet": None, "valid_days": "Viernes", "store_types": "Estaciones",
        }
        update = {
            "callback_query": {
                "id": "callback-1",
                "data": "hoycat:fuel",
                "message": {"chat": {"id": 123}, "message_id": 456},
            }
        }

        with patch.object(bot_handlers, "_query_promotions", return_value=[promo]) as query:
            bot_handlers.handle_callback_query(update, user_db=object(), notifier=notifier)

        self.assertEqual(query.call_args.kwargs, {"today_only": True, "category": "fuel"})
        self.assertEqual(len(notifier.edited), 1)
        self.assertIn("Promos de combustible", notifier.edited[0][2])
        self.assertEqual(notifier.answered, [("callback-1", "")])

    def test_category_pagination_keeps_the_category_filter(self):
        notifier = DummyNotifier()
        update = {
            "callback_query": {
                "id": "callback-2",
                "data": "hoysuper:2",
                "message": {"chat": {"id": 123}, "message_id": 456},
            }
        }

        with patch.object(bot_handlers, "_query_promotions", return_value=[]) as query:
            bot_handlers.handle_callback_query(update, user_db=object(), notifier=notifier)

        self.assertEqual(query.call_args.kwargs, {"today_only": True, "category": "supermarket"})
        self.assertEqual(notifier.answered, [("callback-2", "")])

    def test_mis_starts_with_the_same_category_selector(self):
        notifier = DummyNotifier()
        with patch.object(bot_handlers, "_query_promotions") as query:
            bot_handlers.handle_message(
                {"message": {"chat": {"id": 123}, "text": "/mis"}},
                user_db=DummyUserDb(),
                notifier=notifier,
            )

        self.assertFalse(query.called)
        markup = notifier.sent[0][2]["reply_markup"]
        self.assertEqual(markup["inline_keyboard"][0][0]["callback_data"], "miscat:supermarket")
        self.assertEqual(markup["inline_keyboard"][0][1]["callback_data"], "miscat:fuel")

    def test_mis_filter_uses_linked_methods_and_selected_filter(self):
        notifier = DummyNotifier()
        update = {
            "callback_query": {
                "id": "callback-filter",
                "data": "a:m:s:m:o",
                "message": {"chat": {"id": 123}, "message_id": 456},
            }
        }
        with patch.object(bot_handlers, "_query_promotions", return_value=[]) as query:
            bot_handlers.handle_callback_query(update, user_db=DummyUserDb(), notifier=notifier)

        self.assertEqual(query.call_args.kwargs, {
            "today_only": True,
            "category": "supermarket",
            "modality_filter": "online",
            "payment_methods": [{"name": "Banco Credicoop", "type": "bank"}],
        })
        self.assertIn("Filtro: Online", notifier.edited[0][2])

    def test_rendered_promo_calls_out_modality_and_exclusions_once(self):
        message = bot_handlers._format_promo_html({
            "discount": "30%", "bank": "Banco Credicoop", "store_types": "Online",
            "exclusions": "Aplican exclusiones", "valid_days": "Sábado",
        })
        self.assertEqual(message.count("🏪 Online"), 1)
        self.assertIn("Aplican exclusiones", message)

    def test_conditions_buttons_identify_the_promotion_not_only_the_wallet(self):
        markup = bot_handlers._results_markup([
            {"id": 10, "supermarket_name": "Coto Digital", "bank": "Mercado Pago"},
            {"id": 11, "supermarket_name": "Supermercados Día", "discount": "15%", "bank": "Mercado Pago"},
        ], "hoysuper", 1, 1, "h", "s")

        labels = [row[0]["text"] for row in markup["inline_keyboard"][:-1]]
        self.assertEqual(labels, [
            "📋 Coto Digital · Mercado Pago",
            "📋 Supermercados Día · 15% · Mercado Pago",
        ])

    def test_conditions_render_json_exclusions_as_readable_text(self):
        text = bot_handlers._format_conditions_html({
            "supermarket_name": "Coto Digital",
            "title": "Mercado Pago",
            "terms_exclusions": '["No incluye vinos", "No acumulable con otras ofertas"]',
            "terms_requirements": '[]',
        })

        self.assertIn("No incluye vinos", text)
        self.assertNotIn('["No incluye vinos"', text)

    def test_conditions_message_prioritizes_exclusions_without_exceeding_telegram_limit(self):
        text = bot_handlers._format_conditions_html({
            "supermarket_name": "Más Online", "title": "MásClub",
            "terms_exclusions": '["' + ("productos excluidos " * 500) + '"]',
            "raw_text": "legal " * 900,
        })

        self.assertIn("Exclusiones:", text)
        self.assertLess(len(text), 3900)

    def test_payment_menu_offers_promotions_without_declared_payment_rail(self):
        _, markup = bot_handlers._filter_options("m", "s", "p")
        labels = [row[0]["text"] for row in markup["inline_keyboard"]]
        self.assertIn("❔ No informado", labels)


if __name__ == "__main__":
    unittest.main()
