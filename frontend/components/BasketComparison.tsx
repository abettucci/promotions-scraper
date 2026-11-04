"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { CalendarDays, ChevronDown, CreditCard, Loader2, ShoppingBasket, Truck } from "lucide-react"
import { api } from "@/lib/api"
import { money, quoteDate } from "@/lib/watchlist"
import type { BasketOption } from "@/lib/types"

const conditionText = (value: string | string[] | null | undefined) => Array.isArray(value) ? value.join(" · ") : value || "No informado"

function Conditions({ option }: { option: BasketOption }) {
  if (!option.promotion) return null
  const promo = option.promotion
  return <details className="mt-2 text-xs text-muted-foreground"><summary className="cursor-pointer font-semibold text-primary">Ver beneficio y condiciones del cálculo</summary><div className="mt-2 space-y-2 rounded-lg border border-border p-3"><p className="font-semibold text-foreground">{promo.title || promo.discount}</p><p>Tope: {promo.tope} · Compra mínima: {promo.min_purchase || "no informada"}</p><p>Descuento estimado sobre {option.eligible_count} productos; el resto conserva su precio publicado.</p><p>Requisitos: {conditionText(promo.requirements)}</p><p>Exclusiones: {conditionText(promo.exclusions)}</p><p>Supone el tope sin uso previo y cumplimiento de requisitos, red de tarjeta y alcance territorial. No se sumó otro beneficio.</p></div></details>
}

