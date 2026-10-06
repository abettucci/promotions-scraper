"""Árbol de categorías propio (2 niveles) para filtrar productos de cualquier tienda.

Cada tienda usa su propio árbol ("Heladeras y Freezers", "Electro y tecnología
› Heladeras", "Electrodomésticos › Refrigeración"), así que un filtro armado con
ellos deja afuera productos de las otras tiendas. Acá se clasifica por palabras
del nombre del producto y, si el nombre no alcanza, por la categoría que publica
la tienda. Lo que no entra en ninguna regla queda en "Otros".
"""
from __future__ import annotations

import re
from typing import Iterable

from .matching import norm

# (categoría, subcategoría, regex sobre texto normalizado: minúsculas, sin tildes).
# El orden importa: lo más específico va primero ("dulce de leche" antes que "leche").
_RULES: list[tuple[str, str, str]] = [
    # ── Mascotas y bebés (antes que Almacén/Lácteos: "alimento", "leche")
    ("Mascotas", "Alimento y accesorios", r"\b(alimento|comida)\b.*\b(perro|gato|cachorro|mascota)s?\b|\b(dogui|whiskas|pedigree|purina|royal canin|dog chow|cat chow|excellent|piedras? sanitarias?|arena sanitaria|sieger)\b"),
    ("Bebés", "Pañales y toallitas", r"\bpa(n|ñ)al(es)?\b|\btoallitas? humedas?\b|\bpampers\b|\bhuggies\b"),
    ("Bebés", "Leche y alimentos infantiles", r"\b(nutrilon|nan |sancor bebe|formula infantil|etapa [123])\b|\bleche (infantil|de crecimiento)\b"),
    # ── Almacén
    ("Almacén", "Dulces y mermeladas", r"\bdulce de leche\b|\bmermelada\b|\bdulce de (batata|membrillo)\b|\bmiel\b"),
    ("Almacén", "Aceites y vinagres", r"\baceites?\b|\bvinagres?\b|\baceto balsamico\b"),
    ("Almacén", "Aderezos y salsas", r"\bmayonesa\b|\bketchup\b|\bmostaza\b|\baderezo\b|\bsalsa (golf|criolla|barbacoa|de soja)\b|\bsalsa (de )?tomate\b|\bpure de tomate\b|\bpulpa de tomate\b|\btomate cubeteado\b|\btomate (triturado|perita|en cubos)\b|\bsalsa (lista|pizza|filetto|bolognesa)\b"),
    ("Almacén", "Conservas", r"\b(atun|caballa|sardinas?|arvejas?|choclo|lentejas? (en )?lata|palmitos?|duraznos? en almibar|champi(n|ñ)ones? (en )?lata|aceitunas?|pickles?)\b|\bconservas?\b"),
    ("Almacén", "Fideos y pastas", r"\bfideos?\b|\bspaghetti\b|\btallarines?\b|\bravioles?\b|\bnoquis\b|\bsorrentinos?\b|\bpastas? (secas?|frescas?|rellenas?)\b|\bmo(n|ñ)itos\b|\btirabuzon\b"),
    ("Almacén", "Arroz, legumbres y harinas", r"\barroz\b|\blentejas?\b|\bgarbanzos?\b|\bporotos?\b|\bharinas?\b|\bpolenta\b|\bsemola\b|\bpremezcla\b"),
    ("Almacén", "Yerba, café y té", r"\byerba\b|\bcafe\b|\bte (en saquitos|verde|negro|de|rojo)\b|\bsaquitos\b|\bmate cocido\b|\bcacao\b|\bnesquik\b|\binfusion(es)?\b|\bcapsulas? (de )?cafe\b|\bnescafe\b"),
    ("Almacén", "Galletitas, snacks y golosinas", r"\bgalletitas?\b|\bgalletas?\b|\boreo\b|\bsnacks?\b|\bpapas fritas\b|\blays\b|\bpringles\b|\balfajor(es)?\b|\bchocolates?\b|\bgolosinas?\b|\bcaramelos?\b|\bchicles?\b|\bbarras? de cereal\b|\bmani\b|\bturron\b|\bbombones?\b"),
    ("Almacén", "Azúcar y endulzantes", r"\bazucar\b|\bedulcorantes?\b|\bstevia\b|\bsacarina\b"),
    ("Almacén", "Sal y condimentos", r"\bsal (fina|gruesa|entrefina|de mesa)\b|\bcelusal\b|\bpimienta\b|\bcondimentos?\b|\boregano\b|\bpimenton\b|\bespecias?\b|\bcomino\b"),
    ("Almacén", "Cereales y desayuno", r"\bcereales?\b|\bavena\b|\bgranola\b|\bcopos\b|\bmuesli\b"),
    ("Almacén", "Huevos", r"\bhuevos?\b"),
    # ── Bebidas
    ("Bebidas", "Gaseosas", r"\bgaseosas?\b|\bcoca[- ]?cola\b|\bpepsi\b|\bsprite\b|\bfanta\b|\bseven ?up\b|\b7 ?up\b|\bschweppes\b|\bmirinda\b|\bpomelo\b.*\b(l|lt|lts|ml)\b|\bcola\b"),
    ("Bebidas", "Aguas y sodas", r"\bagua (mineral|sin gas|con gas|saborizada|tonica)\b|\bsoda\b|\bsifon\b|\bvillavicencio\b|\beco de los andes\b|\bbonaqua\b|\bglaciar\b|\bagua de mesa\b"),
    ("Bebidas", "Cervezas", r"\bcervezas?\b|\bquilmes\b|\bbrahma\b|\bstella artois\b|\bheineken\b|\bandes origen\b|\bbudweiser\b|\bcorona\b|\bimperial\b|\bpatagonia (ipa|amber|bohemian)\b"),
    ("Bebidas", "Vinos y espumantes", r"\bvinos?\b|\bmalbec\b|\bcabernet\b|\bchardonnay\b|\bespumantes?\b|\bchampa(n|ñ)a\b|\bchandon\b|\btorrontes\b|\bmerlot\b|\bsyrah\b|\bblend\b.*\b(tinto|blanco)\b"),
    ("Bebidas", "Aperitivos y licores", r"\bfernet\b|\bgin\b|\bvodka\b|\bwhisky\b|\bron\b|\blicor\b|\bcampari\b|\baperol\b|\bbranca\b|\bcinzano\b|\bgancia\b|\bcoctel\b|\btequila\b"),
    ("Bebidas", "Jugos y energizantes", r"\bjugos?\b|\bcepita\b|\bbaggio\b|\bclight\b|\btang\b|\bisotonic[ao]s?\b|\bgatorade\b|\bpowerade\b|\benergizantes?\b|\bmonster\b|\bred bull\b|\bspeed\b"),
    # ── Lácteos
    ("Lácteos", "Manteca y cremas", r"\bmanteca\b|\bmargarina\b|\bcrema (de leche|para batir|doble|de leche)\b|\bcrema chantilly\b"),
    ("Lácteos", "Quesos", r"\bquesos?\b|\bcremoso\b|\bmozzarella\b|\bmuzzarella\b|\bmuzarela\b|\brallado\b|\bfontina\b|\bprovolone\b|\bsardo\b|\bport salut\b|\bricota\b|\bpasteurizado\b|\bdambo\b|\btybo\b"),
    ("Lácteos", "Yogures y postres", r"\byogu?r(t)?\b|\bpostres?\b|\bflan\b|\bgelatina\b|\bdanette\b|\bdanonino\b"),
    ("Lácteos", "Leches", r"\bleche\b|\bleche en polvo\b|\bla serenisima\b.*\b(entera|descremada|larga vida)\b"),
    # ── Carnes y fiambres
    ("Carnes y fiambres", "", r"\b(carne|pollo|milanesas?|hamburguesas?|salchichas?|jamon|fiambres?|salame|bondiola|chorizo|pescado|merluza|nuggets|pata muslo|cerdo|asado|vacio|picada)\b"),
    # ── Limpieza
    ("Limpieza", "Papel higiénico y de cocina", r"\bpapel higienico\b|\brollos? de cocina\b|\bpapel de cocina\b|\bservilletas?\b|\bpa(n|ñ)uelos descartables\b|\bhigienol\b|\belite\b|\bsussex\b"),
    ("Limpieza", "Lavado de ropa", r"\bjabon (en polvo|liquido)\b|\bsuavizantes?\b|\bquitamanchas?\b|\bskip\b|\bariel\b|\bdrive\b|\bvivere\b|\bcomfort\b|\bdetergente para (la )?ropa\b|\bineo\b"),
    ("Limpieza", "Detergentes y lavavajillas", r"\bdetergentes?\b|\blavavajillas?\b|\bmagistral\b|\bcif\b.*\b(crema|cremoso)\b"),
    ("Limpieza", "Lavandinas y desinfectantes", r"\blavandinas?\b|\bdesinfectantes?\b|\blimpiador(es)?\b|\blimpia (pisos|vidrios|hornos|muebles)\b|\bayudin\b|\blysoform\b|\bpoett\b|\binsecticidas?\b|\braid\b|\bfuyi\b|\bdesodorante de ambiente\b|\baromatizante\b"),
    ("Limpieza", "Bolsas y descartables", r"\bbolsas? de (residuos|consorcio|basura)\b|\bfilm\b|\bpapel (aluminio|manteca)\b|\besponjas?\b|\bguantes? de (latex|limpieza)\b|\btrapo\b|\bvasos? descartables\b"),
    # ── Perfumería
    ("Perfumería", "Cuidado del cabello", r"\bshampoo\b|\bacondicionador\b|\bcrema de enjuague\b|\btintura\b|\bgel fijador\b|\bpantene\b|\bsedal\b|\bhead (&|y) shoulders\b|\bplusbelle\b"),
    ("Perfumería", "Desodorantes", r"\bdesodorantes?\b|\bantitranspirantes?\b|\brexona\b|\bspeed stick\b"),
    ("Perfumería", "Higiene bucal", r"\bpasta dental\b|\bcepillos? dental(es)?\b|\benjuague bucal\b|\bcolgate\b|\bhilo dental\b|\boral[- ]?b\b"),
    ("Perfumería", "Cuidado de la piel", r"\bcrema (hidratante|facial|corporal|para manos|antiarrugas)\b|\bprotector(es)? solar(es)?\b|\bbronceador\b|\brepelente\b|\bnivea\b|\bloci(o|ó)n\b|\bdermocosmetica\b"),
    ("Perfumería", "Higiene personal", r"\bjabon (de tocador|intimo|en barra)\b|\bgel de (ducha|ba(n|ñ)o)\b|\btoallas? femeninas?\b|\btampones\b|\bprotectores? diarios?\b|\balgodon\b|\bmaquinitas? de afeitar\b|\bespuma de afeitar\b|\bperfumes?\b|\bcolonia\b|\bdove\b"),
    # ── Electro
    ("Electro", "Heladeras y freezers", r"\bheladeras?\b|\bfreezers?\b|\bfrigobar\b|\bcavas? de vino\b"),
    ("Electro", "Lavarropas y secarropas", r"\blavarropas\b|\blavasecarropas\b|\bsecarropas\b|\blavavajillas (de )?(embutir|libre)\b"),
    ("Electro", "Televisores", r"\btv\b|\btelevisor(es)?\b|\bsmart tv\b|\bled\b.*\b(pulgadas|\d{2}\")\b|\bqled\b|\boled\b|\b\d{2} ?pulgadas\b"),
    ("Electro", "Celulares y tablets", r"\bcelular(es)?\b|\bsmartphones?\b|\biphone\b|\bgalaxy [asmz]\d+\b|\bmoto ?[gebx]\d*\b|\bmotorola\b|\bredmi\b|\bxiaomi\b|\bpoco\b|\btablets?\b|\bipad\b|\bgalaxy tab\b"),
    ("Electro", "Informática", r"\bnotebooks?\b|\blaptops?\b|\bmonitor(es)?\b|\bimpresoras?\b|\bmouse\b|\bteclados?\b|\bcomputadoras?\b|\bpc (de )?escritorio\b|\bpendrive\b|\brouter\b|\bdisco (duro|solido|rigido)\b|\bplacas? de video\b|\bmemoria (ram|usb)\b"),
    ("Electro", "Audio y video", r"\bauricular(es)?\b|\bparlantes?\b|\bbarras? de sonido\b|\bsoundbar\b|\bhome theater\b|\bjbl\b|\bcamaras?\b|\bgopro\b|\bproyector\b|\bbluetooth\b"),
    ("Electro", "Videojuegos", r"\bplaystation\b|\bps[345]\b|\bxbox\b|\bnintendo\b|\bjoysticks?\b|\bconsolas?\b|\bvideojuegos?\b"),
    ("Electro", "Climatización y agua caliente", r"\baires? acondicionados?\b|\bsplit\b|\bfrigorias\b|\bcalefactor(es)?\b|\bestufas?\b|\bventilador(es)?\b|\bcaloventor(es)?\b|\btermotanques?\b|\bcalefon(es)?\b|\bradiador(es)?\b|\bdeshumidificador(es)?\b|\bpurificador de aire\b"),
    ("Electro", "Cocinas y hornos", r"^cocina\b|\bcocinas? (a gas|electricas?|combinadas?|industriales?|multigas|de (gas|induccion)|con horno)\b|\banafes?\b|\bhornos? (electricos?|a gas|empotrables?|de embutir)\b|\bmicroondas\b|\bcampanas? extractoras?\b|\bhornallas\b"),
    ("Electro", "Pequeños electrodomésticos", r"\bfreidoras?\b|\bcafeteras?\b|\bnespresso\b|\bpavas? electricas?\b|\btostadoras?\b|\blicuadoras?\b|\bbatidoras?\b|\bprocesadoras?\b|\baspiradoras?\b|\bplanchas?\b|\bsandwicheras?\b|\bexprimidor(es)?\b|\bmultiprocesadoras?\b|\bairfryer\b|\bolla (electrica|a presion)\b|\bsoda stream\b|\brobot\b|\bpicadora\b|\bwaflera\b|\bgrill\b"),
    # ── Hogar
    ("Hogar", "Muebles y colchones", r"\bcolchon(es)?\b|\bsommiers?\b|\bsillon(es)?\b|\bsillas?\b|\bmesas?\b|\bplacard\b|\bescritorios?\b|\bcamas?\b|\bsomier\b|\bbaulera\b|\brack\b"),
    ("Hogar", "Cocina y bazar", r"\bvinagreras?\b|\baceiteras?\b|\bsaleros?\b|\bcoladores?\b|\bcuchillos?\b|\bollas?\b|\bsarten(es)?\b|\bvajilla\b|\bplatos?\b|\bvasos?\b|\btazas?\b|\bcubiertos\b|\btermos?\b|\bbotellas? termica\b|\bparrilla\b|\bcacerola\b"),
    ("Hogar", "Herramientas y jardín", r"\btaladros?\b|\bherramientas?\b|\bcortadoras? de cesped\b|\bhidrolavadoras?\b|\bamoladoras?\b|\bjardin\b|\bpintura\b"),
]

_COMPILED = [(cat, sub, re.compile(pattern)) for cat, sub, pattern in _RULES]
OTHER = "Otros"


def classify(title: str, store_categories: Iterable[str] = ()) -> list[str]:
    """Devuelve [categoría, subcategoría] (o [categoría] / ["Otros"])."""
    name = norm(title)
    for cat, sub, rule in _COMPILED:
        if rule.search(name):
            return [cat, sub] if sub else [cat]
    # El nombre no alcanzó: se prueba con las categorías que publican las tiendas
    # ("/Bebidas/Gaseosas/Cola/"), que casi siempre nombran el rubro.
    extra = norm(" ".join(c.replace("/", " ") for c in store_categories if c))
    if extra:
        for cat, sub, rule in _COMPILED:
            if rule.search(extra):
                return [cat, sub] if sub else [cat]
    return [OTHER]


def category_string(path: list[str]) -> str:
    """["Almacén", "Aceites"] → "/Almacén/Aceites/" (el formato que ya usa el resto del código)."""
    return "/" + "/".join(path) + "/" if path else ""
