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
    <div className="enter grid grid-cols-2 gap-3 sm:grid-cols-4" style={{ animationDelay: "90ms" }}>
      {items.map(({ icon: Icon, label, value }, index) => (
        <div
          key={label}
          className={`rounded-2xl border px-4 py-4 ${index === 0 ? "border-[#102a4c] bg-[#102a4c] text-white" : "border-[#dbe4ee] bg-white text-[#102a4c] shadow-[0_12px_30px_rgb(16_42_76_/_0.05)]"}`}
        >
          <span className={`mb-3 inline-flex rounded-lg p-2 ${index === 0 ? "bg-[#b8f36b] text-[#102a4c]" : "bg-[#edf2f7] text-[#2758d8]"}`}>
            <Icon className="w-4 h-4" />
          </span>
          <div className="min-w-0">
            <p className="display text-xl font-semibold leading-none tracking-[-0.05em]">{value}</p>
            <p className={`mt-1 text-[11px] leading-tight ${index === 0 ? "text-white/65" : "text-[#52657d]"}`}>{label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