export function BasketComparison({ token, userId, productCount }: { token: string; userId: number; productCount: number }) {
  const query = useQuery({ queryKey: ["watchlist-basket", userId], queryFn: () => api.getWatchlistBasket(token),
    enabled: productCount > 0, staleTime: 60_000, retry: false })
  if (!productCount) return null
  const data = query.data
  const reference = data?.reference
  return <section aria-labelledby="basket-heading" className="overflow-hidden rounded-2xl border border-border bg-card text-card-foreground">
    <details open className="group/basket">
    <summary className="flex cursor-pointer list-none items-center justify-between gap-4 border-b border-border p-5 outline-none marker:hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary sm:p-6 [&::-webkit-details-marker]:hidden"><div><p className="mb-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Tu canasta, comparada</p><h2 id="basket-heading" className="display text-2xl font-semibold tracking-tight">Dónde y cuándo conviene comprar</h2><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Próximos siete días, con tus medios de pago y supermercados guardados. Una unidad de cada producto; valores online estimados.</p></div><span className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-semibold text-primary"><span className="group-open/basket:hidden">Expandir</span><span className="hidden group-open/basket:inline">Contraer</span><ChevronDown aria-hidden="true" className="h-4 w-4 transition-transform group-open/basket:rotate-180" /></span></summary>
    <div className="space-y-5 p-5 sm:p-6">
      <div className="flex justify-end"><Link href="/profile" className="text-sm font-semibold text-primary">Revisar mis medios de pago →</Link></div>
      <p className="flex items-center gap-2 rounded-xl border border-border bg-secondary px-4 py-3 text-sm font-semibold text-secondary-foreground"><Truck className="h-5 w-5 shrink-0" /> Falta considerar el costo de envío y posibles cargos de servicio.</p>
      {query.isFetching && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Calculando con los precios relevados…</p>}
      {query.error && <p role="alert" className="text-sm text-red-600">{(query.error as Error).message} <button type="button" onClick={() => query.refetch()} className="font-semibold underline">Reintentar</button></p>}
      {data && <>
        {reference ? <article className="rounded-xl border border-border bg-secondary p-5 text-secondary-foreground">
          <div className="flex flex-wrap items-start justify-between gap-4"><div><span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide"><ShoppingBasket className="h-4 w-4" />{data.reference_kind === "complete" ? "Menor total entre canastas completas relevadas" : data.reference_kind === "partial" ? "Menor total para los productos comunes" : "Única opción con esta cobertura; sin comparación suficiente"}</span><h3 className="display mt-2 text-2xl font-semibold">{reference.store_name}</h3><p className="mt-1 text-sm">{reference.priced_count} de {data.product_count} productos {data.reference_kind === "complete" ? "· canasta completa" : "· comparación parcial"}</p></div><div className="sm:text-right"><p className="text-xs font-medium">Total estimado · sin envío</p><p className="mt-1 text-3xl font-semibold tracking-tight">{money(reference.total)}</p><p className="mt-1 text-sm">{reference.savings > 0 ? `${money(reference.savings)} de beneficio estimado` : "Sin beneficio adicional calculable"}</p><p className="text-xs text-muted-foreground">Antes del beneficio: {money(reference.subtotal)}</p></div></div>
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-border pt-4 text-sm"><span className="inline-flex items-center gap-2"><CalendarDays className="h-4 w-4" />{reference.day} {quoteDate(reference.date)}</span><span className="inline-flex items-center gap-2"><CreditCard className="h-4 w-4" />{reference.payment}</span><span className="rounded-full bg-card px-2.5 py-1 text-xs font-semibold text-card-foreground">Compra online</span></div>
          {reference.missing.length > 0 && <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">{reference.missing.length} productos fuera de esta comparación</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-xs">{reference.missing.map((name, i) => <li key={i}>{name}</li>)}</ul></details>}
          <Conditions option={reference} />
        </article> : <p className="rounded-xl bg-secondary p-5 text-sm text-secondary-foreground">Todavía no hay precios suficientes para recomendar toda o gran parte de tu lista. Usá “Actualizar precios” arriba. Nunca contamos un producto sin precio como si costara $0.</p>}

        {data.options.length > 0 && <div><h3 className="mb-2 text-sm font-semibold">Alternativas y diferencias sobre los mismos productos</h3><p className="mb-4 text-xs text-muted-foreground">Los subtotales parciales no equivalen a una canasta completa. La diferencia se recalcula solo para los productos comunes, con su mejor día y beneficio compatible.</p><div className="space-y-3">{data.options.map((option) => <article key={option.store} className="rounded-xl border border-border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-semibold">{option.store_name} <span className="ml-1 rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-secondary-foreground">Online</span></h4><p className="mt-1 text-xs text-muted-foreground">{option.priced_count}/{data.product_count} productos · {option.day} {quoteDate(option.date)}</p><p className="mt-1 max-w-xl text-xs text-muted-foreground">{option.payment}</p></div><div className="text-right"><p className="text-lg font-semibold">{money(option.total)}</p><p className="text-xs text-muted-foreground">{option.priced_count === data.product_count ? "Canasta completa" : "Subtotal parcial"} · sin envío</p><p className="mt-1 text-xs">Beneficio estimado: {money(option.savings)}</p></div></div>
          {option.comparison && <details className="mt-3 rounded-lg bg-muted p-3 text-xs text-muted-foreground"><summary className="cursor-pointer font-semibold text-foreground">{money(Math.abs(option.comparison.difference))} {option.comparison.difference < 0 ? "menos" : option.comparison.difference > 0 ? "más" : "de diferencia"} que {reference?.store_name} en {option.comparison.product_count} productos comunes</summary><div className="mt-2 space-y-1"><p>{option.store_name}: {money(option.comparison.store_total)} · {option.comparison.store_day} · {option.comparison.store_payment}</p><p>{reference?.store_name}: {money(option.comparison.reference_total)} · {option.comparison.reference_day} · {option.comparison.reference_payment}</p><p>Se recalcularon mínimos y topes para ese subconjunto. No es una diferencia por toda la lista si faltan productos.</p></div></details>}
          {option.missing.length > 0 && <details className="mt-2 text-xs text-muted-foreground"><summary className="cursor-pointer">Sin precio reciente para {option.missing.length} productos</summary><p className="mt-2">{option.missing.join(" · ")}</p></details>}
          <Conditions option={option} />
        </article>)}</div></div>}
        {data.unsupported_favorites.length > 0 && <p className="text-xs text-muted-foreground">Aún no relevamos precios de estos favoritos: {data.unsupported_favorites.join(", ")}. Tener sus promociones no significa tener su catálogo de productos.</p>}
        <details className="text-xs leading-relaxed text-muted-foreground"><summary className="cursor-pointer font-semibold">Supuestos y límites de la comparación</summary><ul className="mt-2 list-disc space-y-1 pl-4">{data.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul><p className="mt-2">“Gran parte” exige al menos 70% de la lista sobre los mismos productos. No se compararon precios de sucursales presenciales. Confirmá stock, localidad, exclusiones y condiciones antes de pagar.</p></details>
      </>}
    </div>
    </details>
  </section>
}
