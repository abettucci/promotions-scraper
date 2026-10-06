import unittest

from prices.categories import classify, category_string

CASES = [
    # (título, categorías de la tienda, esperado)
    ("Aceite de Girasol Cocinero 1,5 Lt.", [], ["Almacén", "Aceites y vinagres"]),
    ("Aceitunas verdes rellenas 200 g", ["/Quesos y Fiambres/Encurtidos, Aceitunas y Pickles/"], ["Almacén", "Conservas"]),
    ("Dulce de Leche La Serenisima 400 g", [], ["Almacén", "Dulces y mermeladas"]),
    ("Leche Entera La Serenísima 1L", [], ["Lácteos", "Leches"]),
    ("Leche en polvo Nido 800 g", [], ["Lácteos", "Leches"]),
    ("Queso Cremoso La Paulina 1 kg", [], ["Lácteos", "Quesos"]),
    ("Yerba Mate Playadito 1 kg", [], ["Almacén", "Yerba, café y té"]),
    ("Cafetera Nespresso Essenza Mini", [], ["Electro", "Pequeños electrodomésticos"]),
    ("Gaseosa Coca-Cola Sabor Original 2,25 Lt", [], ["Bebidas", "Gaseosas"]),
    ("Cerveza Quilmes Clásica 1 L", [], ["Bebidas", "Cervezas"]),
    ("Vino Tinto Malbec Trapiche 750 ml", [], ["Bebidas", "Vinos y espumantes"]),
    ("Agua Mineral Villavicencio 2 L", [], ["Bebidas", "Aguas y sodas"]),
    ("Galletitas Oreo Originales 118 g", [], ["Almacén", "Galletitas, snacks y golosinas"]),
    ("Alfajores Havanna x6", [], ["Almacén", "Galletitas, snacks y golosinas"]),
    ("Papel Higiénico Elite 12 rollos", [], ["Limpieza", "Papel higiénico y de cocina"]),
    ("Detergente Magistral Limón 750 ml", [], ["Limpieza", "Detergentes y lavavajillas"]),
    ("Jabón en polvo Skip 3 kg", [], ["Limpieza", "Lavado de ropa"]),
    ("Lavandina Ayudín 1 L", [], ["Limpieza", "Lavandinas y desinfectantes"]),
    ("Shampoo Pantene 400 ml", [], ["Perfumería", "Cuidado del cabello"]),
    ("Crema hidratante Nivea 200 ml", [], ["Perfumería", "Cuidado de la piel"]),
    ("Pasta dental Colgate 90 g", [], ["Perfumería", "Higiene bucal"]),
    ("Pañales Pampers XG 36 un", [], ["Bebés", "Pañales y toallitas"]),
    ("Alimento perro adulto Dogui 21 kg", [], ["Mascotas", "Alimento y accesorios"]),
    ("Heladera Samsung No Frost 299 L", [], ["Electro", "Heladeras y freezers"]),
    ("Lavarropas Drean 7 kg", [], ["Electro", "Lavarropas y secarropas"]),
    ('Smart TV 50" Samsung 4K UN50U8000', [], ["Electro", "Televisores"]),
    ('Celular Motorola G17 6.72" 4GB', [], ["Electro", "Celulares y tablets"]),
    ("Tablet Samsung Galaxy Tab A9", [], ["Electro", "Celulares y tablets"]),
    ("Notebook Lenovo IdeaPad 15", [], ["Electro", "Informática"]),
    ("Auriculares JBL Tune 510BT", [], ["Electro", "Audio y video"]),
    ("PlayStation 5 Slim", [], ["Electro", "Videojuegos"]),
    ("Aire Acondicionado Split 3000 frigorías", [], ["Electro", "Climatización y agua caliente"]),
    ("Ventilador de Pie 20 pulgadas", [], ["Electro", "Climatización y agua caliente"]),
    ("Microondas Samsung 23 L", [], ["Electro", "Cocinas y hornos"]),
    ("Freidora de aire 4 L", [], ["Electro", "Pequeños electrodomésticos"]),
    ("Silla gamer ergonómica", [], ["Hogar", "Muebles y colchones"]),
    ("Vinagrera Aceitera Cocina de Metal 250 ml", [], ["Hogar", "Cocina y bazar"]),
    ("Cocina Longvie 4 hornallas", [], ["Electro", "Cocinas y hornos"]),
    ("Cocina a gas Drean 56 cm", [], ["Electro", "Cocinas y hornos"]),
    ("Pulpa de tomate Arcor 520 g", [], ["Almacén", "Aderezos y salsas"]),
]


class ClassifyTests(unittest.TestCase):
    def test_known_products(self):
        wrong = [(title, classify(title, cats), expected) for title, cats, expected in CASES
                 if classify(title, cats) != expected]
        self.assertEqual(wrong, [])

    def test_unknown_products_go_to_otros_and_store_categories_are_a_fallback(self):
        self.assertEqual(classify("Producto misterioso XJ-9"), ["Otros"])
        self.assertEqual(classify("Producto misterioso XJ-9", ["/Bebidas/Cervezas/Rubias/"]), ["Bebidas", "Cervezas"])

    def test_category_string_matches_the_path_format_used_elsewhere(self):
        self.assertEqual(category_string(["Almacén", "Aceites y vinagres"]), "/Almacén/Aceites y vinagres/")
        self.assertEqual(category_string([]), "")


if __name__ == "__main__":
    unittest.main()
