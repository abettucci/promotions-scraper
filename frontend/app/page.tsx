"use client"

import { useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { FilterState } from "@/lib/types"
import { FilterBar } from "@/components/FilterBar"
import { PromoGrid } from "@/components/PromoGrid"
import { StatsBar } from "@/components/StatsBar"
import { Button } from "@/components/ui/button"
import { UserMenu } from "@/components/UserMenu"
import { CalendarDays, AlertCircle } from "lucide-react"

const DEFAULT_FILTERS: FilterState = {
  supermarket: "",
  bank: "",
  day: "",
  search: "",
  discount_type: "",
  page: 1,
}

export default function Home() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)
  const [todayOnly, setTodayOnly] = useState(false)

  const updateFilters = useCallback((partial: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...partial }))
    setTodayOnly(false)
    if (partial.page || partial.supermarket || partial.bank || partial.day || partial.discount_type) {
      window.scrollTo({ top: 0, behavior: "smooth" })
    }
  }, [])

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS)
    setTodayOnly(false)
  }, [])

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: api.getStats,
  })

  const { data: banks = [] } = useQuery({
    queryKey: ["banks"],
    queryFn: api.getBanks,
  })

  const { data: supermarkets = [] } = useQuery({
    queryKey: ["supermarkets"],
    queryFn: api.getSupermarkets,
  })

  const { data: promos, isLoading: promosLoading, isFetching, error } = useQuery({
    queryKey: ["promotions", filters, todayOnly],
    queryFn: () =>
      todayOnly
        ? api.getTodayPromotions().then((r) => ({
            total: r.total,
            page: 1,
            page_size: r.total,
            pages: 1,
            data: r.data,
          }))
        : api.getPromotions({
            supermarket: filters.supermarket || undefined,
            bank: filters.bank || undefined,
            day: filters.day || undefined,
            search: filters.search || undefined,
            discount_type: filters.discount_type || undefined,
            page: filters.page,
            page_size: 24,
          }),
  })

  const todayLabel = new Date().toLocaleDateString("es-AR", { weekday: "long" })

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xl font-black text-slate-900 tracking-tight">PromoAR</span>
            <span className="hidden sm:inline text-xs text-slate-400 font-normal">
              Descuentos de supermercados
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={todayOnly ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setTodayOnly((v) => !v)
                setFilters(DEFAULT_FILTERS)
              }}
              className="gap-1.5 text-sm"
            >
              <CalendarDays className="w-4 h-4" />
              <span className="hidden sm:inline">Hoy — {todayLabel}</span>
              <span className="sm:hidden">Hoy</span>
            </Button>
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Stats bar */}
        <StatsBar stats={stats ?? null} loading={statsLoading} />

        {/* Filters */}
        {!todayOnly && (
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <FilterBar
              filters={filters}
              banks={banks}
              supermarkets={supermarkets}
              onChange={updateFilters}
              onReset={resetFilters}
              totalResults={promos?.total ?? 0}
              loading={isFetching}
            />
          </div>
        )}

        {/* Today mode banner */}
        {todayOnly && (
          <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3">
            <div className="flex items-center gap-2 text-emerald-800">
              <CalendarDays className="w-4 h-4" />
              <span className="text-sm font-medium">
                {promos?.total ?? 0} promociones vigentes hoy — {todayLabel}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              className="text-emerald-700 hover:text-emerald-900"
            >
              Ver todas
            </Button>
          </div>
        )}

        {/* API error */}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-red-700 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>
              No se pudo conectar con la API. Asegurate de que el backend esté corriendo:{" "}
              <code className="font-mono text-xs bg-red-100 px-1 py-0.5 rounded">
                uvicorn api:app --reload
              </code>
            </span>
          </div>
        )}

        {/* Grid */}
        <PromoGrid
          promotions={promos?.data ?? []}
          loading={promosLoading || isFetching}
          page={promos?.page ?? 1}
          pages={promos?.pages ?? 1}
          total={promos?.total ?? 0}
          onPageChange={(p) => updateFilters({ page: p })}
        />
      </main>

      <footer className="mt-12 border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        PromoAR — Datos extraídos de sitios oficiales. Verificar condiciones con cada entidad.
      </footer>
    </div>
  )
}
