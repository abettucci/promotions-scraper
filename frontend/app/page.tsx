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
import Link from "next/link"
import { CalendarDays, AlertCircle, CreditCard, ShoppingCart, Fuel, Sparkles, ArrowUpRight } from "lucide-react"

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
  const todayDate = new Date().toLocaleDateString("es-AR", { day: "numeric", month: "long" })

  return (
    <div className="min-h-screen overflow-x-hidden">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#10243e]/95 text-[#fffdf8] shadow-lg backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="group flex items-center gap-2" aria-label="Ir al inicio de PromoAR">
              <span className="grid h-9 w-9 place-items-center rounded-full bg-[#ffd84d] text-base font-black text-[#10243e] shadow-[3px_3px_0_#ef5845] transition-transform group-hover:-translate-y-0.5">P</span>
              <span className="text-xl font-black tracking-[-0.06em]">PROMO<span className="text-[#ffd84d]">AR</span></span>
            </Link>
            {/* Category tabs */}
            <div className="flex items-center rounded-full border border-white/15 bg-white/10 p-1">
              <button
                onClick={() => {
                  setCategory("supermarket")
                  setFilters(DEFAULT_FILTERS)
                  setMyPromosMode(false)
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-bold rounded-full transition-colors ${
                  category === "supermarket"
                    ? "bg-[#fffdf8] text-[#10243e] shadow-sm"
                    : "text-white/70 hover:text-white"
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
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-bold rounded-full transition-colors ${
                  category === "fuel"
                    ? "bg-[#fffdf8] text-[#10243e] shadow-sm"
                    : "text-white/70 hover:text-white"
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
              className="hidden md:flex gap-1.5 border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white"
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
                className="gap-1.5 border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white"
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

      <main className="max-w-7xl mx-auto px-4 py-6 sm:py-10 space-y-6">
        <section className="rise-in relative overflow-hidden rounded-[2rem] bg-[#10243e] px-6 py-8 text-[#fffdf8] shadow-[8px_8px_0_#ef5845] sm:px-10 sm:py-10">
          <div className="pointer-events-none absolute -right-12 -top-20 h-64 w-64 rounded-full border-[28px] border-[#ffd84d] opacity-95" />
          <div className="pointer-events-none absolute bottom-0 right-20 h-20 w-40 bg-[#ef5845] [clip-path:polygon(0_0,100%_35%,78%_100%,0_76%)]" />
          <div className="relative max-w-2xl">
            <div className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[#ffd84d]"><Sparkles className="h-4 w-4" /> Antes de pagar</div>
            <p className="text-sm font-medium text-white/70">{todayDate}</p>
            <h1 className="promo-display mt-1 text-5xl font-semibold leading-[0.85] tracking-[-0.06em] sm:text-7xl">Antes de pagar,<br /><span className="text-[#ffd84d]">mirá acá.</span></h1>
            <p className="mt-5 max-w-md text-sm leading-relaxed text-white/75 sm:text-base">Descuentos bancarios y promociones de súper. Buscá por día, banco o comercio.</p>
          </div>
          <button onClick={toggleTodayOnly} className="relative mt-7 inline-flex items-center gap-2 rounded-full bg-[#ffd84d] px-4 py-2 text-sm font-black text-[#10243e] transition-transform hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">
            Ver promos de hoy <ArrowUpRight className="h-4 w-4" />
          </button>
        </section>

        <StatsBar stats={stats ?? null} loading={statsLoading} />

        {/* Filters — siempre visibles excepto en "mis promos" */}
        {!myPromosMode && (
          <div className="rise-in rounded-[1.5rem] border border-[#10243e]/10 bg-[#fffdf8] p-4 shadow-[4px_4px_0_rgb(16_36_62_/_0.12)] sm:p-5">
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
          <div className="flex items-center justify-between rounded-2xl border border-[#10243e]/15 bg-[#ffd84d] px-4 py-3 shadow-[3px_3px_0_#10243e]">
            <div className="flex items-center gap-2 text-[#10243e]">
              <CreditCard className="w-4 h-4" />
              <span className="text-sm font-medium">
                {promos?.total ?? 0} promociones para tus medios de pago — {todayLabel}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              className="text-[#10243e] hover:bg-[#10243e]/10 hover:text-[#10243e]"
            >
              Ver todas
            </Button>
          </div>
        )}

        {/* API error */}
        {error && (
          <div className="flex items-center gap-2 rounded-2xl border border-[#ef5845]/30 bg-[#fff0e9] px-4 py-3 text-[#a9362a] text-sm">
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
          layout={filters.supermarket ? "table" : "grid"}
          marketName={filters.supermarket || undefined}
          onPageChange={(p) => updateFilters({ page: p })}
        />
      </main>

      <footer className="mt-14 border-t border-[#10243e]/10 py-8 text-center text-xs text-[#687487]">
        <span className="font-black text-[#10243e]">PROMOAR</span> — Datos extraídos de sitios oficiales. Verificar condiciones con cada entidad.
      </footer>
    </div>
  )
}
