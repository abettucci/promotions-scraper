import unittest
from unittest.mock import patch

from promo_questions import answer_promo_question, is_allowed_promo_question
from supplement_prices import SupplementPrice, _find_product_page, _parse_product_page


SEARCH_HTML = """
<a href="/p/star-nutrition-plant-protein-2-lb"><span class="card__name">Star Nutrition Plant Protein 2 lb</span></a>
<a href="/p/star-nutrition-proteina-2-lb-907-g"><span class="card__name">Star Nutrition Proteína 2 lb (907 g)</span></a>
"""

PRODUCT_HTML = """
<script type="application/ld+json">{"@type":"Product","name":"Star Nutrition Proteína 2 lb (907 g)","offers":{"offerCount":"7","lowPrice":"75000"}}</script>
<article class="offer--best"><span class="offer__store">Suplemed</span><span class="offer__price">$75.000</span><span class="offer__transfer">$71.250 con transferencia</span></article>
"""


class SupplementPriceTests(unittest.TestCase):
    def test_search_prefers_requested_standard_product_over_plant_variant(self):
        url = _find_product_page(SEARCH_HTML, "protein star nutrition 2 lb doypack")
        self.assertEqual(url, "https://www.supleradar.com.ar/p/star-nutrition-proteina-2-lb-907-g")

    def test_parses_best_store_and_structured_price(self):
        result = _parse_product_page(PRODUCT_HTML, "https://www.supleradar.com.ar/p/star-nutrition-proteina-2-lb-907-g")
        self.assertEqual(result.store_name, "Suplemed")
        self.assertEqual(result.price, 75000)
        self.assertEqual(result.transfer_price, 71250)
        self.assertEqual(result.offer_count, 7)

    @patch("promo_questions.find_supplement_price")
    def test_answers_the_telegram_price_question_with_verifiable_result(self, lookup):
        lookup.return_value = SupplementPrice(
            product_name="Star Nutrition Proteína 2 lb (907 g)", store_name="Suplemed",
            price=75000, transfer_price=71250, offer_count=7,
            source_url="https://www.supleradar.com.ar/p/star-nutrition-proteina-2-lb-907-g",
        )
        answer = answer_promo_question("En que lugar esta mas barata la protein star nutrition 2 lb doypack?", [])
        self.assertIn("Suplemed", answer)
        self.assertIn("$75.000", answer)
        self.assertIn("Ver comparación", answer)
        self.assertTrue(is_allowed_promo_question("En que lugar esta mas barata la protein star nutrition 2 lb doypack?"))

    def test_non_supplement_price_questions_use_the_store_comparator(self):
        result = {"groups": [{"name": "Yerba Playadito 1 kg", "store_count": 2, "offers": [
            {"store_name": "Día", "price": 5000, "final_price": 4000, "savings": 1000, "url": "https://x/p",
             "promo": {"discount": "20% reintegro", "entity": "MODO", "requires_min_purchase": False,
                       "min_purchase": None}},
            {"store_name": "Jumbo", "price": 5200, "final_price": 5200, "savings": 0, "url": "https://y/p", "promo": None},
        ]}]}
        with patch("prices.search_prices", return_value=result) as search:
            answer = answer_promo_question("¿En qué lugar está más barata la yerba playadito?", [])
        search.assert_called_once()
        self.assertIn("Yerba Playadito", answer)
        self.assertIn("Hoy conviene <b>Día</b>", answer)


if __name__ == "__main__":
    unittest.main()
