"use client"

import { cn } from "@/lib/utils"
import type { PaymentMethod, PaymentMethodsCatalog } from "@/lib/types"
import { Building2, Wallet, Star } from "lucide-react"

interface Props {
  catalog: PaymentMethodsCatalog
  selected: PaymentMethod[]
  onChange: (methods: PaymentMethod[]) => void
}

const CATEGORY_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  bank:   { label: "Bancos",              icon: <Building2 className="w-4 h-4" />, color: "blue"   },
  wallet: { label: "Billeteras digitales", icon: <Wallet    className="w-4 h-4" />, color: "violet" },
  club:   { label: "Clubes y beneficios", icon: <Star      className="w-4 h-4" />, color: "amber"  },
}

const COLOR_CLASSES: Record<string, { badge: string; selected: string }> = {
  blue:   { badge: "bg-blue-50 text-blue-700 border-blue-200",   selected: "bg-blue-600 text-white border-blue-600"   },
  violet: { badge: "bg-violet-50 text-violet-700 border-violet-200", selected: "bg-violet-600 text-white border-violet-600" },
  amber:  { badge: "bg-amber-50 text-amber-700 border-amber-200", selected: "bg-amber-500 text-white border-amber-500" },
}

export function PaymentMethodSelector({ catalog, selected, onChange }: Props) {
  const isSelected = (name: string) => selected.some((m) => m.name === name)

  const toggle = (name: string, type: PaymentMethod["type"]) => {
    if (isSelected(name)) {
      onChange(selected.filter((m) => m.name !== name))
    } else {
      onChange([...selected, { name, type }])
    }
  }

  return (
    <div className="space-y-6">
      {(["bank", "wallet", "club"] as const).map((type) => {
        const meta  = CATEGORY_META[type]
        const items = catalog[type] ?? []
        const colors = COLOR_CLASSES[meta.color]

        return (
          <div key={type}>
            <div className="flex items-center gap-2 mb-3">
              <span className={cn(
                "flex items-center justify-center w-6 h-6 rounded-md",
                `bg-${meta.color}-100 text-${meta.color}-600`
              )}>
                {meta.icon}
              </span>
              <h3 className="text-sm font-semibold text-slate-700">{meta.label}</h3>
              <span className="text-xs text-slate-400">
                ({selected.filter((m) => m.type === type).length} seleccionado{selected.filter((m) => m.type === type).length !== 1 ? "s" : ""})
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {items.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => toggle(name, type)}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-sm font-medium border transition-all",
                    isSelected(name) ? colors.selected : colors.badge + " hover:opacity-80"
                  )}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
