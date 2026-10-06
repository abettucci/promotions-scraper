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
function Chart({ points }: { points: PricePoint[] }) {
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

  return (
    <div className="flex gap-2">
      <div className="flex flex-col justify-between py-1 text-right text-[10px] font-semibold text-[#52657d]">
        <span>{ars(high)}</span>
        <span>{ars(low)}</span>
      </div>
      <div className="min-w-0 flex-1">
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-36 w-full" role="img"
          aria-label={`Evolución del precio entre ${shortDate(points[0].date)} y ${shortDate(points[points.length - 1].date)}`}>
          <polygon points={area} fill="#b8f36b" fillOpacity="0.25" />
          <polyline points={line((p) => p.max)} fill="none" stroke="#c7d4e3" strokeWidth="2" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
          <polyline points={line((p) => p.min)} fill="none" stroke="#3d6626" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
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
  if (!data || !data.tracked || data.points.length === 0) {
    return <p className="px-4 py-4 text-xs text-[#52657d] sm:px-5">Todavía no seguimos este producto. El historial se arma con la canasta diaria; si lo buscás seguido, lo sumamos.</p>
  }
  if (data.points.length < 2) {
    return <p className="px-4 py-4 text-xs text-[#52657d] sm:px-5">Empezamos a registrar este producto hoy. En unos días vas a ver cómo evoluciona su precio.</p>
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
      <Chart points={data.points} />
      <p className="text-[10px] text-[#8a9ab0]">Línea verde: tienda más barata. Línea punteada: la más cara. Precios online publicados, sin envío.</p>
    </div>
  )
}
