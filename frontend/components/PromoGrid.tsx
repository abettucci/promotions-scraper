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
      <div className="text-center py-16 text-slate-500">
        <p className="text-lg font-medium">Sin resultados</p>
        <p className="text-sm mt-1">Probá con otros filtros</p>
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
    <div className="space-y-4">
      <div
        className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 transition-opacity duration-150 ${loading ? "opacity-40 pointer-events-none" : ""}`}
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
