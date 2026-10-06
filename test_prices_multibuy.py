import unittest
from datetime import date

from prices.effective import apply_best_promo
from prices.models import Offer
from prices.multibuy import MultiBuy, parse_multibuy
from prices.registry import STORES
from prices.sources import coto, vtex

STORE = {s.key: s for s in STORES}
SATURDAY = date(2026, 10, 3)


def offer(price=1000.0, multibuy=None, store="carrefour"):
    s = STORE[store]
    return Offer(store=s.key, store_name=s.name, merchant=s.merchant, title="Producto", price=price,
                 url="https://x/p", multibuy=multibuy.to_dict() if multibuy else None)


class ParseTests(unittest.TestCase):
    def test_carrefour_teaser_names(self):
        mb = parse_multibuy("PROMO-2do al 50% Max 48 unidades Combinable COCA COLA-Reg-2-50-1Aniv 2 al 8.10")
        self.assertEqual((mb.label, mb.kind, mb.min_qty, mb.pct, mb.max_units, mb.exact),
                         ("2do al 50%", "nth_pct", 2, 50, 48, True))

    def test_other_formats(self):
        self.assertEqual(parse_multibuy("Llevando 3x2 en lácteos").pay, 2)
        self.assertEqual(parse_multibuy("50% 2da").label, "2do al 50%")
        self.assertEqual(parse_multibuy("3ro al 70%").min_qty, 3)

    def test_campaign_tag_is_approximate(self):
        mb = parse_multibuy("Hasta 2do al 70% en Almacén y Bebidas")
        self.assertFalse(mb.exact)
        self.assertTrue(mb.label.startswith("hasta"))

    def test_non_quantity_promos_are_ignored(self):
        for text in ("PROMO-Exclusivo online 30% Off -Reg-1-30-Quilmes2/10 al 8/10", "Tarjeta Carrefour 15%",
                     "Aniversario DIA 2026", "12x330 ml", "", None):
            self.assertIsNone(parse_multibuy(text), text)


class TotalTests(unittest.TestCase):
    def test_second_at_half_price(self):
        mb = parse_multibuy("2do al 50%")
        self.assertEqual([mb.total(1000, q) for q in (1, 2, 3, 4)], [1000, 1500, 2500, 3000])

    def test_max_units_caps_the_promo(self):
        mb = parse_multibuy("2do al 50% Max 8 unidades")
        self.assertEqual(mb.total(1000, 10), 4 * 1500 + 2 * 1000)

    def test_n_for_m(self):
        mb = parse_multibuy("3x2")
        self.assertEqual([mb.total(100, q) for q in (1, 2, 3, 5, 6)], [100, 200, 200, 400, 400])

    def test_published_unit_price_wins(self):
        mb = parse_multibuy("2x1", unit_price=901)
        self.assertEqual((mb.total(1802, 2), mb.total(1802, 3)), (1802, 3604))

    def test_approximate_tags_never_change_the_price(self):
        self.assertEqual(parse_multibuy("Hasta 2do al 70% en Bebidas").total(1000, 2), 2000)


class EffectiveTests(unittest.TestCase):
    BANK = [{"supermarket_name": "Carrefour", "title": "Patagonia 30%", "discount": "30%",
             "bank": "Banco Patagonia", "valid_days": "Sábado", "tope": "$5.000"}]

    def test_one_unit_is_unaffected_but_the_tag_is_exposed(self):
        result = apply_best_promo(offer(multibuy=parse_multibuy("2do al 50%")), [], SATURDAY, qty=1)
        self.assertEqual((result.total, result.savings, result.deal), (1000, 0, None))
        self.assertEqual(result.multibuy["unit_at_min"], 750)

    def test_buying_two_applies_the_quantity_promo(self):
        result = apply_best_promo(offer(multibuy=parse_multibuy("2do al 50%")), [], SATURDAY, qty=2)
        self.assertEqual((result.total, result.final_price, result.deal), (1500, 750, "multibuy"))
        self.assertIsNone(result.promo)

    def test_picks_the_cheaper_path_without_stacking(self):
        # 2do al 50% ahorra 500 sobre 2 u.; el banco ahorra 30% = 600 (tope 5.000): gana el banco
        result = apply_best_promo(offer(multibuy=parse_multibuy("2do al 50%")), self.BANK, SATURDAY, qty=2)
        self.assertEqual((result.deal, result.total), ("bank", 1400))
        self.assertEqual(result.promo["entity"], "Banco Patagonia")
        # con 2do al 80% ahorra 800 > 600: gana la promo de cantidad
        result = apply_best_promo(offer(multibuy=parse_multibuy("2do al 80%")), self.BANK, SATURDAY, qty=2)
        self.assertEqual((result.deal, result.total), ("multibuy", 1200))

    def test_bank_cap_applies_to_the_whole_purchase(self):
        result = apply_best_promo(offer(price=100000), self.BANK, SATURDAY, qty=3)
        self.assertEqual(result.savings, 5000)
        self.assertEqual(result.total, 295000)


class SourceTests(unittest.TestCase):
    def test_vtex_reads_carrefour_teasers_and_ignores_card_teasers(self):
        product = {"productName": "Gaseosa", "brand": "Coca", "link": "/g/p", "categories": ["/Bebidas/Gaseosas/"],
                   "items": [{"ean": "1", "images": [], "sellers": [{"sellerDefault": True, "commertialOffer": {
                       "Price": 6000, "ListPrice": 6000, "IsAvailable": True, "Teasers": [
                           {"<Name>k__BackingField": "Tarjeta Carrefour 15%", "<Conditions>k__BackingField":
                            {"<MinimumQuantity>k__BackingField": 0}},
                           {"<Name>k__BackingField": "PROMO-2do al 50% Max 48 unidades Combinable",
                            "<Conditions>k__BackingField": {"<MinimumQuantity>k__BackingField": 2}}]}}]}]}
        parsed = vtex.parse_product(STORE["carrefour"], product)
        self.assertEqual((parsed.multibuy["label"], parsed.multibuy["min_qty"], parsed.multibuy["max_units"]),
                         ("2do al 50%", 2, 48))
        self.assertEqual(parsed.category, "/Bebidas/Gaseosas/")

    def test_vtex_cluster_tag_is_not_calculated(self):
        product = {"productName": "Gaseosa", "link": "/g/p", "clusterHighlights": {"1": "Coca Cola",
                   "2": "Hasta 2do al 70% en Almacén y Bebidas"},
                   "items": [{"ean": "1", "images": [], "sellers": [{"commertialOffer": {
                       "Price": 6000, "IsAvailable": True}}]}]}
        parsed = vtex.parse_product(STORE["jumbo"], product)
        self.assertFalse(parsed.multibuy["exact"])

    def test_coto_two_for_one_uses_the_published_unit_price(self):
        attrs = {"product.dtoDescuentos": ['[{"textoDescuento":"2x1","precioDesc":"901.00",'
                                           '"precioDescTextoAdicional":"c/u","textoLlevando":"Llevando 2"}]']}
        found = coto._multibuy(attrs)
        self.assertEqual((found["label"], found["min_qty"], found["unit_price"]), ("2x1", 2, 901.0))
        self.assertIsNone(coto._multibuy({"product.dtoDescuentos": ['[{"textoDescuento":"25%Dto","precioDesc":"10"}]']}))


if __name__ == "__main__":
    unittest.main()
