"use client"

import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { api } from "@/lib/api"
import type { PricePoint } from "@/lib/types"

const ars = (value: number) => `$${Math.round(value).toLocaleString("es-AR")}`
const shortDate = (iso: string) => {
  const [, month, day] = iso.split("-")
  return `${day}/${month}`
}

/** Línea del mínimo (verde) y del máximo (gris) entre tiendas, día por día. */
function Chart({ points, series = [] }: { points: PricePoint[]; series?: { store: string; store_name: string; points: { date: string; price: number }[] }[] }) {
  const width = 600
  const height = 150
  const pad = 8
  const low = Math.min(...points.map((p) => p.min))
  const high = Math.max(...points.map((p) => p.max))
  const span = high - low || 1
  const x = (index: number) => pad + (index / Math.max(points.length - 1, 1)) * (width - pad * 2)
  const y = (value: number) => height - pad - ((value - low) / span) * (height - pad * 2)
  const line = (pick: (p: PricePoint) => number) => points.map((p, i) => `${x(i)},${y(pick(p))}`).join(" ")
  const area = `${pad},${height - pad} ${line((p) => p.min)} ${width - pad},${height - pad}`
  const storeValues = series.flatMap((item) => item.points.map((point) => point.price))
  const storeLow = Math.min(...storeValues), storeHigh = Math.max(...storeValues)
  const storeSpan = storeHigh - storeLow || 1
  const storeY = (value: number) => height - pad - ((value - storeLow) / storeSpan) * (height - pad * 2)
  const colors = ["#3d6626", "#2758d8", "#b45309", "#a21caf", "#0891b2", "#be123c", "#475569"]

  return (
    <div className="flex gap-2">
      <div className="flex flex-col justify-between py-1 text-right text-[10px] font-semibold text-[#52657d]">
        <span>{ars(high)}</span>
        <span>{ars(low)}</span>
      </div>
      <div className="min-w-0 flex-1">
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-36 w-full" role="img"
          aria-label={`Evolución del precio entre ${shortDate(points[0].date)} y ${shortDate(points[points.length - 1].date)}`}>
          {series.length > 0 ? series.map((item, index) => <polyline key={item.store} points={item.points.map((point, i) => `${pad + (i / Math.max(item.points.length - 1, 1)) * (width - pad * 2)},${storeY(point.price)}`).join(" ")} fill="none" stroke={colors[index % colors.length]} strokeWidth="2.5" vectorEffect="non-scaling-stroke" />) : <><polygon points={area} fill="#b8f36b" fillOpacity="0.25" /><polyline points={line((p) => p.max)} fill="none" stroke="#c7d4e3" strokeWidth="2" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" /><polyline points={line((p) => p.min)} fill="none" stroke="#3d6626" strokeWidth="2.5" vectorEffect="non-scaling-stroke" /></>}
        </svg>
        <div className="flex justify-between text-[10px] text-[#8a9ab0]">
          <span>{shortDate(points[0].date)}</span>
          <span>{shortDate(points[points.length - 1].date)}</span>
        </div>
      </div>
    </div>
  )
}

export function PriceHistoryChart({ productKey }: { productKey: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["price-history", productKey],
    queryFn: () => api.getPriceHistory(productKey, 90),
    staleTime: 10 * 60 * 1000,
  })

  if (isLoading) return <p className="flex items-center gap-2 px-4 py-4 text-xs text-[#52657d] sm:px-5"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Cargando historial…</p>
  if (error) return <p className="px-4 py-4 text-xs text-[#9c4138] sm:px-5">No pudimos cargar el historial.</p>
  if (!data || !data.tracked) {
    return <p className="px-4 py-4 text-xs text-[#52657d] sm:px-5">Todavía no hay historial para este producto. El seguimiento se completa a medida que se relevan los catálogos y depende de los datos que publica cada comercio.</p>
  }
  if (data.points.length === 0) {
    return <p className="px-4 py-4 text-xs text-[#52657d] sm:px-5">No hay precios recientes registrados para este producto en el período consultado.</p>
  }
  if (data.points.length < 2) {
    return <p className="px-4 py-4 text-xs text-[#52657d] sm:px-5">Primer precio registrado: {shortDate(data.points[0].date)}. Cuando haya más observaciones vas a poder ver su evolución.</p>
  }
  const summary = data.summary
  return (
    <div className="space-y-3 px-4 py-4 sm:px-5">
      {summary && (
        <p className="text-xs text-[#52657d]">
          Hoy <b className="text-[#102a4c]">{ars(summary.today)}</b> · mínimo del período <b>{ars(summary.lowest)}</b> ({shortDate(summary.lowest_date)}) · máximo <b>{ars(summary.highest)}</b>
          {summary.change_pct !== 0 && <> · <b className={summary.change_pct < 0 ? "text-[#3d6626]" : "text-[#8f2d28]"}>{summary.change_pct > 0 ? "+" : ""}{summary.change_pct}%</b> desde {shortDate(data.points[0].date)}</>}
        </p>
      )}
      {data.changes && <div className="grid gap-2 sm:grid-cols-3">
        {[{ label: "Últimos 7 días", value: data.changes.weekly.change_pct, stores: data.changes.weekly.stores },
          { label: "Últimos 30 días", value: data.changes.monthly.change_pct, stores: data.changes.monthly.stores },
          { label: `IPC INDEC · ${data.ipc?.period ?? "sin dato"}`, value: data.ipc?.monthly_pct ?? null, stores: null }].map((item) => <div key={item.label} className="rounded-lg bg-[#f5f7fb] px-3 py-2">
            <p className="text-[10px] text-[#71839a]">{item.label}</p><p className={`mt-0.5 text-sm font-bold ${(item.value ?? 0) < 0 ? "text-[#3d6626]" : "text-[#8f2d28]"}`}>{item.value === null ? "Sin datos comparables" : `${item.value > 0 ? "+" : ""}${item.value.toLocaleString("es-AR", { maximumFractionDigits: 1 })}%`}</p>
            {item.stores !== null && <p className="text-[10px] text-[#8a9ab0]">{item.stores} tienda{item.stores === 1 ? "" : "s"} comparables</p>}
          </div>)}
      </div>}
      {data.ipc && <p className="text-[10px] text-[#8a9ab0]">El IPC es mensual y nacional; se muestra como referencia, no como inflación propia de este producto.</p>}
      <Chart points={data.points} series={data.series} />
      {data.series?.length ? <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-[#52657d]">{data.series.map((item, index) => <span key={item.store} className="inline-flex items-center gap-1.5"><i className="h-0.5 w-3" style={{ backgroundColor: ["#3d6626", "#2758d8", "#b45309", "#a21caf", "#0891b2", "#be123c", "#475569"][index % 7] }} />{item.store_name}</span>)}</div> : <p className="text-[10px] text-[#8a9ab0]">Línea verde: tienda más barata. Línea punteada: la más cara.</p>}
      <p className="text-[10px] text-[#8a9ab0]">Precios online observados, sin envío. Las líneas se interrumpen cuando la tienda deja de confirmar el precio.</p>
    </div>
  )
}
