# Mis compras: cruce con promociones históricas

La función anterior de lista habitual no registraba consumos. `scrape_history`
sólo guardaba estado y cantidad de resultados por ejecución. `promotions` conserva
filas vencidas, pero su UPSERT puede sobrescribir porcentaje, fechas y legales.
Ninguna de esas tablas era un historial versionado de condiciones ni una métrica
de compras realizadas.

## Uso

En el menú principal y de usuario: **Mis compras** (`/purchases`). Se carga fecha,
comercio, monto original antes del descuento y, opcionalmente, banco, billetera,
tipo de pago, canal y descuento/reintegro ya recibido. No se importan consumos de
otras aplicaciones ni movimientos bancarios. No se guarda PAN, CVV ni ticket.

El reporte permite filtrar un período de hasta 366 días (90 por defecto), ver
compras y condiciones observadas en ese día y eliminar registros propios. Se
limita a 5000 compras por cuenta, con paginación y clave de idempotencia para
reintentos. No se envían alertas al registrar compras ni al actualizar el cruce.

## Fórmulas y límites

- **Compras en día de promoción**: una compra con al menos una promoción
  porcentual observada para el mismo comercio y día, cuya vigencia y día de
  aplicación sean explícitos. No presupone que se pagó con el medio requerido.
- **Porcentaje de compras en día de promo**: compras anteriores dividido por las
  compras con evidencia diaria suficiente. Las compras sin histórico verificable
  se muestran por separado: no se cuentan como compras sin promoción.
- **Distribución por porcentaje publicado**: cada compra cuenta una vez. Si hay
  varios porcentajes distintos, va a “Varios porcentajes”. `Hasta 30%` no se
  convierte en un 30% garantizado. Las cuotas no son un porcentaje de ahorro.
- **Posible coincidencia de pago**: se cruzan sólo banco/billetera, tipo de tarjeta
  y canal declarados en esa compra, nunca el perfil actual como prueba del pasado.
  No verifica tier, red, sucursal, productos excluidos, mínimos ni saldo del tope:
  no es una adjudicación de beneficio ni una estimación de ahorro perdido.
- **Ahorro recibido declarado**: suma de los montos ingresados expresamente por
  el usuario. La tasa efectiva usa sólo compras con descuento informado:
  suma(descuento recibido) / suma(monto original) × 100. Un cero explícito no es un
  dato ausente. Los montos se guardan en centavos enteros.

No se asegura que todas las promociones del comercio estén cubiertas. “Sin
porcentaje registrado” se limita a los datos observados, no afirma que no hubiera
otros beneficios. La granularidad es diaria, no identifica condiciones exactas
a la hora de pago. La sucursal/localidad puede cambiar el alcance de la promoción.

## Histórico durable

`promotion_versions` guarda snapshots inmutables deduplicados por SHA-256 del
contenido público. `promotion_observations` referencia la última versión por
identidad y fecha argentina. Las actualizaciones no modifican versiones previas;
una promoción sin cambios agrega una observación diaria, no otro bloque de legales.
El camino de caché verificado por una respuesta reciente también registra evidencia.

Las tablas se crean en `promotions.db` y viajan con la publicación existente de
esa base desde GitHub Actions. La API copia sólo la historia pública a `users.db`,
que vive en el Railway Volume; allí también residen las compras privadas. No se
copian usuarios ni compras a `promotions.db` ni al repo. El arranque, las corridas
del scheduler Railway, el alta de compra y el POST de actualización sincronizan
el archivo. Una nueva base de promociones no elimina historia ya archivada.

El bootstrap de filas antiguas y la restauración de snapshots externos se marcan
`legacy` y conservan su fecha original; no cuentan como observación histórica
verificada ni como un scrapeo nuevo. **No se pueden recuperar retrospectivamente
versiones que ya se sobrescribieron antes de activar este registro.**

## Seguridad y operación

Todos los endpoints son privados y reutilizan la sesión JWT existente. La
identidad procede de `get_current_user`, las consultas comprueban el dueño en SQL,
los cuerpos prohíben campos extra y los IDs de compra son UUID aleatorios. Hay
cuotas persistentes por cuenta: 60 escrituras/h, 30 reportes/min, 6 sincronizaciones/h.
No se agregan logs de compras, importes, datos de pago o cuerpos HTTP; los errores
de SQLite se devuelven con mensajes genéricos. La UI usa renderizado de texto React,
no HTML de los legales. GET no sincroniza historia ni dispara scraping.

No exige claves nuevas, IA ni servicios pagos. Crece el almacenamiento de SQLite
y se suma trabajo local de versionado/copias; debe mantenerse el volumen de
`USERS_DB_DIR`. No modifica variables remotas ni despliega por sí mismo.

Endpoints: `GET/POST /api/auth/me/purchases`, `GET /api/auth/me/purchases/options`,
`DELETE /api/auth/me/purchases/{uuid}`, `POST /api/auth/me/purchases/refresh-history`.

Validación: `python -m unittest test_purchases test_scrape_result_cache`;
en `frontend`, `node --test tests/*.test.mjs`, `npm run build` y lint de los archivos.
