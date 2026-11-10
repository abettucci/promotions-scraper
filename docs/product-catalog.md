# Catálogo, escáner y evolución de precios

## Comportamiento

`/precios` permite explorar los productos identificados por EAN, modelo o SKU de tienda que ya
relevó el proceso de precios, ordenar y filtrar por rubro sin consultar comercios.
Cada oferta guarda su última fecha de confirmación aunque el precio no cambie.
Sólo se listan ofertas en stock confirmadas en los últimos 3 días. La ficha
muestra los precios publicados, sin reintegros bancarios, personalización ni envío.
“Actualizar en vivo” abre la búsqueda existente con promociones del día.
No se importa información de Pricely ni de los otros comparadores.

Además de la canasta fija, un proceso independiente recorre los catálogos de
Carrefour, Día, Jumbo, Disco, Vea, ChangoMás y Coto. Guarda el cursor de cada
comercio en `prices.db`, procesa páginas de hasta 50 publicaciones y reanuda
después de un reinicio. VTEX limita la paginación, por lo que se subdividen
intervalos de precios hasta que cada consulta sea paginable; las fronteras se
superponen y la escritura es idempotente. Coto usa el cursor `No` de Endeca.

Se guardan ofertas con precio positivo, enlace e identidad estable (EAN o SKU
propio del comercio); un SKU sin EAN no se fusiona con otra tienda. Los
comercios pueden cambiar su catálogo, omitir productos, limitar consultas o no
publicar precio/identificador. Si una página falla, se reintenta sin avanzar;
un intervalo con más de 2400 productos al mismo precio queda pendiente y no se
marca el recorrido como completo. `GET /api/prices/catalog/status` muestra
avance, errores y particiones pendientes. La primera pasada y las actualizaciones
llevan tiempo; sólo se muestran ofertas confirmadas dentro de la ventana de
frescura indicada.

El escáner carga ZXing bajo demanda y decodifica la cámara en el dispositivo.
Admite GTIN-8, UPC-A, EAN-13 y GTIN-14 con verificador válido; sólo se envía el
número. No hay subida de fotos ni consultas a IA. Exige HTTPS (o localhost),
permiso del navegador y cámara disponible. Incluye ingreso manual, diálogo con
foco contenido y cierre por Escape. Cierra la cámara al terminar, cerrar el
diálogo, desmontarse o salir de la pestaña; también libera permisos concedidos
después de cerrar. Un código desconocido no se reemplaza por un producto similar.

## Activación en Railway

- Persistir `USERS_DB_DIR` en el volumen existente; allí vive `prices.db`.
- El recolector y las recomendaciones de canasta quedan activados por defecto.
  `ENABLE_PRICES_JOB=false` los desactiva.
- `PRICES_BASKET_EVERY_HOURS` mantiene el intervalo existente (20 h por defecto).
- `PRICES_CATALOG_GROUPS_PER_QUERY=12` conserva más resultados del conjunto que
  ya devolvían las tiendas (antes se conservaban 3). Rango 1–30. No incrementa
  la cantidad de requests por búsqueda ni el límite de 8 ofertas del adaptador.
- `PRICES_CATALOG_RATE_LIMIT_MAX=300` limita las lecturas por ventana/IP (HMAC,
  sin guardar IP cruda); usa `PRICES_RATE_LIMIT_WINDOW_SECONDS` (3600 s).
- `ENABLE_SUPERMARKET_CATALOG_JOB=true` habilita el recorrido paginado mientras
  `ENABLE_PRICES_JOB` esté activo, en un hilo separado de las alertas. Ajustes:
  `CATALOG_CRAWL_PAGE_SIZE=50`, `CATALOG_CRAWL_DELAY_SECONDS=1.5`,
  `CATALOG_CRAWL_EVERY_HOURS=20` y `CATALOG_CRAWL_RETRY_SECONDS=300`.
  El volumen necesita espacio para ofertas e historial del catálogo ampliado.
- La migración SQLite es aditiva e idempotente. El catálogo arranca vacío hasta
  la primera recolección: no se presenta como recién confirmado un dato viejo.
- Prueba manual sin enviar alertas: `python scripts/collect_prices_catalog.py
  --max-queries 2 --groups 12`. Escribe en el `USERS_DB_DIR` configurado. El comando
  está pensado para diagnóstico y no posterga la próxima corrida completa; el
  recolector programado recorre la canasta completa.

No requiere nuevas claves, servicios pagos ni proveedores de IA. Aumenta el
almacenamiento de ofertas y resultados guardados. La cobertura depende de lo
publicado para la ubicación por defecto de cada tienda, no de cada sucursal.

## API pública

- `GET /api/prices/catalog`: `q`, `rubric`, `sort` (`recent`, `price_asc`,
  `price_desc`, `name`), `page`, `page_size`, `ean`. Devuelve productos, total,
  facetas y ventana de frescura. Paginación y longitudes acotadas.
- `GET /api/prices/catalog/product?key=ean:...`: ofertas recientes de la identidad
  exacta, o 404 si no existe/no quedan ofertas recientes.
- `GET /api/prices/trends?days=7|30`: variaciones de un panel comparable por rubro.
  Los tres endpoints son lecturas sin scraping ni notificaciones. Responden
  422 ante datos inválidos, 429 por cuota y 503 genérico ante errores de SQLite.

## Metodología experimental

La base es el conjunto de productos/tiendas con observación histórica en la
fecha base o hasta 8 días antes (se permite carry-forward porque el histórico
registra cambios y un latido cada 7 días). Se compara cada identidad **en la misma
tienda** contra una oferta actual confirmada en los últimos 3 días. Las tiendas
pesan igual dentro de cada producto, y los productos pesan igual dentro del rubro.
La variación sólo se publica con al menos 5 productos comparados y 80% de
cobertura de los productos de la base. No se sustituyen faltantes silenciosamente.
No se reconstruye historia inexistente ni se mide inflación oficial. Tampoco es
todavía una canasta representativa o un índice encadenado de composición fija:
el panel base se determina para cada período y se informa su cobertura.

## Validación

- `python -m unittest test_prices_catalog test_prices_alerts`
- Desde `frontend`: `node --test tests/*.test.mjs` (Node 22.18+ para tests TS)
- Desde `frontend`: `npm run build`
- Antes de desplegar: comprobar cámara real y permisos en Android/iOS, tema
  claro/oscuro, lectura de un EAN presente y otro ausente, y guardado en lista.
