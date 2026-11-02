"use client"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function PriceTrends() {
  const [days, setDays] = useState<7 | 30>(30)
  const { data, error, isFetching } = useQuery({ queryKey: ["price-trends", days], queryFn: () => api.getPriceTrends(days), staleTime: 300_000 })
  return <section id="evolucion" className="space-y-4 rounded-2xl border border-border bg-card p-5 text-card-foreground sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Panel experimental</p><h2 className="display mt-1 text-2xl font-semibold tracking-tight">Cómo se mueven los precios</h2></div><div className="flex gap-2">{([7, 30] as const).map((n) => <button key={n} type="button" aria-pressed={days === n} onClick={() => setDays(n)} className={`rounded-full border px-3 py-2 text-xs font-semibold ${days === n ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>{n} días</button>)}</div></div>
    {isFetching && <p role="status" className="text-sm text-muted-foreground">Consultando observaciones…</p>}
    {error && <p role="alert" className="text-sm text-red-600">No pudimos cargar la evolución de precios.</p>}
    {data && <>
      {data.categories.length === 0 && <p className="rounded-xl bg-secondary p-4 text-sm text-secondary-foreground">Estamos reuniendo observaciones comparables. No mostramos una variación de {days} días sin datos del período base.</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{data.categories.map((row) => <article key={row.category} className="rounded-xl border border-border p-4"><h3 className="text-sm font-semibold">{row.category}</h3><p className="my-2 text-2xl font-semibold">{row.change_pct === null ? "Sin datos suficientes" : `${row.change_pct > 0 ? "+" : ""}${row.change_pct.toLocaleString("es-AR")}%`}</p><p className="text-xs text-muted-foreground">{row.compared_products} de {row.baseline_products} productos base · cobertura {row.coverage_pct}%</p></article>)}</div>
      <details className="text-xs leading-relaxed text-muted-foreground"><summary className="cursor-pointer font-semibold">Metodología y límites</summary><p className="mt-2">Comparamos precios publicados del mismo producto en la misma tienda entre {data.baseline} y {data.as_of}. Promediamos variaciones por tienda y luego damos el mismo peso a cada producto. Exigimos al menos {data.min_products} productos y {data.min_coverage_pct}% de cobertura de los productos base. No reemplazamos faltantes por otros productos ni sumamos reintegros bancarios. Es un panel observacional de nuestro catálogo, no una canasta representativa ni inflación oficial. Los precios online pueden variar por sucursal; no incluyen envío.</p></details>
    </>}
  </section>
}
