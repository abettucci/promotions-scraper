import unittest

from supermarket_tiers import big_chain_ids, is_big_chain, normalize_tier, tier_sql


class SupermarketTiersTests(unittest.TestCase):
    def test_big_chains_are_recognized_with_name_variants(self):
        for name in ["Carrefour", "Supermercados Día", "Supermercados Dia", "Coto Digital",
                     "Jumbo (Cencosud)", "Vea", "Disco", "Más Online (ChangoMás)", "Chango Mas"]:
            self.assertTrue(is_big_chain(name), name)

    def test_other_stores_are_small(self):
        for name in ["Diarco", "Super Vanoli", "Velasquez e Hijos", "Discovery Market", "Cooperativa Obrera"]:
            self.assertFalse(is_big_chain(name), name)

    def test_big_chain_ids_from_a_table(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE supermarkets (id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO supermarkets VALUES (?, ?)",
                         [(1, "Carrefour"), (2, "Diarco"), (3, "Disco"), (4, "Super Vanoli")])
        self.assertEqual(sorted(big_chain_ids(conn)), [1, 3])

    def test_normalize_tier_rejects_unknown_values(self):
        self.assertEqual(normalize_tier("Grandes"), "grandes")
        self.assertEqual(normalize_tier("chicos"), "chicos")
        self.assertIsNone(normalize_tier("todos"))
        self.assertIsNone(normalize_tier(""))

    def test_tier_sql_builds_in_and_not_in(self):
        self.assertEqual(tier_sql("grandes", "p.supermarket_id", [1, 3]),
                         ("p.supermarket_id IN (?,?)", [1, 3]))
        self.assertEqual(tier_sql("chicos", "p.supermarket_id", [1, 3]),
                         ("p.supermarket_id NOT IN (?,?)", [1, 3]))

    def test_tier_sql_without_big_chains_does_not_break(self):
        self.assertEqual(tier_sql("grandes", "p.supermarket_id", []), ("1 = 0", []))
        self.assertEqual(tier_sql("chicos", "p.supermarket_id", []), ("1 = 1", []))


if __name__ == "__main__":
    unittest.main()
