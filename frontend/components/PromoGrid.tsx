"use client"

import { PromoCard } from "./PromoCard"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight } from "lucide-react"
import type { Promotion } from "@/lib/types"

interface Props {
  promotions: Promotion[]
  loading: boolean
  page: number
  pages: number
  total: number
  onPageChange: (page: number) => void
}

export function PromoGrid({ promotions, loading, page, pages, total, onPageChange }: Props) {
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
      <div className="rounded-[2rem] border border-dashed border-[#10243e]/25 bg-[#fffdf8] py-16 text-center text-[#687487]">
        <p className="text-xl font-black text-[#10243e]">No encontramos promos por acá.</p>
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
      <div className="flex items-end justify-between px-1">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#ef5845]">Selección</p>
          <h2 className="text-2xl font-black tracking-[-0.05em] text-[#10243e]">Promos para aprovechar</h2>
        </div>
        <p className="hidden text-sm font-medium text-[#687487] sm:block">{total.toLocaleString("es-AR")} resultados</p>
      </div>
      <div
        className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 transition-opacity duration-150 ${loading ? "opacity-40 pointer-events-none" : ""}`}
      >
        {promotions.map((promo) => (
          <PromoCard key={promo.id} promo={promo} />
        ))}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
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
