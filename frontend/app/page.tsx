"use client"

import { useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"
import type { FilterState, Category, DayCode } from "@/lib/types"
import { FilterBar } from "@/components/FilterBar"
import { PromoGrid } from "@/components/PromoGrid"
import { StatsBar } from "@/components/StatsBar"
import { Button } from "@/components/ui/button"
import { UserMenu } from "@/components/UserMenu"
import { useRouter } from "next/navigation"
import { CalendarDays, AlertCircle, CreditCard, ShoppingCart, Fuel } from "lucide-react"

const DEFAULT_FILTERS: FilterState = {
  supermarket: "",
  bank: "",
  days: [],
  search: "",
  discount_type: "",
  state: "activa",
  modality: [],
  page: 1,
}

// JS getDay(): 0=domingo .. 6=sábado
const DAY_CODES: DayCode[] = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
const todayCode: DayCode = DAY_CODES[new Date().getDay()]

export default function Home() {
  const [category, setCategory] = useState<Category>("supermarket")
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)
  const [myPromosMode, setMyPromosMode] = useState(false)
  const { user, token } = useAuthStore()
  const router = useRouter()
  const hasPaymentMethods = (user?.payment_methods?.length ?? 0) > 0

  // "Hoy" mode = solo el día de hoy está seleccionado en filters.days
  const todayOnly = filters.days.length === 1 && filters.days[0] === todayCode

  const updateFilters = useCallback((partial: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...partial }))
    setMyPromosMode(false)
    if (
      partial.page ||
      partial.supermarket ||
      partial.bank ||
      partial.days ||
      partial.discount_type ||
      partial.state ||
      partial.modality
    ) {
      window.scrollTo({ top: 0, behavior: "smooth" })
    }
  }, [])

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS)
    setMyPromosMode(false)
  }, [])

  const toggleTodayOnly = useCallback(() => {
    // Si hoy ya está como único filtro de día → limpiar; si no → setear hoy
    setFilters((prev) => ({
      ...prev,
      days: todayOnly ? [] : [todayCode],
      page: 1,
    }))
    setMyPromosMode(false)
  }, [todayOnly])

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: api.getStats,
  })

  const { data: banks = [] } = useQuery({
    queryKey: [
      "banks", category,
      filters.supermarket, filters.days, filters.discount_type, filters.state, filters.modality,
    ],
    queryFn: () => api.getBanks({
      category,
      supermarket: filters.supermarket || undefined,
      day: filters.days.length ? filters.days.join(",") : undefined,
      discount_type: filters.discount_type || undefined,
      state: filters.state || undefined,
      modality: filters.modality.length ? filters.modality.join(",") : undefined,
    }),
  })

  const { data: supermarkets = [] } = useQuery({
    queryKey: ["supermarkets", category],
    queryFn: () => api.getSupermarkets(category),
  })

  const { data: promos, isLoading: promosLoading, isFetching, error } = useQuery({
    queryKey: ["promotions", filters, myPromosMode, category],
    queryFn: () => {
      if (myPromosMode && token) {
        return api.getMyPromotions(token, true).then((r) => ({
          total: r.total,
          page: 1,
          page_size: r.total,
          pages: 1,
          data: r.by_supermarket.flatMap((s) => s.promotions),
        }))
      }
      return api.getPromotions({
        supermarket: filters.supermarket || undefined,
        bank: filters.bank || undefined,
        day: filters.days.length ? filters.days.join(",") : undefined,
        search: filters.search || undefined,
        discount_type: filters.discount_type || undefined,
        state: filters.state || undefined,
        modality: filters.modality.length ? filters.modality.join(",") : undefined,
        category,
        page: filters.page,
        page_size: 24,
      })
    },
  })

  const todayLabel = new Date().toLocaleDateString("es-AR", { weekday: "long" })

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="text-xl font-black text-slate-900 tracking-tight">PromoAR</span>
            {/* Category tabs */}
            <div className="flex items-center bg-slate-100 rounded-lg p-0.5">
              <button
                onClick={() => {
                  setCategory("supermarket")
                  setFilters(DEFAULT_FILTERS)
                  setMyPromosMode(false)
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  category === "supermarket"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                <ShoppingCart className="w-4 h-4" />
                <span className="hidden sm:inline">Supermercados</span>
              </button>
              <button
                onClick={() => {
                  setCategory("fuel")
                  setFilters(DEFAULT_FILTERS)
                  setMyPromosMode(false)
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  category === "fuel"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                <Fuel className="w-4 h-4" />
                <span className="hidden sm:inline">Combustible</span>
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={todayOnly ? "default" : "outline"}
              size="sm"
              onClick={toggleTodayOnly}
              className="gap-1.5 text-sm"
            >
              <CalendarDays className="w-4 h-4" />
              <span className="hidden sm:inline">Hoy — {todayLabel}</span>
              <span className="sm:hidden">Hoy</span>
            </Button>
            {user && (
              <Button
                variant={myPromosMode ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  if (!hasPaymentMethods) {
                    router.push("/profile")
                    return
                  }
                  setMyPromosMode((v) => !v)
                  setFilters(DEFAULT_FILTERS)
                }}
                className="gap-1.5 text-sm"
              >
                <CreditCard className="w-4 h-4" />
                <span className="hidden sm:inline">Mis promos</span>
                <span className="sm:hidden">Mis</span>
              </Button>
            )}
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Stats bar */}
        <StatsBar stats={stats ?? null} loading={statsLoading} />

        {/* Filters — siempre visibles excepto en "mis promos" */}
        {!myPromosMode && (
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <FilterBar
              filters={filters}
              banks={banks}
              supermarkets={supermarkets}
              category={category}
              onChange={updateFilters}
              onReset={resetFilters}
              totalResults={promos?.total ?? 0}
              loading={isFetching}
            />
          </div>
        )}

        {/* My promos mode banner */}
        {myPromosMode && (
          <div className="flex items-center justify-between bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
            <div className="flex items-center gap-2 text-blue-800">
              <CreditCard className="w-4 h-4" />
              <span className="text-sm font-medium">
                {promos?.total ?? 0} promociones para tus medios de pago — {todayLabel}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              className="text-blue-700 hover:text-blue-900"
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
