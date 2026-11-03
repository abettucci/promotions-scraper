"use client"

import { useQuery } from "@tanstack/react-query"
import { ExternalLink, Loader2, ScanBarcode } from "lucide-react"
import { api } from "@/lib/api"
import { PriceHistoryChart } from "@/components/PriceHistoryChart"

const ars = (value: number) => "$" + value.toLocaleString("es-AR", { maximumFractionDigits: 2 })

export function BarcodePriceLookup({ ean }: { ean: string }) {
  const { data, isFetching, error } = useQuery({
    queryKey: ["price-barcode", ean], queryFn: ({ signal }) => api.getBarcodePrices(ean, signal),
    enabled: !!ean, staleTime: 0, refetchOnMount: "always",
  })
  if (isFetching && !data) return <div role="status" className="flex items-center gap-3 rounded-2xl border border-border bg-card p-6 text-card-foreground"><Loader2 className="h-5 w-5 animate-spin text-primary" /> Consultando el mismo EAN en los supermercados…</div>
  if (error) return <div role="alert" className="rounded-2xl border border-destructive/30 bg-destructive/5 p-5 text-sm text-destructive">{(error as Error).message}</div>
  if (!data) return null
  const group = data.group
  if (!group) return <section className="rounded-2xl border border-border bg-card p-6 text-card-foreground"><div className="flex items-center gap-2 text-sm font-semibold"><ScanBarcode className="h-4 w-4 text-primary" /> No encontramos una coincidencia exacta</div><p className="mt-2 text-sm text-muted-foreground">El código {data.ean} no apareció en los catálogos consultados. No lo reemplazamos por un producto parecido. Puede que una tienda no publique ese EAN o no tenga el producto disponible.</p>{data.failed_stores.length > 0 && <p className="mt-2 text-xs text-muted-foreground">No respondieron: {data.failed_stores.join(", ")}.</p>}</section>
  return <section className="overflow-hidden rounded-2xl border border-border bg-card text-card-foreground shadow-sm" aria-label="Resultado del código escaneado">
    <header className="border-b border-border bg-secondary/50 p-5 sm:p-6"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">Coincidencia exacta · EAN {group.ean}</p><div className="mt-2 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><h2 className="display text-xl font-semibold tracking-tight sm:text-2xl">{group.name}</h2><p className="mt-1 text-sm text-muted-foreground">{group.brand || "Producto"} · {group.store_count} {group.store_count === 1 ? "comercio" : "comercios"}</p></div><p className="text-xs text-muted-foreground">Consultado {new Date(data.checked_at).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}</p></div></header>
    <div className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-3">{group.offers.map((offer, index) => <article key={offer.store} className={`rounded-xl border p-4 ${index === 0 ? "border-primary/40 bg-primary/5" : "border-border bg-background"}`}><div className="flex items-start justify-between gap-3"><h3 className="font-semibold">{offer.store_name}</h3>{index === 0 && <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold text-primary-foreground">MENOR PRECIO</span>}</div><p className="mt-2 text-2xl font-semibold tracking-tight">{ars(offer.price)}</p>{offer.multibuy && <p className="mt-1 text-xs font-medium text-primary">{offer.multibuy.label}{!offer.multibuy.exact && " · condición publicada, no calculada"}</p>}<a href={offer.url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">Ver en la tienda <ExternalLink className="h-3.5 w-3.5" /></a></article>)}</div>
    {data.history_key && <div className="border-t border-border"><div className="px-5 pt-5"><h3 className="font-semibold">Historial observado por comercio</h3><p className="mt-1 text-xs text-muted-foreground">Las consultas de este producto alimentan el seguimiento diario, hasta 100 códigos escaneados recientemente.</p></div><PriceHistoryChart productKey={data.history_key} /></div>}
    <p className="border-t border-border px-5 py-3 text-xs leading-relaxed text-muted-foreground">Precios publicados online; pueden variar por sucursal. No incluyen envío ni garantizan el precio de góndola. El historial comienza con las observaciones disponibles, no reconstruye precios anteriores.</p>
  </section>
}
