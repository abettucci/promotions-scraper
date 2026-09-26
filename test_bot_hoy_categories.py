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


if __name__ == "__main__":
    unittest.main()
