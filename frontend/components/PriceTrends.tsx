"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { PriceIndexResponse, PriceTrendsResponse } from "@/lib/types"

const COLORS = ["#6366f1", "#64748b", "#10b981", "#0369a1", "#0ea5e9", "#f43f5e", "#dc2626", "#ca8a04", "#f97316", "#a855f7"]
const percent = (value: number) => `${value > 0 ? "+" : ""}${value.toLocaleString("es-AR", { maximumFractionDigits: 1 })}%`

function PriceIndexChart({ data }: { data: PriceIndexResponse }) {
  const width = 900, height = 310, pad = { top: 14, right: 14, bottom: 22, left: 46 }
  const values = data.series.flatMap((series) => series.points.map((point) => point.index).filter((value): value is number => value !== null))
  const low = Math.min(0, ...values), high = Math.max(0, ...values)
  const span = high - low || 1
  const pointCount = Math.max(2, ...data.series.map((item) => item.points.length))
  const x = (index: number) => pad.left + (index / Math.max(pointCount - 1, 1)) * (width - pad.left - pad.right)
  const y = (value: number) => pad.top + ((high - value) / span) * (height - pad.top - pad.bottom)
  const ticks = [high, high / 2, 0, low / 2, low].filter((value, index, items) => items.findIndex((v) => Math.abs(v - value) < 0.01) === index)

  if (!values.length) return <div className="grid h-64 place-items-center rounded-xl bg-background px-5 text-center text-sm text-muted-foreground">Todavía no hay suficientes semanas comparables para dibujar el índice. El historial se va a completar con las corridas periódicas.</div>

  return <div className="overflow-hidden rounded-xl bg-background p-2 sm:p-4">
    <svg viewBox={`0 0 ${width} ${height}`} className="h-64 w-full" role="img" aria-label="Índice histórico semanal de precios por rubro">
      {ticks.map((tick) => <g key={tick}><line x1={pad.left} x2={width-pad.right} y1={y(tick)} y2={y(tick)} stroke={tick === 0 ? "#94a3b8" : "#e2e8f0"} strokeDasharray={tick === 0 ? "" : "3 5"} /><text x={pad.left-8} y={y(tick)+4} textAnchor="end" fontSize="11" fill="#64748b">{percent(tick)}</text></g>)}
      {data.series.map((line, seriesIndex) => {
        const segments: string[][] = []
        for (const [index, point] of line.points.entries()) {
          if (point.index === null) continue
          if (!segments.length || line.points[index - 1]?.index === null) segments.push([])
          segments[segments.length - 1].push(`${x(index)},${y(point.index)}`)
        }
        return segments.filter((segment) => segment.length > 1).map((points, segmentIndex) => <polyline key={`${line.category}-${segmentIndex}`} points={points.join(" ")} fill="none" stroke={COLORS[seriesIndex % COLORS.length]} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />)
      })}
      <text x={pad.left} y={height-2} fontSize="11" fill="#64748b">{new Date(data.from + "T12:00:00").toLocaleDateString("es-AR", { month: "short", year: "2-digit" })}</text>
      <text x={width-pad.right} y={height-2} textAnchor="end" fontSize="11" fill="#64748b">{new Date(data.to + "T12:00:00").toLocaleDateString("es-AR", { month: "short", year: "2-digit" })}</text>
    </svg>
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2 border-t border-border pt-3">{data.series.map((line, index) => <span key={line.category} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"><i className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />{line.category}</span>)}</div>
  </div>
}

