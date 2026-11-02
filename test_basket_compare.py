import unittest
from datetime import date

from prices.basket_compare import compare_basket, amount

TODAY = date(2026, 11, 2)  # lunes
METHODS = [{"name": "Banco Uno", "type": "bank", "card_mode": "credit", "tiers": []}]


def product(key, price, store="coto", name="Leche X 1 L", path=None, **extra):
    from prices.registry import STORES
    source = next(s for s in STORES if s.key == store)
    return {"product_key": key, "product_name": name, "category_path": path or ["Lácteos", "Leches"],
            "offers": [{"store": store, "price": price, "merchant": source.merchant, **extra}]}


def promotion(**changes):
    return {"id": 1, "title": "Banco Uno 30%", "discount": "30%", "bank": "Banco Uno",
            "store_types": "Online", "card_type": "Crédito", "tope": "$50", "valid_days": "Todos los días",
            "valid_from": "2026-11-01", "valid_until": "2026-11-30", "supermarket_name": "Coto Digital", **changes}


def report(products, promos=None, methods=None, **kwargs):
    return compare_basket(products, promos if promos is not None else [promotion()],
                          methods if methods is not None else METHODS, today=TODAY, **kwargs)


class BasketTests(unittest.TestCase):
    def test_shared_cap_applies_once_to_whole_ticket(self):
        row = report([product("a", 100), product("b", 100)])["reference"]
        self.assertEqual(row["subtotal"], 200)
        self.assertEqual(row["savings"], 50)
        self.assertEqual(row["total"], 150)

    def test_minimum_is_enforced_and_counts_eligible_amount(self):
        for promos in ([promotion(min_purchase="$300")], [promotion(min_purchase="$.")],
                       [promotion(min_purchase="Sin mínimo informado")],
                       [promotion(requirements=["Mínimo de $300"])],
                       [promotion(terms_raw="Compra mínima de $ 300")]):
            self.assertEqual(report([product("a", 100)], promos)["reference"]["savings"], 0)
        row = report([product("a", 100), product("b", 100)], [promotion(min_purchase="$200")])["reference"]
        self.assertEqual(row["savings"], 50)

    def test_unknown_cap_is_not_unlimited_and_decimal_percent_is_preserved(self):
        self.assertEqual(report([product("a", 100)], [promotion(tope="Sin tope informado")])["reference"]["savings"], 0)
        self.assertEqual(report([product("a", 100)], [promotion(tope="Sin tope", discount="12,5%")])["reference"]["savings"], 12.5)
        self.assertEqual(amount("$100 mil"), 100000)

    def test_does_not_apply_physical_or_expired_promos_to_online_quotes(self):
        for promo in (promotion(store_types="Tiendas"), promotion(valid_until="2026-11-01"), promotion(store_types="")):
            self.assertEqual(report([product("a", 100)], [promo])["reference"]["savings"], 0)

    def test_day_and_payment_are_recommended_within_horizon(self):
        row = report([product("a", 100)], [promotion(valid_days="Miércoles")])["reference"]
        self.assertEqual(row["date"], "2026-11-04")
        self.assertEqual(row["day"], "Miércoles")
        self.assertIn("Banco Uno", row["payment"])

    def test_no_profile_and_wrong_card_type_do_not_get_a_benefit(self):
        self.assertEqual(report([product("a", 100)], methods=[])["reference"]["savings"], 0)
        methods = [{**METHODS[0], "card_mode": "debit"}]
        self.assertEqual(report([product("a", 100)], methods=methods)["reference"]["savings"], 0)

    def test_bank_and_wallet_are_both_required(self):
        promo = promotion(wallet="MODO")
        for methods in (METHODS, [{"name": "MODO", "type": "wallet"}]):
            self.assertEqual(report([product("a", 100)], [promo], methods)["reference"]["savings"], 0)
        methods = METHODS + [{"name": "MODO", "type": "wallet"}]
        self.assertEqual(report([product("a", 100)], [promo], methods)["reference"]["savings"], 30)

    def test_profile_tier_is_required(self):
        promo = promotion(bank="Brubank", title="Brubank 30% Plan Ultra")
        methods = [{"name": "Brubank", "type": "bank", "tiers": []}]
        self.assertEqual(report([product("a", 100)], [promo], methods)["reference"]["savings"], 0)
        methods[0]["tiers"] = ["ultra"]
        self.assertEqual(report([product("a", 100)], [promo], methods)["reference"]["savings"], 30)

    def test_excluded_wines_are_not_discounted(self):
        items = [product("milk", 100), product("wine", 100, name="Vino Alaris Malbec", path=["Bebidas", "Vinos y espumantes"])]
        row = report(items, [promotion(exclusions=["No incluye vinos"])])["reference"]
        self.assertEqual(row["total"], 170)
        self.assertEqual(row["eligible_count"], 1)

    def test_closed_list_only_discounts_matched_products(self):
        items = [product("milk", 100), product("wine", 100, name="Vino Malbec", path=["Bebidas", "Vinos"])]
        promo = promotion(exclusions=["El descuento aplica únicamente a los productos listados; todo producto fuera de esta lista queda excluido. Productos incluidos: LECHES, ADEREZOS"])
        self.assertEqual(report(items, [promo])["reference"]["savings"], 30)

    def test_closed_list_does_not_hide_later_exclusions(self):
        items = [product("milk", 100), product("yogurt", 100, name="Yogur X", path=["Lácteos", "Yogures"])]
        promo = promotion(exclusions=["Productos incluidos: LECHES, YOGURES", "No incluye leches"])
        self.assertEqual(report(items, [promo])["reference"]["savings"], 30)
        promo = promotion(exclusions=["Productos incluidos: LECHES, YOGURES. No incluye leches"])
        self.assertEqual(report(items, [promo])["reference"]["savings"], 30)

    def test_comparisons_reprice_common_products_and_recheck_minimum(self):
        a, b = product("a", 100), product("b", 100)
        a["offers"].append({"store": "dia", "price": 90})
        result = report([a, b], [promotion(min_purchase="$200")])
        other = next(r for r in result["options"] if r["store"] == "dia")
        self.assertEqual(result["reference"]["total"], 150)
        self.assertEqual(other["comparison"]["reference_total"], 100)
        self.assertEqual(other["comparison"]["difference"], -10)

    def test_single_promo_is_chosen_not_stacked_and_unknown_sale_accumulation_is_excluded(self):
        row = report([product("a", 100)], [promotion(), promotion(discount="20%", tope="Sin tope")])["reference"]
        self.assertEqual(row["savings"], 30)
        self.assertEqual(report([product("a", 100, list_price=120)])["reference"]["savings"], 0)
        self.assertEqual(report([product("a", 100, list_price=120)], [promotion(acumulable=True)])["reference"]["savings"], 30)

    def test_missing_products_do_not_make_a_partial_basket_the_winner(self):
        a, b = product("a", 100), product("b", 100)
        a["offers"].append({"store": "dia", "price": 1})
        result = report([a, b], [])
        self.assertEqual(result["reference"]["store"], "coto")
        other = next(r for r in result["options"] if r["store"] == "dia")
        self.assertEqual(other["missing"], [b["product_name"]])
        self.assertEqual(other["comparison"]["product_count"], 1)
        self.assertEqual(other["comparison"]["difference"], -99)

    def test_partial_reference_compares_only_intersection(self):
        a, b, c, missing = [product(k, 100) for k in ("a", "b", "c", "d")]
        missing["offers"] = []
        for p in (a, b, c):
            p["offers"].append({"store": "dia", "price": 90})
        result = report([a, b, c, missing], [])
        self.assertEqual(result["reference_kind"], "partial")
        self.assertEqual(result["reference"]["store"], "dia")
        self.assertEqual(result["reference"]["priced_count"], 3)

    def test_zero_nan_and_unknown_stores_are_not_prices(self):
        for value in (0, -1, float("nan"), float("inf")):
            self.assertIsNone(report([product("a", value)])["reference"])
        self.assertFalse(report([product("a", 100)])["shipping_included"])

    def test_favorite_stores_are_respected(self):
        result = report([product("a", 100)], favorites=["Carrefour", "Local sin adaptador"])
        self.assertEqual(result["options"], [])
        self.assertEqual(result["unsupported_favorites"], ["Local sin adaptador"])


if __name__ == "__main__":
    unittest.main()
