import unittest
from unittest.mock import patch

from prices import suggest as sg
from prices.models import Offer, ProductGroup
from prices.search import _fill_group_metadata, build_facets, search_prices, _cache as search_cache
from prices.suggest import matches, suggest


def offer(store, title, brand="", ean="", category="", image="img", in_stock=True):
    return Offer(store=store, store_name=store.title(), merchant=None, title=title, brand=brand, ean=ean,
                 price=100.0, url=f"https://{store}/p", category=category, image=image, in_stock=in_stock)


class MatchTests(unittest.TestCase):
    def test_every_typed_word_must_start_a_word_of_the_name(self):
        self.assertTrue(matches("heladera sam", "Heladera Samsung No Frost"))
        self.assertTrue(matches("SAM heladera", "Heladera Samsung"))       # orden y mayúsculas no importan
        self.assertTrue(matches("lé", "Leche entera"))                       # tildes no importan
        self.assertFalse(matches("acei", "Crema hidratante"))
        self.assertFalse(matches("amsung", "Heladera Samsung"))              # no es sufijo ni subcadena
        self.assertFalse(matches("", "Leche"))

    def test_brand_counts_as_text(self):
        self.assertTrue(matches("cocinero acei", "Aceite de girasol 1,5 L", "Cocinero"))


class SuggestTests(unittest.TestCase):
    def setUp(self):
        sg._cache.clear()
        self.calls = []

    def fake_search(self, results):
        def fn(store, query, limit, timeout):
            self.calls.append(store.key)
            return results.get(store.key, [])
        return fn

    def test_local_index_answers_without_going_out(self):
        products = [
            {"key": "ean:1", "name": "Aceite Cocinero 900 ml", "brand": "Cocinero", "image": "a.jpg",
             "category": "/Almacén/Aceites/"},
            {"key": "ean:2", "name": "Vinagre Cocinero", "brand": "Cocinero", "image": "", "category": ""},
            {"key": "ean:3", "name": "Leche", "brand": "X", "image": "", "category": ""},
        ]
        result = suggest("aceite coc", products=products, live=False)
        self.assertEqual([s["key"] for s in result["suggestions"]], ["ean:1"])
        self.assertEqual(result["suggestions"][0]["image"], "a.jpg")
        self.assertEqual(result["suggestions"][0]["category_path"], ["Almacén", "Aceites"])
        self.assertEqual(suggest("a", products=products, live=False)["suggestions"], [])   # menos de 2 letras

    def test_live_groups_by_product_counts_stores_and_drops_non_matches(self):
        results = {
            "carrefour": [offer("carrefour", "Heladera Samsung RT29", "Samsung", "7790000000111", "/Electro/Heladeras/"),
                          offer("carrefour", "Funda para celular", "Xyz", "7790000000999")],
            "fravega": [offer("fravega", "HELADERA SAMSUNG RT29K", "Samsung", "7790000000111", "/Heladeras/Heladeras/No Frost/")],
            "jumbo": [offer("jumbo", "Heladera Philco", "Philco", "7790000000222")],
        }
        with patch.object(sg, "_FAST_STORES", ("carrefour", "fravega", "jumbo")):
            result = suggest("heladera sam", live=True, search_fn=self.fake_search(results))
        self.assertEqual(len(result["suggestions"]), 1)
        item = result["suggestions"][0]
        self.assertEqual((item["stores"], item["image"]), (2, "img"))
        self.assertEqual(item["category_path"], ["Electro", "Heladeras y freezers"])   # árbol propio, no el de cada tienda

    def test_live_results_are_cached_but_empty_ones_are_not(self):
        results = {"carrefour": [offer("carrefour", "Leche entera", "Sancor", "7790000000005")]}
        fn = self.fake_search(results)
        with patch.object(sg, "_FAST_STORES", ("carrefour",)):
            suggest("leche", live=True, search_fn=fn)
            suggest("leche", live=True, search_fn=fn)
            self.assertEqual(self.calls, ["carrefour"])           # la segunda salió del cache
            suggest("zzzz", live=True, search_fn=fn)
            suggest("zzzz", live=True, search_fn=fn)
            self.assertEqual(self.calls.count("carrefour"), 3)    # lo vacío se vuelve a pedir

    def test_a_failing_store_does_not_break_the_rest(self):
        def fn(store, query, limit, timeout):
            if store.key == "jumbo":
                raise RuntimeError("caída")
            return [offer(store.key, "Leche entera", "Sancor", "7790000000005")]
        with patch.object(sg, "_FAST_STORES", ("carrefour", "jumbo")):
            self.assertEqual(suggest("leche", live=True, search_fn=fn)["suggestions"][0]["stores"], 1)

    def test_category_suggestions_use_one_tree_for_every_store(self):
        results = {"carrefour": [
            offer("carrefour", "Aceite Natura girasol", "Natura", "7790000000001", "/Almacén/Aceites y vinagres/"),
            offer("carrefour", "Aceite Cocinero mezcla", "Cocinero", "7790000000002", "/Almacén/Aceites y Vinagres/")],
            "masonline": [
            offer("masonline", "Aceite Arcor maíz", "Arcor", "7790000000003", "/Aceites, Vinagres Y Aderezos/Aceites/")]}
        with patch.object(sg, "_FAST_STORES", ("carrefour", "masonline")):
            categories = suggest("aceite", live=True, search_fn=self.fake_search(results))["categories"]
        # tres productos de dos tiendas con árboles distintos → una sola categoría propia
        self.assertEqual([(c["path"], c["count"]) for c in categories], [(["Almacén", "Aceites y vinagres"], 3)])

    def test_names_starting_with_the_query_rank_first(self):
        products = [{"key": "ean:1", "name": "Vinagre de aceite", "brand": "", "image": "", "category": ""},
                    {"key": "ean:2", "name": "Aceite de girasol", "brand": "", "image": "", "category": ""}]
        self.assertEqual(suggest("aceite", products=products, live=False)["suggestions"][0]["key"], "ean:2")


