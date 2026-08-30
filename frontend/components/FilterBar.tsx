"use client"

import { useState, useEffect, useRef } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Search, X, ShoppingCart, Clock, Trash2 } from "lucide-react"
import type {
  Bank,
  Supermarket,
  FilterState,
  Category,
  PromotionState,
  Modality,
  DayCode,
} from "@/lib/types"

interface Props {
  filters: FilterState
  banks: Bank[]
  supermarkets: Supermarket[]
  category?: Category
  onChange: (filters: Partial<FilterState>) => void
  onReset: () => void
  totalResults: number
  loading?: boolean
}

const DAYS: { code: DayCode; letter: string; label: string }[] = [
  { code: "lunes", letter: "L", label: "Lunes" },
  { code: "martes", letter: "M", label: "Martes" },
  { code: "miércoles", letter: "X", label: "Miércoles" },
  { code: "jueves", letter: "J", label: "Jueves" },
  { code: "viernes", letter: "V", label: "Viernes" },
  { code: "sábado", letter: "S", label: "Sábado" },
  { code: "domingo", letter: "D", label: "Domingo" },
]

const STATES: { value: PromotionState; label: string; Icon: typeof ShoppingCart }[] = [
  { value: "activa", label: "Activas", Icon: ShoppingCart },
  { value: "proxima", label: "Próximas", Icon: Clock },
  { value: "finalizada", label: "Finalizadas", Icon: Trash2 },
]

const MODALITIES: { value: Modality; label: string }[] = [
  { value: "presencial", label: "Presencial" },
  { value: "online", label: "Online" },
]

const DISCOUNT_TYPES = [
  { value: "percent", label: "% Descuento" },
  { value: "cuotas", label: "Cuotas" },
  { value: "cashback", label: "Cashback" },
]

const ALL_VALUE = "__all__"

