"use client"

import { useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { CalendarDays, AlertCircle, CreditCard, ShoppingCart, Fuel, ArrowUpRight, Check } from "lucide-react"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"
import type { FilterState, Category, DayCode } from "@/lib/types"
import { FilterBar } from "@/components/FilterBar"
import { PromoGrid } from "@/components/PromoGrid"
import { StatsBar } from "@/components/StatsBar"
import { Button } from "@/components/ui/button"
import { UserMenu } from "@/components/UserMenu"
import { PromoAssistant } from "@/components/PromoAssistant"

const DEFAULT_FILTERS: FilterState = {
  supermarket: "", bank: "", days: [], search: "", discount_type: "",
  state: "activa", modality: [], page: 1,
}

const DAY_CODES: DayCode[] = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
const todayCode: DayCode = DAY_CODES[new Date().getDay()]

export default function Home() {
  const [category, setCategory] = useState<Category>("supermarket")
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)
  const [myPromosMode, setMyPromosMode] = useState(false)
  const { user, token } = useAuthStore()
  const router = useRouter()
  const hasPaymentMethods = (user?.payment_methods?.length ?? 0) > 0
  const todayOnly = filters.days.length === 1 && filters.days[0] === todayCode

  const updateFilters = useCallback((partial: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...partial }))
    setMyPromosMode(false)
    if (partial.page || partial.supermarket || partial.bank || partial.days || partial.discount_type || partial.state || partial.modality) {
      window.scrollTo({ top: 0, behavior: "smooth" })
    }
  }, [])

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS)
    setMyPromosMode(false)
  }, [])

  const toggleTodayOnly = useCallback(() => {
    setFilters((prev) => ({ ...prev, days: todayOnly ? [] : [todayCode], page: 1 }))
    setMyPromosMode(false)
  }, [todayOnly])

  const { data: stats, isLoading: statsLoading } = useQuery({ queryKey: ["stats"], queryFn: api.getStats })
  const { data: banks = [] } = useQuery({
    queryKey: ["banks", category, filters.supermarket, filters.days, filters.discount_type, filters.state, filters.modality],
    queryFn: () => api.getBanks({
      category, supermarket: filters.supermarket || undefined,
      day: filters.days.length ? filters.days.join(",") : undefined,
      discount_type: filters.discount_type || undefined, state: filters.state || undefined,
      modality: filters.modality.length ? filters.modality.join(",") : undefined,
    }),
  })
  const { data: supermarkets = [] } = useQuery({ queryKey: ["supermarkets", category], queryFn: () => api.getSupermarkets(category) })
  const { data: promos, isLoading: promosLoading, isFetching, error } = useQuery({
    queryKey: ["promotions", filters, myPromosMode, category],
    queryFn: () => {
      if (myPromosMode && token) {
        return api.getMyPromotions(token, true).then((r) => ({ total: r.total, page: 1, page_size: r.total, pages: 1, data: r.by_supermarket.flatMap((s) => s.promotions) }))
      }
      return api.getPromotions({
        supermarket: filters.supermarket || undefined, bank: filters.bank || undefined,
        day: filters.days.length ? filters.days.join(",") : undefined, search: filters.search || undefined,
        discount_type: filters.discount_type || undefined, state: filters.state || undefined,
        modality: filters.modality.length ? filters.modality.join(",") : undefined,
        category, page: filters.page, page_size: 24,
      })
    },
  })

  const todayLabel = new Date().toLocaleDateString("es-AR", { weekday: "long" })
  const todayDate = new Date().toLocaleDateString("es-AR", { day: "numeric", month: "long" })

  function chooseCategory(next: Category) {
    setCategory(next)
    setFilters(DEFAULT_FILTERS)
    setMyPromosMode(false)
  }

  return (
    <div className="min-h-dvh overflow-x-hidden">
      <a href="#promotions" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-[#102a4c]">Ir a promociones</a>
      <header className="sticky top-0 z-30 border-b border-[#dbe4ee]/80 bg-[#f5f7fb]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-18 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3 sm:gap-7">
            <Link href="/" className="display flex shrink-0 items-center gap-2 text-base font-semibold tracking-[-0.05em] text-[#102a4c]" aria-label="Ir al inicio de PromoAR">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-[#102a4c] text-xs font-bold text-[#b8f36b]">P</span>
              PROMOAR
            </Link>
            <nav aria-label="Categorías" className="flex items-center gap-1 rounded-xl border border-[#dbe4ee] bg-white p-1">
              <button onClick={() => chooseCategory("supermarket")} aria-pressed={category === "supermarket"} className={`inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition-colors sm:px-3 sm:text-sm ${category === "supermarket" ? "bg-[#102a4c] text-white" : "text-[#52657d] hover:bg-[#edf2f7] hover:text-[#102a4c]"}`}>
                <ShoppingCart className="h-3.5 w-3.5" aria-hidden="true" /><span className="hidden sm:inline">Supermercados</span><span className="sm:hidden">Súper</span>
              </button>
              <button onClick={() => chooseCategory("fuel")} aria-pressed={category === "fuel"} className={`inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition-colors sm:px-3 sm:text-sm ${category === "fuel" ? "bg-[#102a4c] text-white" : "text-[#52657d] hover:bg-[#edf2f7] hover:text-[#102a4c]"}`}>
                <Fuel className="h-3.5 w-3.5" aria-hidden="true" /><span>Combustible</span>
              </button>
            </nav>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            <Button variant="outline" size="sm" onClick={toggleTodayOnly} className={`hidden min-h-9 border-[#cbd8e6] bg-white text-[#102a4c] hover:bg-[#edf2f7] md:inline-flex ${todayOnly ? "border-[#102a4c] bg-[#102a4c] text-white hover:bg-[#102a4c] hover:text-white" : ""}`}>
              <CalendarDays className="h-3.5 w-3.5" /> Hoy
            </Button>
            {user && <Button variant={myPromosMode ? "default" : "outline"} size="sm" onClick={() => { if (!hasPaymentMethods) { router.push("/profile"); return } setMyPromosMode((value) => !value); setFilters(DEFAULT_FILTERS) }} className="hidden min-h-9 border-[#cbd8e6] bg-white text-[#102a4c] hover:bg-[#edf2f7] sm:inline-flex"><CreditCard className="h-3.5 w-3.5" /> Mis promos</Button>}
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-7 px-4 py-6 sm:px-6 sm:py-10">
        <section className="enter relative overflow-hidden rounded-[1.5rem] bg-[#102a4c] px-6 py-8 text-white sm:px-10 sm:py-11">
          <div className="pointer-events-none absolute inset-y-0 right-0 w-[45%] bg-[linear-gradient(135deg,transparent_0%,rgb(184_243_107_/_0.16)_100%)]" />
          <div className="relative grid items-end gap-8 lg:grid-cols-[1.25fr_.75fr]">
            <div className="max-w-2xl">
              <p className="mb-4 inline-flex items-center gap-2 text-xs font-semibold text-[#b8f36b]"><span className="h-1.5 w-1.5 rounded-full bg-[#b8f36b]" /> Datos actualizados · {todayDate}</p>
              <h1 className="display max-w-xl text-4xl font-semibold leading-[1.06] tracking-[-0.06em] sm:text-6xl">Pagá mejor en cada compra.</h1>
              <p className="mt-5 max-w-lg text-base leading-relaxed text-[#d9e3ef]">Promociones bancarias de supermercados y combustible, con condiciones, topes y días para decidir antes de llegar a la caja.</p>
              <button onClick={toggleTodayOnly} className="mt-7 inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#b8f36b] px-4 text-sm font-semibold text-[#102a4c] transition-colors hover:bg-[#d4ff9e]">Ver las de hoy <ArrowUpRight className="h-4 w-4" /></button>
            </div>
            <aside className="grid gap-px overflow-hidden rounded-2xl border border-white/15 bg-white/10 backdrop-blur-sm sm:grid-cols-3 lg:grid-cols-1" aria-label="Resumen de PromoAR">
              <div className="p-4"><p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#b8f36b]">Categoría</p><p className="mt-1 text-lg font-semibold">{category === "fuel" ? "Combustible" : "Supermercados"}</p></div>
              <div className="border-white/10 p-4 sm:border-l lg:border-l-0 lg:border-t"><p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#b8f36b]">Promos activas</p><p className="mt-1 text-lg font-semibold">{statsLoading ? "…" : (stats?.total_promotions ?? 0).toLocaleString("es-AR")}</p></div>
              <div className="border-white/10 p-4 sm:border-l lg:border-l-0 lg:border-t"><p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#b8f36b]">Buscá por</p><p className="mt-1 text-sm font-medium">Banco, día o comercio</p></div>
            </aside>
          </div>
        </section>

        <div className="grid gap-3 text-sm text-[#52657d] sm:grid-cols-3">
          {["Vigencia y condiciones a la vista", "Topes y medios de pago claros", "Datos extraídos de sitios oficiales"].map((item) => <p key={item} className="flex items-center gap-2"><Check className="h-4 w-4 shrink-0 text-[#2758d8]" aria-hidden="true" />{item}</p>)}
        </div>

        <PromoAssistant token={token} />

        <StatsBar stats={stats ?? null} loading={statsLoading} />

        {!myPromosMode && <section className="surface enter rounded-2xl p-4 sm:p-6" style={{ animationDelay: "70ms" }}><div className="mb-5 flex items-end justify-between gap-4"><div><p className="eyebrow">Explorá beneficios</p><h2 className="display mt-1 text-xl font-semibold tracking-[-0.045em] text-[#102a4c]">Encontrá cómo te conviene pagar</h2></div><button onClick={toggleTodayOnly} className="hidden text-sm font-semibold text-[#2758d8] hover:text-[#102a4c] sm:block">Solo hoy</button></div><FilterBar key={category} filters={filters} banks={banks} supermarkets={supermarkets} category={category} onChange={updateFilters} onReset={resetFilters} totalResults={promos?.total ?? 0} loading={isFetching} /></section>}

        {myPromosMode && <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#b8f36b] bg-[#efffdc] px-4 py-3 text-[#102a4c]"><p className="text-sm font-medium"><span className="font-semibold">Tus promos de {todayLabel}</span> · {promos?.total ?? 0} resultados para tus medios de pago</p><Button variant="ghost" size="sm" onClick={resetFilters} className="text-[#102a4c] hover:bg-[#dff5bd]">Ver todas</Button></div>}

        {error && <div role="alert" className="flex items-start gap-3 rounded-xl border border-[#f0b7b2] bg-[#fff3f2] px-4 py-3 text-sm text-[#8f2d28]"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>No se pudo conectar con la API. Verificá que el backend esté corriendo y reintentá.</span></div>}

        <div id="promotions"><PromoGrid promotions={promos?.data ?? []} loading={promosLoading || isFetching} page={promos?.page ?? 1} pages={promos?.pages ?? 1} total={promos?.total ?? 0} layout={filters.supermarket ? "table" : "grid"} marketName={filters.supermarket || undefined} onPageChange={(page) => updateFilters({ page })} /></div>
      </main>

      <footer className="mx-auto mt-10 max-w-7xl border-t border-[#dbe4ee] px-4 py-7 text-sm text-[#52657d] sm:px-6"><span className="display mr-2 font-semibold tracking-[-0.04em] text-[#102a4c]">PROMOAR</span> Información extraída de sitios oficiales. Confirmá las condiciones antes de pagar.</footer>
    </div>
  )
}