export function PriceTrends() {
  const [period, setPeriod] = useState<"year" | "3m" | "6m" | "1y" | "all">("year")
  const [currency, setCurrency] = useState<"ars" | "usd_official" | "usd_blue">("ars")
  const [days, setDays] = useState<7 | 30>(30)
  const { data: index, error: indexError, isFetching: indexLoading } = useQuery({
    queryKey: ["price-index", period, currency], queryFn: () => api.getPriceIndex(period, currency), staleTime: 300_000,
  })
  const { data, error, isFetching } = useQuery({
    queryKey: ["price-trends", days], queryFn: () => api.getPriceTrends(days), staleTime: 300_000,
  })
  const rangeOptions = useMemo(() => [
    { value: "year" as const, label: String(new Date().getFullYear()) },
    { value: "3m" as const, label: "3M" }, { value: "6m" as const, label: "6M" },
    { value: "1y" as const, label: "1A" }, { value: "all" as const, label: "Todo" },
  ], [])

  return <div className="space-y-5">
    <section className="space-y-4 rounded-2xl border border-border bg-card p-5 text-card-foreground sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Evolución</p><h2 className="display mt-1 text-2xl font-semibold tracking-tight">Índice de precios por rubro</h2></div><div className="flex flex-wrap gap-2"><div className="flex gap-1 rounded-full border border-border bg-background p-1">{rangeOptions.map((option) => <button key={option.value} type="button" aria-pressed={period === option.value} onClick={() => setPeriod(option.value)} className={`rounded-full px-3 py-2 text-xs font-semibold ${period === option.value ? "bg-foreground text-background" : "text-muted-foreground"}`}>{option.label}</button>)}</div><div className="flex gap-1 rounded-full border border-border bg-background p-1">{([{ value: "ars", label: "ARS" }, { value: "usd_official", label: "USD oficial" }, { value: "usd_blue", label: "USD blue" }] as const).map((option) => <button key={option.value} type="button" aria-pressed={currency === option.value} onClick={() => setCurrency(option.value)} className={`rounded-full px-3 py-2 text-xs font-semibold ${currency === option.value ? "bg-foreground text-background" : "text-muted-foreground"}`}>{option.label}</button>)}</div></div></div>
      {indexLoading && <p role="status" className="text-sm text-muted-foreground">Consultando historial semanal…</p>}
      {indexError && <p role="alert" className="text-sm text-red-600">No pudimos cargar el índice histórico.</p>}
      {index && <><PriceIndexChart data={index} /><p className="text-xs text-muted-foreground">Índice encadenado desde 0% al inicio del período · {currency === "ars" ? "precios en ARS" : `precios convertidos por cotización vendedora ${currency === "usd_blue" ? "blue" : "oficial"}`} · datos hasta {new Date(index.to + "T12:00:00").toLocaleDateString("es-AR")}{index.exchange_source && ` · fuente cambiaria: ${index.exchange_source}`}</p></>}
    </section>

    <section className="space-y-4 rounded-2xl border border-border bg-card p-5 text-card-foreground sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Últimos {days} días</p><h2 className="display mt-1 text-2xl font-semibold tracking-tight">Aumentos de precios e inflación</h2></div><div className="flex gap-2">{([7, 30] as const).map((n) => <button key={n} type="button" aria-pressed={days === n} onClick={() => setDays(n)} className={`rounded-full border px-3 py-2 text-xs font-semibold ${days === n ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>{n} días</button>)}</div></div>
      {isFetching && <p role="status" className="text-sm text-muted-foreground">Actualizando comparación…</p>}
      {error && <p role="alert" className="text-sm text-red-600">No pudimos cargar la evolución de precios.</p>}
      {data && <>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <article className="rounded-xl border border-border p-4"><p className="text-sm font-semibold">Canasta relevada</p><p className={`my-2 text-3xl font-bold ${(data.basket.change_pct ?? 0) < 0 ? "text-emerald-600" : "text-rose-600"}`}>{data.basket.change_pct === null ? "—" : percent(data.basket.change_pct)}</p><p className="text-xs text-muted-foreground">{data.basket.compared_products} de {data.basket.baseline_products} productos · cobertura {data.basket.coverage_pct}%</p></article>
          {data.categories.map((row, index) => <article key={row.category} className="rounded-xl border border-border p-4"><h3 className="flex items-center gap-2 text-sm font-semibold"><i className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />{row.category}</h3><p className={`my-2 text-3xl font-bold ${(row.change_pct ?? 0) < 0 ? "text-emerald-600" : "text-rose-600"}`}>{row.change_pct === null ? "Sin datos suficientes" : percent(row.change_pct)}</p><p className="text-xs text-muted-foreground">{row.compared_products}/{row.baseline_products} productos base · cobertura {row.coverage_pct}%</p>{row.vs_inflation_pp !== null && <p className="mt-2 text-xs font-semibold">{row.vs_inflation_pp > 0 ? "+" : ""}{row.vs_inflation_pp.toLocaleString("es-AR")} p.p. vs IPC</p>}</article>)}
        </div>
        {data.ipc ? <p className="rounded-xl bg-background p-4 text-sm">IPC Nacional INDEC ({data.ipc.period}): <b>{percent(data.ipc.monthly_pct)}</b> mensual. {days === 7 && <>Equivalente semanal estimado: <b>{percent(data.ipc.comparison_pct)}</b>. </>}Comparación de la canasta observada: <b>{data.basket.vs_inflation_pp === null ? "sin datos suficientes" : `${data.basket.vs_inflation_pp > 0 ? "+" : ""}${data.basket.vs_inflation_pp.toLocaleString("es-AR")} p.p.`}</b>.</p> : <p className="rounded-xl bg-background p-4 text-sm text-muted-foreground">No pudimos actualizar el IPC oficial. Los cambios observados en precios siguen disponibles.</p>}
      </>}
      <details className="text-xs leading-relaxed text-muted-foreground"><summary className="cursor-pointer font-semibold">Metodología y límites</summary><p className="mt-2">El índice del catálogo compara el mismo producto en el mismo comercio, promedia primero las tiendas por producto y luego da el mismo peso a cada producto. Sólo muestra períodos con al menos {data?.min_products ?? 5} productos comparables y {data?.min_coverage_pct ?? 80}% de cobertura. El IPC es el último dato mensual oficial publicado por INDEC; para 7 días se muestra una equivalencia estimada, no una medición semanal oficial. La canasta relevada no reemplaza la canasta representativa del IPC. Precios online observados: pueden variar por sucursal y no incluyen envío.</p></details>
      <p className="text-[11px] text-muted-foreground">Fuente IPC: INDEC · serie de Nivel General Nacional, base diciembre de 2016.</p>
      {index && <details className="text-xs leading-relaxed text-muted-foreground"><summary className="cursor-pointer font-semibold">Cómo armamos el índice histórico</summary><p className="mt-2">{index.method} Sólo incluimos productos con identidad estable y comercios que vuelven a confirmar su precio. Si falta cobertura suficiente, dejamos un corte en la línea en lugar de completar con productos distintos. La serie comienza cuando PromoAR empezó a guardar observaciones comparables.</p></details>}
    </section>
  </div>
}