export function FilterBar({
  filters,
  banks,
  supermarkets,
  category = "supermarket",
  onChange,
  onReset,
  totalResults,
  loading,
}: Props) {
  const isFuel = category === "fuel"
  const merchantLabel = isFuel ? "Empresa o marca" : "Supermercado"
  const merchantAllLabel = isFuel ? "Todas las empresas" : "Todos los super"

  const hasActiveFilters =
    filters.supermarket ||
    filters.bank ||
    filters.days.length > 0 ||
    filters.search ||
    filters.discount_type ||
    filters.modality.length > 0 ||
    filters.state !== "activa"

  const [localSearch, setLocalSearch] = useState(filters.search)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    setLocalSearch(filters.search)
  }, [filters.search])

  const handleSearchChange = (value: string) => {
    setLocalSearch(value)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      onChange({ search: value, page: 1 })
    }, 350)
  }

  const toggleDay = (day: DayCode) => {
    const current = filters.days
    const next = current.includes(day) ? current.filter((d) => d !== day) : [...current, day]
    onChange({ days: next, page: 1 })
  }

  const toggleModality = (m: Modality) => {
    const current = filters.modality
    const next = current.includes(m) ? current.filter((x) => x !== m) : [...current, m]
    onChange({ modality: next, page: 1 })
  }

  return (
    <div className="space-y-5">
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#687487] pointer-events-none" />
        <Input
          placeholder="Buscar promoción, banco, condición..."
          value={localSearch}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="h-12 rounded-xl border-[#10243e]/15 bg-[#f7f2e8] pl-10 text-[#10243e] placeholder:text-[#687487] focus-visible:ring-[#ef5845]"
        />
      </div>

      {/* Estado */}
      <section className="space-y-2">
        <h4 className="text-xs font-black uppercase tracking-[0.15em] text-[#10243e]">Estado</h4>
        <div className="flex gap-3">
          {STATES.map(({ value, label, Icon }) => {
            const selected = filters.state === value
            return (
              <button
                key={value}
                onClick={() => onChange({ state: value, page: 1 })}
                className={`flex flex-col items-center gap-1.5 transition-colors`}
                aria-pressed={selected}
              >
                <span
                  className={`flex items-center justify-center w-12 h-12 rounded-xl border ${
                  selected
                      ? "bg-[#ef5845] border-[#ef5845] text-white shadow-[2px_2px_0_#10243e]"
                      : "bg-[#f7f2e8] border-[#10243e]/15 text-[#10243e] hover:bg-[#ffd84d]"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </span>
                <span
                  className={`text-xs ${
                    selected ? "text-[#10243e] font-bold" : "text-[#687487]"
                  }`}
                >
                  {label}
                </span>
              </button>
            )
          })}
        </div>
      </section>

      {/* Días de aplicación */}
      <section className="space-y-2">
        <h4 className="text-xs font-black uppercase tracking-[0.15em] text-[#10243e]">Días de aplicación</h4>
        <div className="flex gap-2 flex-wrap">
          {DAYS.map(({ code, letter, label }) => {
            const selected = filters.days.includes(code)
            return (
              <button
                key={code}
                onClick={() => toggleDay(code)}
                title={label}
                aria-pressed={selected}
                className={`w-11 h-11 rounded-xl border text-sm font-medium transition-colors ${
                  selected
                    ? "bg-[#10243e] border-[#10243e] text-[#ffd84d] shadow-[2px_2px_0_#ef5845]"
                    : "bg-[#f7f2e8] border-[#10243e]/15 text-[#10243e] hover:bg-[#ffd84d]"
                }`}
              >
                {letter}
              </button>
            )
          })}
        </div>
      </section>

      {/* Modalidad de uso */}
      <section className="space-y-2">
        <h4 className="text-xs font-black uppercase tracking-[0.15em] text-[#10243e]">Modalidad de uso</h4>
        <div className="flex gap-6">
          {MODALITIES.map(({ value, label }) => {
            const selected = filters.modality.includes(value)
            return (
              <label
                key={value}
                className="flex items-center gap-2 cursor-pointer select-none"
              >
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => toggleModality(value)}
                  className="w-4 h-4 rounded border-[#10243e]/30 text-[#ef5845] focus:ring-[#ef5845]"
                />
                <span className="text-sm font-medium text-[#10243e]">{label}</span>
              </label>
            )
          })}
        </div>
      </section>

      {/* Empresa / Banco / Tipo de descuento */}
      <section className="space-y-2">
        <h4 className="text-xs font-black uppercase tracking-[0.15em] text-[#10243e]">Filtros adicionales</h4>
        <div className="flex flex-wrap gap-2">
          <Select
            value={filters.supermarket || ALL_VALUE}
            onValueChange={(v) => onChange({ supermarket: v === ALL_VALUE ? "" : v, page: 1 })}
          >
            <SelectTrigger className="w-[170px] h-10 rounded-xl text-sm bg-[#f7f2e8] border-[#10243e]/15">
              <SelectValue placeholder={merchantLabel} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>{merchantAllLabel}</SelectItem>
              {supermarkets.map((s) => (
                <SelectItem key={s.id} value={s.name}>
                  {s.name} ({s.active_promotions})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.bank || ALL_VALUE}
            onValueChange={(v) => onChange({ bank: v === ALL_VALUE ? "" : v, page: 1 })}
          >
            <SelectTrigger className="w-[160px] h-10 rounded-xl text-sm bg-[#f7f2e8] border-[#10243e]/15">
              <SelectValue placeholder="Banco / Wallet" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>Todos los bancos</SelectItem>
              {banks.map((b) => (
                <SelectItem key={b.name} value={b.name}>
                  {b.name} ({b.count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.discount_type || ALL_VALUE}
            onValueChange={(v) => onChange({ discount_type: v === ALL_VALUE ? "" : v, page: 1 })}
          >
            <SelectTrigger className="w-[145px] h-10 rounded-xl text-sm bg-[#f7f2e8] border-[#10243e]/15">
              <SelectValue placeholder="Tipo descuento" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>Todos los tipos</SelectItem>
              {DISCOUNT_TYPES.map((d) => (
                <SelectItem key={d.value} value={d.value}>
                  {d.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              className="h-10 text-[#687487] hover:bg-[#f0e6d4] hover:text-[#10243e] gap-1"
            >
              <X className="w-3.5 h-3.5" />
              Limpiar
            </Button>
          )}
        </div>
      </section>

      {/* Results count */}
      <p className={`text-xs font-medium transition-opacity ${loading ? "text-[#687487]/40" : "text-[#687487]"}`}>
        {totalResults.toLocaleString("es-AR")} promociones encontradas
      </p>
    </div>
  )
}
