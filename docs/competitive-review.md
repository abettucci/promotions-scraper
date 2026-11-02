# Descuentito y Calculabot frente a PromoAR

Revisión: 31/10/2026. Fuentes públicas y código local; sin autenticación,
sin importar sus promociones ni reproducir sus assets. Las páginas recuperadas
por el buscador pueden ser snapshots: no se verificó la vigencia de descuentos
individuales, cobertura real, tráfico, calidad de sus scrapers ni backend privado.

## Descuentito — https://descuentito.ar/

La página se presenta como descuentos de supermercados de CABA. La versión
indexada expone selección por día, configuración de medios de pago, restricciones,
topes y advertencia de verificar en las fuentes oficiales. También hay una página
de accesos rápidos a supermercados: https://descuentito.ar/supermercados.

PromoAR ya tiene filtros por día, medios de pago en perfil, condiciones y enlaces,
por lo que esas no son funciones nuevas que debamos duplicar. Lo aprovechable es
un onboarding más corto y una vista pública de semana muy fácil de recorrer.
Su alcance geográfico explícito es una buena señal: PromoAR debería distinguir
mejor cobertura nacional, provincia, sucursal y formato, sin inferirla si falta.

| Propuesta | Implementación sugerida | Dificultad | Costo adicional |
|---|---|---|---|
| Onboarding de medios de pago | Asistente corto reutilizando perfil y tiers actuales | Baja/media | Sin API paga; principalmente desarrollo |
| Semana de descuentos | Vista de 7 días sobre nuestras promos vigentes y perfil | Media | Consultas a DB existente; sin proveedor nuevo |
| Cobertura visible | Etiquetas con datos reales y “sin dato” cuando falten | Media/alta | Depende de mejorar extracción por sucursal |

No se probó su wizard autenticado ni se pudo confirmar dónde persiste preferencias.

## Calculabot — https://www.calculabot.com/

La página indexada ofrece un top 5 por día, navegación por supermercado y tarjeta,
y una columna “Ticket Ideal” junto al descuento y tope. La apertura directa tuvo
timeout en el lector web y HTTP 503 en una segunda consulta directa durante esta
revisión; las conclusiones de funciones se basan en esa
versión pública indexada, no en haber probado todas sus interacciones en vivo.

PromoAR ya filtra por supermercado, banco y día. La diferencia útil es convertir
un porcentaje/tope en una cifra accionable y ofrecer un resumen diario compacto.

| Propuesta | Implementación sugerida | Dificultad | Costo adicional |
|---|---|---|---|
| Ticket para alcanzar el tope | Para porcentaje y tope conocidos: tope / tasa; respetar compra mínima y explicitar período | Baja/media | Cálculo local, sin IA |
| Top 5 personalizado | Ordenar por ahorro para un monto ingresado, no sólo por porcentaje | Media | DB actual y cálculo determinista |
| Simular una compra | Importe, medio de pago y promo; devolver ahorro y neto estimados | Media | Sin servicio nuevo; requiere pruebas de reglas |

No debe inventarse un ticket ideal para cuotas, topes desconocidos o promociones
sin tope. El cálculo exige aclarar si se supone el tope intacto: no conocemos cuánto
consumió el usuario de un tope mensual/semanal compartido. No acumular descuentos
bancarios y billeteras sin evidencia explícita de acumulación.

## Orden recomendado después de catálogo y escáner

1. Ticket para alcanzar el tope, con estados “no calculable” y condiciones claras.
2. Simulador por monto y ranking por ahorro efectivo, respetando perfil/tiers.
3. Resumen semanal y onboarding corto, sin duplicar la configuración existente.

Son recomendaciones, no funciones implementadas en este cambio. No se agregó
dependencia de esos comparadores ni se consumieron créditos de Gluecrawl/modelos.
Los costos de desarrollo son estimaciones relativas, no presupuestos de proveedores.
