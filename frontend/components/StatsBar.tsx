"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { Tag, Building2, Landmark, Clock } from "lucide-react"
import type { Stats } from "@/lib/types"

interface Props {
  stats: Stats | null
  loading: boolean
}

export function StatsBar({ stats, loading }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-16 rounded-xl" />
        ))}
      </div>
    )
  }

  if (!stats) return null

  const lastUpdated = stats.last_updated
    ? new Date(stats.last_updated).toLocaleDateString("es-AR", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "–"

  const items = [
    { icon: Tag, label: "Promociones activas", value: stats.total_promotions.toLocaleString("es-AR") },
    { icon: Building2, label: "Supermercados", value: stats.total_supermarkets },
    { icon: Landmark, label: "Bancos / Wallets", value: stats.total_banks },
    { icon: Clock, label: "Actualizado", value: lastUpdated },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {items.map(({ icon: Icon, label, value }) => (
        <div
          key={label}
          className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center gap-3"
        >
          <span className="bg-slate-100 rounded-lg p-2 shrink-0">
            <Icon className="w-4 h-4 text-slate-600" />
          </span>
          <div className="min-w-0">
            <p className="text-lg font-bold text-slate-900 leading-none">{value}</p>
            <p className="text-[11px] text-slate-500 mt-0.5 leading-tight">{label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
