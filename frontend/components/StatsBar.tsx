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
          <Skeleton key={i} className="h-24 rounded-2xl" />
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
    <div className="rise-in grid grid-cols-2 sm:grid-cols-4 gap-3" style={{ animationDelay: "80ms" }}>
      {items.map(({ icon: Icon, label, value }, index) => (
        <div
          key={label}
          className={`rounded-2xl border px-4 py-4 ${index === 0 ? "border-[#10243e] bg-[#10243e] text-[#fffdf8] shadow-[4px_4px_0_#ffd84d]" : "border-[#10243e]/10 bg-[#fffdf8] text-[#10243e]"}`}
        >
          <span className={`mb-3 inline-flex rounded-full p-2 ${index === 0 ? "bg-[#ffd84d] text-[#10243e]" : "bg-[#f0e6d4] text-[#10243e]"}`}>
            <Icon className="w-4 h-4" />
          </span>
          <div className="min-w-0">
            <p className="text-xl font-black leading-none tracking-tight">{value}</p>
            <p className={`text-[11px] mt-1 leading-tight ${index === 0 ? "text-white/60" : "text-[#687487]"}`}>{label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
