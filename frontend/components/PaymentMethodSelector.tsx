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
      onChange([...selected, { name, type, card_mode: "both" }])
    }
  }

  const setCardMode = (name: string, cardMode: PaymentMethod["card_mode"]) => {
    onChange(selected.map((method) => method.name === name ? { ...method, card_mode: cardMode } : method))
  }

  const configurableMethods = selected.filter((method) => method.type === "bank" || method.type === "wallet")

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

      {configurableMethods.length > 0 && (
        <section className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="mb-3">
            <h3 className="text-sm font-semibold text-slate-800">Cómo pagás con cada entidad</h3>
            <p className="mt-0.5 text-xs text-slate-500">Usaremos esto para ocultar promos exclusivas de una tarjeta que no tenés.</p>
          </div>
          <div className="space-y-2">
            {configurableMethods.map((method) => {
              const currentMode = method.card_mode ?? "both"
              return (
                <div key={method.name} className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-sm font-medium text-slate-700">{method.name}</span>
                  <div className="grid grid-cols-3 rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-medium">
                    {([
                      ["credit", "Crédito"], ["debit", "Débito"], ["both", "Ambas"],
                    ] as const).map(([mode, label]) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => setCardMode(method.name, mode)}
                        aria-pressed={currentMode === mode}
                        className={cn(
                          "rounded-md px-2.5 py-1.5 transition-colors",
                          currentMode === mode ? "bg-slate-900 text-white shadow-sm" : "text-slate-600 hover:text-slate-900",
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}
