"use client"

import { PromoCard } from "./PromoCard"
import { BankBadge } from "./BankBadge"
import { DiscountBadge } from "./DiscountBadge"
import { SupermarketLogo } from "./SupermarketLogo"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight, LayoutGrid, TableProperties } from "lucide-react"
import type { Promotion } from "@/lib/types"

interface Props {
  promotions: Promotion[]
  loading: boolean
  page: number
  pages: number
  total: number
  layout: "grid" | "table"
  marketName?: string
  onPageChange: (page: number) => void
}

function PromotionTable({ promotions, marketName }: { promotions: Promotion[]; marketName?: string }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-[#dbe4ee] bg-white shadow-[0_14px_36px_rgb(16_42_76_/_0.07)]">
      <header className="flex items-center justify-between gap-4 bg-[#102a4c] px-5 py-4 text-white sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          {marketName && <SupermarketLogo name={marketName} showLabel={false} />}
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#b8f36b]">Listado del súper</p>
            <h3 className="display truncate text-lg font-semibold tracking-[-0.04em]">{marketName || "Promociones seleccionadas"}</h3>
          </div>
        </div>
        <span className="hidden rounded-full border border-white/15 px-3 py-1 text-xs font-bold text-white/75 sm:block">Compará beneficio por beneficio</span>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead className="bg-[#edf2f7] text-[10px] font-semibold uppercase tracking-[0.13em] text-[#52657d]">
            <tr>
              <th scope="col" className="whitespace-nowrap px-5 py-3 sm:px-6">Día</th>
              <th scope="col" className="whitespace-nowrap px-4 py-3">Banco / billetera</th>
              <th scope="col" className="whitespace-nowrap px-4 py-3">Descuento</th>
              <th scope="col" className="whitespace-nowrap px-4 py-3">Tope</th>
              <th scope="col" className="px-4 py-3">Condición</th>
              <th scope="col" className="whitespace-nowrap px-5 py-3 sm:px-6">Vigencia</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5ebf2]">
            {promotions.map((promo) => {
              const entity = promo.bank || promo.wallet || "Sin entidad"
              const limit = promo.tope || promo.max_discount || "Sin tope informado"
              const validity = promo.valid_until ? `Hasta ${promo.valid_until}` : promo.valid_from ? `Desde ${promo.valid_from}` : "Ver condiciones"

              return (
                <tr key={promo.id} className="transition-colors hover:bg-[#f5f8fc]">
                  <td className="whitespace-nowrap px-5 py-4 align-top text-sm font-semibold text-[#102a4c] sm:px-6">{promo.valid_days || "Todos los días"}</td>
                  <td className="px-4 py-4 align-top"><BankBadge name={entity} size="sm" showLabel /></td>
                  <td className="px-4 py-4 align-top"><DiscountBadge discount={promo.discount || "Beneficio"} /></td>
                  <td className="max-w-48 px-4 py-4 align-top text-sm font-semibold leading-snug text-[#102a4c]">{limit}</td>
                  <td className="min-w-72 px-4 py-4 align-top text-sm leading-snug text-[#52657d]">{promo.title}</td>
                  <td className="whitespace-nowrap px-5 py-4 align-top text-xs font-medium text-[#52657d] sm:px-6">{validity}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-[#e5ebf2] px-5 py-3 text-xs text-[#52657d] sm:px-6">Deslizá horizontalmente para ver todas las columnas en pantallas chicas.</p>
    </section>
  )
}

export function PromoGrid({ promotions, loading, page, pages, total, layout, marketName, onPageChange }: Props) {
  if (loading && promotions.length === 0) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {[...Array(12)].map((_, i) => (
          <Skeleton key={i} className="h-40 rounded-xl" />
        ))}
      </div>
    )
  }

  if (!loading && promotions.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[#b7c7d8] bg-white py-16 text-center text-[#52657d]">
        <p className="display text-xl font-semibold text-[#102a4c]">No encontramos promos por acá.</p>
        <p className="mt-1 text-sm">Probá con otros filtros o volvé a mirar mañana.</p>
      </div>
    )
  }

  const pageNumbers: number[] = []
  const maxVisible = 5
  let start = Math.max(1, page - Math.floor(maxVisible / 2))
  const end = Math.min(pages, start + maxVisible - 1)
  start = Math.max(1, end - maxVisible + 1)
  for (let i = start; i <= end; i++) pageNumbers.push(i)

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-4 px-1">
        <div>
          <p className="eyebrow">{layout === "table" ? "Compará" : "Vigentes"}</p>
          <h2 className="display text-3xl font-semibold tracking-[-0.055em] text-[#102a4c]">{layout === "table" ? `Promos de ${marketName || "este súper"}` : "Promos para esta semana"}</h2>
        </div>
        <div className="hidden items-center gap-2 text-sm font-medium text-[#52657d] sm:flex">
          {layout === "table" ? <TableProperties className="h-4 w-4" aria-hidden="true" /> : <LayoutGrid className="h-4 w-4" aria-hidden="true" />}
          {total.toLocaleString("es-AR")} resultados
        </div>
      </div>
      {layout === "table" ? (
        <div className={loading ? "pointer-events-none opacity-40 transition-opacity duration-150" : "transition-opacity duration-150"}>
          <PromotionTable promotions={promotions} marketName={marketName} />
        </div>
      ) : (
        <div
          className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 transition-opacity duration-150 ${loading ? "opacity-40 pointer-events-none" : ""}`}
        >
          {promotions.map((promo) => (
            <PromoCard key={promo.id} promo={promo} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            aria-label="Ir a la página anterior"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>

          {start > 1 && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 text-xs"
                onClick={() => onPageChange(1)}
              >
                1
              </Button>
              {start > 2 && <span className="text-xs text-slate-400 px-1">...</span>}
            </>
          )}

          {pageNumbers.map((n) => (
            <Button
              key={n}
              variant={n === page ? "default" : "ghost"}
              size="sm"
              className="h-8 w-8 p-0 text-xs"
              onClick={() => onPageChange(n)}
            >
              {n}
            </Button>
          ))}

          {end < pages && (
            <>
              {end < pages - 1 && <span className="text-xs text-slate-400 px-1">...</span>}
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 text-xs"
                onClick={() => onPageChange(pages)}
              >
                {pages}
              </Button>
            </>
          )}

          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
            aria-label="Ir a la página siguiente"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>

          <span className="text-xs text-slate-400 ml-2">
            {total.toLocaleString("es-AR")} promos
          </span>
        </div>
      )}
    </div>
  )
}
