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
import { Search, X } from "lucide-react"
import type { Bank, Supermarket, FilterState } from "@/lib/types"

interface Props {
  filters: FilterState
  banks: Bank[]
  supermarkets: Supermarket[]
  onChange: (filters: Partial<FilterState>) => void
  onReset: () => void
  totalResults: number
  loading?: boolean
}

const DAYS = [
  { value: "lunes", label: "Lunes" },
  { value: "martes", label: "Martes" },
  { value: "miércoles", label: "Miércoles" },
  { value: "jueves", label: "Jueves" },
  { value: "viernes", label: "Viernes" },
  { value: "sábado", label: "Sábado" },
  { value: "domingo", label: "Domingo" },
]

const DISCOUNT_TYPES = [
  { value: "percent", label: "% Descuento" },
  { value: "cuotas", label: "Cuotas" },
  { value: "cashback", label: "Cashback" },
]

const ALL_VALUE = "__all__"

export function FilterBar({ filters, banks, supermarkets, onChange, onReset, totalResults, loading }: Props) {
  const hasActiveFilters =
    filters.supermarket || filters.bank || filters.day || filters.search || filters.discount_type

  const [localSearch, setLocalSearch] = useState(filters.search)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

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

  return (
    <div className="space-y-3">
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        <Input
          placeholder="Buscar promoción, banco, condición..."
          value={localSearch}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="pl-9 bg-white border-slate-200 focus-visible:ring-slate-300"
        />
      </div>

      {/* Dropdowns row */}
      <div className="flex flex-wrap gap-2">
        {/* Supermarket */}
        <Select
          value={filters.supermarket || ALL_VALUE}
          onValueChange={(v) => onChange({ supermarket: v === ALL_VALUE ? "" : v, page: 1 })}
        >
          <SelectTrigger className="w-[170px] h-9 text-sm bg-white border-slate-200">
            <SelectValue placeholder="Supermercado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_VALUE}>Todos los super</SelectItem>
            {supermarkets.map((s) => (
              <SelectItem key={s.id} value={s.name}>
                {s.name} ({s.active_promotions})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Bank */}
        <Select
          value={filters.bank || ALL_VALUE}
          onValueChange={(v) => onChange({ bank: v === ALL_VALUE ? "" : v, page: 1 })}
        >
          <SelectTrigger className="w-[160px] h-9 text-sm bg-white border-slate-200">
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

        {/* Day */}
        <Select
          value={filters.day || ALL_VALUE}
          onValueChange={(v) => onChange({ day: v === ALL_VALUE ? "" : v, page: 1 })}
        >
          <SelectTrigger className="w-[130px] h-9 text-sm bg-white border-slate-200">
            <SelectValue placeholder="Día" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_VALUE}>Todos los días</SelectItem>
            {DAYS.map((d) => (
              <SelectItem key={d.value} value={d.value}>
                {d.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Discount type */}
        <Select
          value={filters.discount_type || ALL_VALUE}
          onValueChange={(v) => onChange({ discount_type: v === ALL_VALUE ? "" : v, page: 1 })}
        >
          <SelectTrigger className="w-[145px] h-9 text-sm bg-white border-slate-200">
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

        {/* Reset button */}
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            className="h-9 text-slate-500 hover:text-slate-800 gap-1"
          >
            <X className="w-3.5 h-3.5" />
            Limpiar
          </Button>
        )}
      </div>

      {/* Results count */}
      <p className={`text-xs transition-opacity ${loading ? "text-slate-300" : "text-slate-500"}`}>
        {totalResults.toLocaleString("es-AR")} promociones encontradas
      </p>
    </div>
  )
}
