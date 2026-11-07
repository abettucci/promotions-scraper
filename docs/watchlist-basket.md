# Lista habitual: precios y comparación de canasta

La lista se agrupa por el árbol compartido de categorías. Los productos antiguos
sin categoría se clasifican por nombre al leerlos, sin borrar ni volver a crear
alertas. El menor precio de cada producto es el precio **publicado online**, no el
precio personalizado tras aplicar beneficios bancarios.

## Cotizaciones

- Guardar una alerta y el monitoreo existente conservan las ofertas consultadas;
  no agregan otra búsqueda para obtener la cotización.
- `Actualizar precios` consulta manualmente lotes de hasta tres alertas propias.
  El servidor resuelve las consultas guardadas; no acepta consultas arbitrarias,
  URLs ni IDs de otro usuario. La UI permite detener los siguientes lotes.
- Una consulta privada reciente se reutiliza durante una hora. Las fuentes
  mantienen además su caché existente. Las cotizaciones dejan de mostrarse a los
  tres días; se purgan los snapshots privados de más de siete días al guardar.
- Solo se acepta el mismo `product_key`, no una sustitución difusa. Para EAN/modelo
  se puede usar también el catálogo público reciente. Un error de transporte no
  rejuvenece datos anteriores. Nunca se interpreta un precio ausente o cero como
  producto gratuito.
- Los snapshots se aíslan por usuario y producto. Guardan precio publicado,
  precio de lista, tienda, URL y fecha; no medios de pago ni precios personalizados.

## Cómo se calcula

Se toma **una unidad de cada producto**, los supermercados guardados (o todos los
adaptadores disponibles si no hay selección) y los próximos siete días. Se
contrastan las promociones vigentes con los medios de pago y tiers del perfil.
El día recomendado es condicional a que se mantengan precio y stock; no es una
predicción.

Cada comercio usa una sola promoción por ticket. Se comprueban mínimo, días,
vigencia, canal, tarjeta, tier y exclusiones conocidas; el tope se aplica **una
sola vez sobre el ticket**, suponiendo que el usuario no lo consumió. Cuotas,
topes desconocidos, canal desconocido, requisitos personales no verificables y
ofertas exclusivamente presenciales/NFC no generan ahorro calculado sobre un
precio online. No se acumulan distintos beneficios. Los productos ya rebajados
solo reciben descuento adicional si la acumulación está explícitamente permitida.
Los montos monetarios se calculan con `Decimal` y redondeo a centavos.

Primero se busca el menor total entre canastas completas relevadas. Si no hay
ninguna completa, se exige una intersección idéntica de al menos el 70% de la
lista entre los comercios de mayor cobertura. Si hay una sola opción se informa
como tal, sin afirmar que vence a otras tiendas. Cada diferencia contra otra
tienda se recalcula sobre los mismos productos, incluso sus mínimos y topes.
Los subtotales incompletos nunca se presentan como precio de toda la lista.

**No se incluye envío**, preparación ni servicio. No hay precios/stock verificados
de sucursales presenciales; se indica compra online. Confirmar localidad,
adherencia, red de tarjeta y condiciones antes de pagar. Las estimaciones no son
una garantía de reintegro ni un cálculo del saldo disponible del tope.

## API y operación

- `GET /api/auth/me/watchlist`: lista propia, categoría y mejor cotización.
- `POST /api/auth/me/watchlist/refresh-prices`: `{ "alert_ids": [1, 2, 3] }`.
  Autenticado, validación estricta y cuota persistente por usuario. Se configura
  con `WATCHLIST_REFRESH_BATCHES_PER_HOUR` (60 por defecto); 100 productos
  requieren 34 lotes. Una falla individual se devuelve como `error`.
- `GET /api/auth/me/watchlist/basket`: comparación propia; máximo 60/minuto. No dispara scraping ni envía mensajes.
- El job de precios, activado por defecto (`ENABLE_PRICES_JOB=false` para desactivarlo), actualiza cotizaciones y manda por Telegram una recomendación diaria con tienda/día y precios de los productos de la lista. Respeta `notify_daily`; si no hay cotizaciones suficientes, espera al próximo ciclo.

Usa las bases SQLite y adaptadores existentes; no requiere claves nuevas ni IA,
ni incorpora un proveedor pago. La actualización manual aumenta el trabajo de
red/CPU de las fuentes existentes. `prices.db` debe permanecer en el volumen
persistente ya configurado. Las tablas nuevas se crean de forma aditiva.

Pruebas: `python -m unittest test_basket_compare test_watchlist_quotes
test_prices_catalog test_prices_alerts` y, en `frontend`, `node --test tests/*.test.mjs`
y `npm run build`.
