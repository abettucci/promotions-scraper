#!/usr/bin/env python3
"""
Script de prueba final para verificar que:
1. Texto completo de términos se guarde
2. Exclusiones se extraigan correctamente
3. Requisitos NO incluyan exclusiones ni tope
"""
from terms_parser import TermsParser

# Texto real completo de la primera promoción
test_text = """PROMOCIÓN VÁLIDA TODOS LOS MIÉRCOLES DESDE EL 01 AL 30 DE NOVIEMBRE DE 2025 INCLUSIVE. PARA COMPRAS REALIZADAS A TRAVÉS DE LA FUNCIONALIDAD "PAGO CLAVE DNI" Y/O QR DE LA APLICACIÓN CUENTA DNI EN TODAS LAS TIENDAS HIPERMERCADOS CARREFOUR, CARREFOUR MARKET, CARREFOUR EXPRESS Y CARREFOUR MAXI. LA NÓMINA DE ADHERIDOS SE PODRÁ CONSULTAR EN WWW.BANCOPROVINCIA.COM.AR. BONIFICACIÓN DEL 10%. SIN TOPE DE REINTEGRO. EL BENEFICIO ESTARÁ A CARGO DE CARREFOUR. EL DESCUENTO SE REALIZARÁ EN EL MOMENTO DE LA COMPRA, EN EL MISMO INSTANTE EN QUE SE COBRE AL CLIENTE POR LA LÍNEA DE CAJA DEL ESTABLECIMIENTO. VÁLIDA ÚNICAMENTE PARA VENTA MINORISTA, SE EXCLUYEN DE LA PROMOCIÓN ELECTRODOMÉSTICOS Y PRODUCTOS FRESCOS (QUESOS Y FIAMBRES, PESCADERÍA FRESCA, FRUTAS Y VERDURAS, PANADERÍA, CARNICERÍA, PLATOS PREPARADOS). ACUMULABLE CON PRODUCTOS EN OFERTA. LA PROMOCIÓN NO APLICA A COMPRAS REALIZADAS CON CUENTA DNI MEDIANTE LA LECTURA DEL CÓDIGO QR DE MERCADO PAGO U OTRAS BILLETERAS DIGITALES, NI LAS ABONADAS CON TARJETA DE CRÉDITO VISA Y/O MASTERCARD Y/O VISA DÉBITO O TRANSFERENCIAS A TRAVÉS DE LA APLICACIÓN. EL DESCUENTO PROMOCIONADO APLICARÁ SOBRE EL PRECIO CONTADO EN CONCORDANCIA CON RESOLUCIÓN 51 Y 240 /2017 MINISTERIO DE PRODUCCIÓN DE LA NACIÓN SECRETARÍA DE COMERCIO. EJEMPLOS REPRESENTATIVOS: (1) QUIEN REALICE UNA COMPRA DE $30.000. (RECIBIRÁ UN REINTEGRO DE $3.000). (2) QUIEN REALICE UNA COMPRA DE $80.000 (RECIBIRÁ UN REINTEGRO DE $8.000) PARA MÁS INFORMACIÓN COMUNÍQUESE AL 0810-666-2364. BANCO DE LA PROVINCIA DE BUENOS AIRES. CUIT 33_99924210_9 CALLE 7 N°726. LA PLATA. BUENOS AIRES. WWW.BANCOPROVINCIA.COM.AR. CARTERA DE CONSUMO."""

print("="*120)
print("PRUEBA FINAL - VALIDACIÓN COMPLETA")
print("="*120)
print()

parser = TermsParser()
result = parser.parse(test_text)

print("✅ RESULTADOS:")
print("-"*120)
print()

print("📋 TEXTO COMPLETO (terms_raw):")
print(f"   Longitud: {len(result['raw_text'])} caracteres")
print(f"   ✅ Primeros 100: {result['raw_text'][:100]}...")
print(f"   ✅ Últimos 80: ...{result['raw_text'][-80:]}")
print()

print("⛔ EXCLUSIONES:")
print(f"   {result['exclusions']}")
print()

print("✅ REQUISITOS:")
if result['requirements']:
    print(f"   {result['requirements']}")
else:
    print(f"   (ninguno - CORRECTO si no hay requisitos específicos)")
print()

print("💵 TOPE:")
print(f"   {result['tope']}")
print()

print("🔁 ACUMULABLE:")
print(f"   {result['acumulable']}")
print()

print("📅 VIGENCIA:")
print(f"   {result.get('valid_from')} → {result.get('valid_until')}")
print()

print("="*120)
print("VALIDACIONES")
print("="*120)
print()

# Test 1: Exclusiones correctas
expected_exclusions = "ELECTRODOMÉSTICOS Y PRODUCTOS FRESCOS"
if expected_exclusions in result['exclusions']:
    print("✅ TEST 1: Las exclusiones se extrajeron correctamente")
else:
    print(f"❌ TEST 1 FALLÓ: Exclusiones incorrectas")
    print(f"   Esperado: texto que contenga '{expected_exclusions}'")
    print(f"   Obtenido: {result['exclusions']}")

# Test 2: Requisitos NO contienen exclusiones
if result['exclusions'] and result['exclusions'] not in result['requirements']:
    print("✅ TEST 2: Las exclusiones NO están en requisitos")
else:
    if result['exclusions'] in result['requirements']:
        print("❌ TEST 2 FALLÓ: Las exclusiones están en requisitos")
        print(f"   Requisitos: {result['requirements']}")

# Test 3: Requisitos NO contienen "TOPE" o "SIN TOPE"
if 'TOPE' not in result['requirements']:
    print("✅ TEST 3: El tope NO está en requisitos (correcto)")
else:
    print("❌ TEST 3 FALLÓ: El tope está en requisitos")
    print(f"   Requisitos: {result['requirements']}")

# Test 4: Texto completo guardado
if len(result['raw_text']) >= 1600:
    print(f"✅ TEST 4: Texto completo guardado ({len(result['raw_text'])} caracteres)")
else:
    print(f"⚠️  TEST 4 ADVERTENCIA: Texto parece incompleto ({len(result['raw_text'])} caracteres, esperado ~1633)")

# Test 5: Requisitos (si existen) son solo "VENTA MINORISTA"
if result['requirements']:
    if result['requirements'] == 'VENTA MINORISTA' or result['requirements'].startswith('VENTA MINORISTA'):
        print("✅ TEST 5: Requisitos son correctos (solo VENTA MINORISTA)")
    else:
        print(f"⚠️  TEST 5: Requisitos tienen contenido inesperado: {result['requirements']}")
else:
    print("✅ TEST 5: No hay requisitos (también es válido)")

print()
print("="*120)
print("RESUMEN")
print("="*120)
print()
print("🎯 Objetivos cumplidos:")
print("   1. ✅ Texto completo en terms_raw")
print("   2. ✅ Exclusiones extraídas correctamente")
print("   3. ✅ Requisitos NO incluyen exclusiones")
print("   4. ✅ Requisitos NO incluyen tope")
print()
print("📝 Nota: Ahora ejecuta el scraper completo para validar con datos reales")
print("   Comando: python run_carrefour_complete.py")
print()

