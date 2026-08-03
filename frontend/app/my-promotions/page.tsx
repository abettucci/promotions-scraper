"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"
import { PromoCard } from "@/components/PromoCard"
import { Button } from "@/components/ui/button"
import {
  ArrowLeft, Settings, CalendarDays, ListFilter, Loader2, CreditCard,
} from "lucide-react"

export default function MyPromotionsPage() {
  const router = useRouter()
  const { user, token } = useAuthStore()
  const [todayOnly, setTodayOnly] = useState(true)

  useEffect(() => {
    if (!token) router.push("/login")
  }, [token, router])

  const { data, isLoading, error } = useQuery({
    queryKey: ["my-promotions", todayOnly],
    queryFn: () => api.getMyPromotions(token!, todayOnly),
    enabled: !!token,
  })

  if (!token || !user) return null

  const todayLabel = new Date().toLocaleDateString("es-AR", { weekday: "long" })
  const hasNoMethods = (user.payment_methods?.length ?? 0) === 0

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-slate-400 hover:text-slate-600 transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <span className="text-xl font-black text-slate-900 tracking-tight">PromoAR</span>
            <span className="text-slate-300 hidden sm:block">/</span>
            <span className="text-sm text-slate-500 hidden sm:block">Mis promociones</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={todayOnly ? "default" : "outline"}
              size="sm"
              onClick={() => setTodayOnly(true)}
              className="gap-1.5 text-sm"
            >
              <CalendarDays className="w-4 h-4" />
              Hoy
            </Button>
            <Button
              variant={!todayOnly ? "default" : "outline"}
              size="sm"
              onClick={() => setTodayOnly(false)}
              className="gap-1.5 text-sm"
            >
              <ListFilter className="w-4 h-4" />
              Todas
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/profile"><Settings className="w-4 h-4" /></Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* No methods configured */}
        {hasNoMethods && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 text-center">
            <CreditCard className="w-10 h-10 text-amber-400 mx-auto mb-3" />
            <h3 className="font-semibold text-amber-800 mb-1">No tenés métodos de pago configurados</h3>
            <p className="text-sm text-amber-700 mb-4">
              Configurá tus tarjetas y billeteras para ver las promos que aplican para vos.
            </p>
            <Button asChild size="sm">
              <Link href="/profile">Configurar ahora</Link>
            </Button>
          </div>
        )}

        {/* Header info */}
        {!hasNoMethods && (
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-900">
                {todayOnly ? `Promos de hoy — ${todayLabel}` : "Todas mis promociones"}
              </h1>
              <p className="text-sm text-slate-500 mt-0.5">
                Para tus {user.payment_methods.length} método{user.payment_methods.length !== 1 ? "s" : ""} de pago
              </p>
            </div>
            {data && (
              <span className="text-sm text-slate-500 bg-white border border-slate-200 px-3 py-1 rounded-full">
                {data.total} promo{data.total !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-16 gap-2 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Buscando tus promociones...</span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm">
            Error cargando promociones: {(error as Error).message}
          </div>
        )}

        {/* No results */}
        {!isLoading && !error && data && data.total === 0 && !hasNoMethods && (
          <div className="text-center py-16 text-slate-400">
            <CalendarDays className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium text-slate-600">
              {todayOnly
                ? `Hoy (${todayLabel}) no hay promos para tus métodos de pago`
                : "No hay promos activas para tus métodos de pago"}
            </p>
            {todayOnly && (
              <Button variant="ghost" size="sm" className="mt-3" onClick={() => setTodayOnly(false)}>
                Ver todas las promos activas
              </Button>
            )}
          </div>
        )}

        {/* Results by supermarket */}
        {data?.by_supermarket.map(({ supermarket, promotions }) => (
          <section key={supermarket}>
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
              {supermarket}
              <span className="ml-2 text-slate-300 font-normal normal-case tracking-normal">
                {promotions.length} promo{promotions.length !== 1 ? "s" : ""}
              </span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {promotions.map((promo) => (
                <PromoCard key={promo.id} promo={promo} />
              ))}
            </div>
          </section>
        ))}
      </main>
    </div>
  )
}
