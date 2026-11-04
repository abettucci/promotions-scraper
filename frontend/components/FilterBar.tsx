"use client"

import { useState, useRef } from "react"
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

const PROVINCES = [
  ["buenos aires", "Buenos Aires"], ["caba", "CABA"], ["catamarca", "Catamarca"],
  ["chaco", "Chaco"], ["chubut", "Chubut"], ["cordoba", "Córdoba"], ["corrientes", "Corrientes"],
  ["entre rios", "Entre Ríos"], ["formosa", "Formosa"], ["jujuy", "Jujuy"], ["la pampa", "La Pampa"],
  ["la rioja", "La Rioja"], ["mendoza", "Mendoza"], ["misiones", "Misiones"], ["neuquen", "Neuquén"],
  ["rio negro", "Río Negro"], ["salta", "Salta"], ["san juan", "San Juan"], ["san luis", "San Luis"],
  ["santa cruz", "Santa Cruz"], ["santa fe", "Santa Fe"], ["santiago del estero", "Santiago del Estero"],
  ["tierra del fuego", "Tierra del Fuego"], ["tucuman", "Tucumán"],
] as const

function MultiChoice({ label, allLabel, selected, options, onChange }: {
  label: string; allLabel: string; selected: string[]
  options: { value: string; label: string }[]; onChange: (values: string[]) => void
}) {
  const toggle = (value: string) => onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])
  const summary = selected.length === 0 ? allLabel : selected.length === 1
    ? (options.find((option) => option.value === selected[0])?.label ?? selected[0])
    : `${selected.length} seleccionados`
  return <details className="group relative">
    <summary className="flex h-11 min-w-[170px] cursor-pointer list-none items-center justify-between gap-3 rounded-xl border border-[#cbd8e6] bg-[#f8fafd] px-3 text-sm text-[#102a4c] shadow-sm hover:border-[#9cb5d0] [&::-webkit-details-marker]:hidden">
      <span className="max-w-[220px] truncate">{summary}</span><span aria-hidden="true" className="text-[#71839a] transition-transform group-open:rotate-180">⌄</span>
    </summary>
    <div className="absolute left-0 top-[calc(100%+6px)] z-40 max-h-72 min-w-full w-max max-w-[min(90vw,22rem)] overflow-y-auto rounded-xl border border-[#dbe4ee] bg-white p-2 shadow-[0_16px_40px_rgb(16_42_76_/_0.16)]" role="group" aria-label={label}>
      <div className="flex items-center justify-between gap-4 border-b border-[#edf1f5] px-2 pb-2"><span className="text-[11px] font-semibold uppercase tracking-wide text-[#71839a]">{selected.length ? `${selected.length} seleccionados` : "Sin filtro"}</span>{selected.length > 0 && <button type="button" onClick={() => onChange([])} className="text-xs font-semibold text-[#2758d8] hover:underline">Limpiar</button>}</div>
      <div className="pt-1">{options.map((option) => <label key={option.value} className="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-[#102a4c] hover:bg-[#f1f5f9]"><input type="checkbox" checked={selected.includes(option.value)} onChange={() => toggle(option.value)} className="h-4 w-4 accent-[#102a4c]" /><span className="min-w-0 flex-1 truncate">{option.label}</span></label>)}</div>
    </div>
  </details>
}

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
  const isMobility = category === "mobility"
  const merchantLabel = isMobility ? "Servicio o red" : isFuel ? "Empresa o marca" : "Supermercado"
  const merchantAllLabel = isMobility ? "Todos los servicios" : isFuel ? "Todas las empresas" : "Todos los super"

  const hasActiveFilters =
    filters.supermarket.length > 0 ||
    filters.bank.length > 0 ||
    filters.province ||
    filters.days.length > 0 ||
    filters.search ||
    filters.discount_type ||
    filters.modality.length > 0 ||
    filters.state !== "activa"

  const [localSearch, setLocalSearch] = useState(filters.search)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)

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

  const handleReset = () => {
    clearTimeout(debounceRef.current)
    setLocalSearch("")
    onReset()
  }

  return (
    <div className="space-y-6">
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#687487] pointer-events-none" />
        <Input
          placeholder="Buscar promoción, banco, condición..."
          value={localSearch}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="h-12 rounded-xl border-[#cbd8e6] bg-[#f8fafd] pl-10 text-[#102a4c] placeholder:text-[#71839a] focus-visible:border-[#2758d8] focus-visible:ring-[#2758d8]/25"
        />
      </div>

      {/* Estado */}
      <section className="space-y-2">
        <h4 className="eyebrow">Estado</h4>
        <div className="flex gap-3">
          {STATES.map(({ value, label, Icon }) => {
            const selected = filters.state === value
            return (
              <button
                key={value}
                onClick={() => onChange({ state: value, page: 1 })}
                className="flex min-w-12 flex-col items-center gap-1.5 transition-colors"
                aria-pressed={selected}
              >
                <span
                  className={`flex items-center justify-center w-12 h-12 rounded-xl border ${
                  selected
                      ? "border-[#102a4c] bg-[#102a4c] text-white"
                      : "border-[#cbd8e6] bg-[#f8fafd] text-[#102a4c] hover:border-[#9cb5d0] hover:bg-[#edf2f7]"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </span>
                <span
                  className={`text-xs ${
                    selected ? "font-semibold text-[#102a4c]" : "text-[#52657d]"
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
        <h4 className="eyebrow">Días de aplicación</h4>
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
                    ? "border-[#102a4c] bg-[#102a4c] text-[#b8f36b]"
                    : "border-[#cbd8e6] bg-[#f8fafd] text-[#102a4c] hover:border-[#9cb5d0] hover:bg-[#edf2f7]"
                }`}
              >
                {letter}
              </button>
            )
          })}
        </div>
      </section>

      {isMobility && (
        <section className="space-y-2">
          <h4 className="eyebrow">Tipo de movilidad</h4>
          <div className="flex flex-wrap gap-2">
            {[{ value: "", label: "Todo" }, { value: "ride_hailing", label: "Apps de viaje" }, { value: "public_transit", label: "Transporte público" }].map((item) => (
              <button key={item.value || "all"} onClick={() => onChange({ mobility_kind: item.value as FilterState["mobility_kind"], page: 1 })} aria-pressed={filters.mobility_kind === item.value} className={`min-h-9 rounded-full border px-3 text-xs font-semibold transition-colors ${filters.mobility_kind === item.value ? "border-[#102a4c] bg-[#102a4c] text-[#b8f36b]" : "border-[#cbd8e6] bg-[#f8fafd] text-[#52657d] hover:border-[#9cb5d0] hover:text-[#102a4c]"}`}>
                {item.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Modalidad de uso */}
      <section className="space-y-2">
        <h4 className="eyebrow">Modalidad de uso</h4>
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
                <span className="text-sm font-medium text-[#102a4c]">{label}</span>
              </label>
            )
          })}
        </div>
      </section>

      {/* Empresa / Banco / Tipo de descuento */}
      <section className="space-y-2">
        <h4 className="eyebrow">Filtros adicionales</h4>
        <div className="flex flex-wrap gap-2">
          <MultiChoice label={merchantLabel} allLabel={merchantAllLabel} selected={filters.supermarket}
            options={supermarkets.map((s) => ({ value: s.name, label: `${s.name} (${s.active_promotions})` }))}
            onChange={(supermarket) => onChange({ supermarket, page: 1 })} />

          <MultiChoice label="Banco o billetera" allLabel="Todos los bancos" selected={filters.bank}
            options={banks.map((b) => ({ value: b.name, label: `${b.name} (${b.count})` }))}
            onChange={(bank) => onChange({ bank, page: 1 })} />

          <Select value={filters.province || ALL_VALUE}
            onValueChange={(province) => onChange({ province: province === ALL_VALUE ? "" : province, page: 1 })}>
            <SelectTrigger aria-label="Filtrar por provincia" className="h-11 w-[190px] rounded-xl border-[#cbd8e6] bg-[#f8fafd] text-sm text-[#102a4c]">
              <SelectValue placeholder="Todas las provincias" />
            </SelectTrigger>
            <SelectContent><SelectItem value={ALL_VALUE}>Todas las provincias</SelectItem>
              {PROVINCES.map(([value, name]) => <SelectItem key={value} value={value}>{name}</SelectItem>)}
            </SelectContent>
          </Select>

          <Select
            value={filters.discount_type || ALL_VALUE}
            onValueChange={(v) => onChange({ discount_type: v === ALL_VALUE ? "" : v, page: 1 })}
          >
            <SelectTrigger className="h-11 w-[145px] rounded-xl border-[#cbd8e6] bg-[#f8fafd] text-sm text-[#102a4c]">
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
              onClick={handleReset}
              className="h-11 gap-1 text-[#52657d] hover:bg-[#edf2f7] hover:text-[#102a4c]"
            >
              <X className="w-3.5 h-3.5" />
              Limpiar
            </Button>
          )}
        </div>
      </section>

      <p className="-mt-4 text-[11px] leading-relaxed text-[#71839a]">La provincia se detecta en las condiciones publicadas. Las promos sin una región explícita también se incluyen; verificá los términos antes de comprar.</p>

      {/* Results count */}
      <p aria-live="polite" className={`text-xs font-medium transition-opacity ${loading ? "text-[#52657d]/40" : "text-[#52657d]"}`}>
        {totalResults.toLocaleString("es-AR")} promociones encontradas
      </p>
    </div>
  )
}