class FacetTests(unittest.TestCase):
    def test_group_gets_the_own_category_and_an_image_that_loads(self):
        group = ProductGroup(key="ean:1", name="Aceite de girasol 1 L", offers=[
            offer("coto", "x", category="", image="coto-blocked.jpg"),
            offer("carrefour", "x", category="/Almacén/Enlatados/", image="ok.jpg")])
        _fill_group_metadata(group)
        self.assertEqual(group.category, "/Almacén/Aceites y vinagres/")
        self.assertEqual(group.image, "ok.jpg")
        # si el nombre no alcanza, ayuda la categoría que publica la tienda
        vague = ProductGroup(key="ean:2", name="Producto XJ-9", offers=[offer("carrefour", "x", category="/Bebidas/Cervezas/")])
        _fill_group_metadata(vague)
        self.assertEqual(vague.category, "/Bebidas/Cervezas/")

    def test_facets_merge_case_variants_and_sort_by_count(self):
        groups = [{"category_path": p} for p in (
            ["Almacén", "Aceites y vinagres"], ["almacén", "Aceites y Vinagres"], ["Almacén", "Conservas"],
            ["Bebidas", "Gaseosas"], [])]
        facets = build_facets(groups)
        self.assertEqual([(f["name"], f["count"]) for f in facets], [("Almacén", 3), ("Bebidas", 1)])
        self.assertEqual(facets[0]["children"][0], {"name": "Aceites y vinagres", "count": 2})

    def test_otros_is_always_the_last_facet(self):
        groups = [{"category_path": p} for p in (["Otros"], ["Otros"], ["Otros"], ["Bebidas", "Gaseosas"])]
        self.assertEqual([f["name"] for f in build_facets(groups)], ["Bebidas", "Otros"])

    def test_search_response_exposes_categories_and_limit(self):
        offers = [offer("carrefour", f"Aceite Marca{i} 1l", "M", f"779000000000{i}", "/Almacén/Aceites/") for i in range(5)]
        search_cache.clear()
        with patch("prices.search._fetch_offers", return_value=(offers, [])):
            result = search_prices("aceite", max_groups=3)
        self.assertEqual(len(result["groups"]), 3)
        self.assertEqual(result["facets"][0]["name"], "Almacén")
        self.assertEqual(result["groups"][0]["category_path"], ["Almacén", "Aceites y vinagres"])


if __name__ == "__main__":
    unittest.main()
