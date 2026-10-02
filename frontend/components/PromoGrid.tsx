"use client"

import { PromoCard } from "./PromoCard"
import { BankBadge } from "./BankBadge"
import { DiscountBadge } from "./DiscountBadge"
import { SupermarketLogo } from "./SupermarketLogo"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { useEffect, useState } from "react"
import { AlertTriangle, ChevronLeft, ChevronRight, ExternalLink, FileText, LayoutGrid, TableProperties, X } from "lucide-react"
import { api } from "@/lib/api"
import type { Promotion, PromotionDetails } from "@/lib/types"
import { benefitLabel } from "@/lib/benefit"
import { channelLabel, entityLabel, paymentMethods } from "@/lib/promo-meta"

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

const OFFICIAL_PROMOTION_DOMAINS = [
  "carrefour.com.ar", "coto.com.ar", "cotodigital.com.ar", "supermercadosdia.com.ar",
  "diaonline.supermercadosdia.com.ar", "jumbo.com.ar", "masonline.com.ar", "mercadopago.com.ar",
  "shell.com.ar", "axionenergy.com", "pumaenergyarg.com.ar", "modo.com.ar", "macro.com.ar",
  "galicia.ar", "bna.com.ar", "bancoprovincia.com.ar", "brubank.com", "personal.com.ar",
  "buepp.com.ar", "lanacion.com.ar",
]

function safeOfficialPromotionUrl(value: string | null | undefined): string | null {
  if (!value) return null
  try {
    const url = new URL(value)
    const hostname = url.hostname.toLowerCase()
    const officialDomain = OFFICIAL_PROMOTION_DOMAINS.some(
      (domain) => hostname === domain || hostname.endsWith(`.${domain}`),
    )
    return url.protocol === "https:" && officialDomain ? url.href : null
  } catch {
    return null
  }
}

function conditionMarkers(promo: Promotion) {
  return {
    channel: channelLabel(promo),
    exclusions: Array.isArray(promo.exclusions) ? promo.exclusions : [],
  }
}

function ConditionsDialog({ promo, onClose }: { promo: Promotion; onClose: () => void }) {
  const [details, setDetails] = useState<PromotionDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    api.getPromotion(promo.id)
      .then((response) => { if (!cancelled) setDetails(response) })
      .catch(() => { if (!cancelled) setFailed(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [promo])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [promo, onClose])

  // Mientras la API se actualiza (o si existe una fila histórica incompleta),
  // nunca ocultamos condiciones que ya estaban presentes en el listado.
  const display: Promotion | PromotionDetails = details
    ? {
        ...details,
        exclusions: details.exclusions.length > 0 ? details.exclusions : promo.exclusions,
        requirements: details.requirements.length > 0 ? details.requirements : promo.requirements,
      }
    : promo
  const exclusions = Array.isArray(display.exclusions) ? display.exclusions : []
  const requirements = Array.isArray(display.requirements) ? display.requirements : []
  const sourceUrl = safeOfficialPromotionUrl(display.url)
  const terms = details?.raw_text || details?.terms_raw || ""

  return (
    <div className="fixed inset-0 z-[70] flex items-end bg-[#071a31]/55 p-3 backdrop-blur-sm sm:items-center sm:justify-center sm:p-6" onMouseDown={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="conditions-title"
        className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-[1.5rem] border border-[#dce6d2] bg-[#fcfdf9] shadow-[0_26px_90px_rgb(7_26_49_/_0.34)]"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-[#e1e8dc] bg-[#fcfdf9]/95 px-5 py-5 backdrop-blur sm:px-7">
          <div>
            <p className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-[#c9e79e] bg-[#f3ffe6] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#3d6626]">
              <FileText className="h-3 w-3" /> Condiciones de la promo
            </p>
            <h2 id="conditions-title" className="display text-xl font-semibold tracking-[-0.045em] text-[#102a4c]">{display.title}</h2>
            <p className="mt-1 text-sm text-[#52657d]">{display.supermarket_name}</p>
          </div>
          <button type="button" onClick={onClose} className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-[#d6e0eb] text-[#52657d] transition hover:border-[#102a4c] hover:text-[#102a4c]" aria-label="Cerrar condiciones">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-5 px-5 py-5 sm:px-7 sm:py-6">
          {loading && <p className="rounded-xl bg-[#f1f5ef] px-4 py-3 text-sm text-[#52657d]">Cargando condiciones publicadas…</p>}
          {failed && <p className="rounded-xl border border-[#f0c7c3] bg-[#fff5f4] px-4 py-3 text-sm text-[#9c4138]">No pudimos cargar el detalle ahora. Podés consultar la fuente oficial.</p>}

          <div className="grid gap-3 sm:grid-cols-3">
            <Detail label="Modalidad" value={display.store_types || "No informada"} />
            <Detail label="Medio de pago" value={display.payment_method || display.card_type || "No informado"} />
            <Detail label="Tope" value={display.tope || display.max_discount || "No informado"} />
            <Detail label="Método" value={paymentMethods(display).join(" · ") || "No informado"} />
            <Detail label="Compra mínima" value={display.min_purchase || "Sin mínimo informado"} />
          </div>

          {requirements.length > 0 && (
            <div className="rounded-xl border border-[#d4e0f7] bg-[#f4f7ff] px-4 py-3 text-sm leading-relaxed text-[#34517d]">
              <p className="mb-1 font-semibold text-[#1f4ab8]">Requisitos</p>
              <ul className="space-y-1">
                {requirements.map((requirement, index) => <li key={`${requirement}-${index}`}>• {requirement}</li>)}
              </ul>
            </div>
          )}

          {exclusions.length > 0 && (
            <div className="rounded-xl border border-[#efbbb5] bg-[#fff4f2] px-4 py-3 text-sm leading-relaxed text-[#7f332d]">
              <p className="mb-1 flex items-center gap-1.5 font-semibold"><AlertTriangle className="h-4 w-4" /> Aplican exclusiones</p>
              <ul className="space-y-1">
                {exclusions.map((exclusion, index) => <li key={`${exclusion}-${index}`}>• {exclusion}</li>)}
              </ul>
            </div>
          )}

          {terms && (
            <div>
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.12em] text-[#52657d]">Texto publicado</p>
              <p className="whitespace-pre-wrap rounded-xl border border-[#e0e7dd] bg-white px-4 py-3 text-sm leading-relaxed text-[#52657d]">{terms}</p>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#e1e8dc] pt-4">
            <p className="text-xs leading-relaxed text-[#73836e]">Verificá el texto oficial antes de pagar: las condiciones pueden cambiar.</p>
            {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-9 items-center gap-1.5 rounded-full bg-[#102a4c] px-4 text-xs font-bold text-white transition hover:bg-[#183b67]">Fuente oficial <ExternalLink className="h-3.5 w-3.5" /></a>}
          </div>
        </div>
      </section>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-[#e0e7dd] bg-white px-3.5 py-3"><p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#71826d]">{label}</p><p className="mt-1 text-sm font-semibold leading-snug text-[#102a4c]">{value}</p></div>
}

function PromotionTable({ promotions, marketName, onOpenConditions }: { promotions: Promotion[]; marketName?: string; onOpenConditions: (promo: Promotion) => void }) {
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
        <table className="w-full min-w-[980px] border-collapse text-left">
          <thead className="bg-[#edf2f7] text-[10px] font-semibold uppercase tracking-[0.13em] text-[#52657d]">
            <tr>
              <th scope="col" className="whitespace-nowrap px-5 py-3 sm:px-6">Día</th>
              <th scope="col" className="whitespace-nowrap px-4 py-3">Banco / billetera</th>
              <th scope="col" className="whitespace-nowrap px-4 py-3">Descuento</th>
              <th scope="col" className="whitespace-nowrap px-4 py-3">Método</th>
              <th scope="col" className="whitespace-nowrap px-4 py-3">Tope</th>
              <th scope="col" className="whitespace-nowrap px-4 py-3">Mínimo</th>
              <th scope="col" className="px-4 py-3">Condición</th>
              <th scope="col" className="whitespace-nowrap px-5 py-3 sm:px-6">Vigencia</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5ebf2]">
            {promotions.map((promo) => {
              const entity = entityLabel(promo)
              const limit = promo.tope || promo.max_discount || "Sin tope informado"
              const validity = promo.valid_until ? `Hasta ${promo.valid_until}` : promo.valid_from ? `Desde ${promo.valid_from}` : "Vigencia en condiciones"
              const markers = conditionMarkers(promo)
              const methods = paymentMethods(promo)

              return (
                <tr key={promo.id} className="transition-colors hover:bg-[#f5f8fc]">
                  <td className="whitespace-nowrap px-5 py-4 align-top text-sm font-semibold text-[#102a4c] sm:px-6">{promo.valid_days || "Todos los días"}</td>
                  <td className="px-4 py-4 align-top"><BankBadge name={entity} size="sm" showLabel /></td>
                  <td className="px-4 py-4 align-top"><DiscountBadge discount={benefitLabel(promo)} /></td>
                  <td className="px-4 py-4 align-top">
                    {methods.length > 0
                      ? <div className="flex flex-wrap gap-1">{methods.map((method) => <span key={method} className="whitespace-nowrap rounded-full border border-[#d6e0eb] bg-[#f5f8fc] px-2 py-0.5 text-[11px] font-bold text-[#102a4c]">{method}</span>)}</div>
                      : <span className="text-xs text-[#8a9ab0]">No informado</span>}
                  </td>
                  <td className="max-w-48 px-4 py-4 align-top text-sm font-semibold leading-snug text-[#102a4c]">{limit}</td>
                  <td className="whitespace-nowrap px-4 py-4 align-top text-sm font-semibold text-[#102a4c]">{promo.min_purchase ? `Desde ${promo.min_purchase}` : <span className="text-xs font-normal text-[#8a9ab0]">Sin mínimo</span>}</td>
                  <td className="min-w-72 px-4 py-4 align-top text-sm leading-snug text-[#52657d]">
                    <p>{promo.title}</p>
                    {(markers.channel || markers.exclusions.length > 0) && <div className="mt-2 flex flex-wrap gap-1.5">
                      {markers.channel && <span className="rounded-full border border-[#c7d9f7] bg-[#f0f5ff] px-2 py-0.5 text-[10px] font-bold text-[#315fae]">{markers.channel}</span>}
                      {markers.exclusions.length > 0 && <span className="rounded-full border border-[#f0b7b2] bg-[#fff3f2] px-2 py-0.5 text-[10px] font-bold text-[#8f2d28]">Aplica exclusiones</span>}
                    </div>}
                    {/* Las exclusiones concretas (marcas, rubros) se ven sin abrir el
                        legal; la lista completa queda en "Ver condiciones". */}
                    {markers.exclusions.length > 0 && <>
                      <p className="mt-2 line-clamp-2 text-xs text-[#8f2d28]">Excluye: {markers.exclusions.join(" ")}</p>
                      <button type="button" onClick={() => onOpenConditions(promo)} className="mt-1 text-xs font-bold text-[#8f2d28] underline">Ver todas las exclusiones</button>
                    </>}
                  </td>
                  <td className="px-5 py-4 align-top text-xs font-medium text-[#52657d] sm:px-6">
                    <p className="whitespace-nowrap">{validity}</p>
                    <button type="button" onClick={() => onOpenConditions(promo)} className="mt-2 inline-flex items-center gap-1 font-bold text-[#2758d8] transition hover:text-[#102a4c]" aria-label={`Ver condiciones de ${promo.title}`}>
                      <FileText className="h-3.5 w-3.5" /> Ver condiciones
                    </button>
                  </td>
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
  const [conditionPromo, setConditionPromo] = useState<Promotion | null>(null)
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
          <PromotionTable promotions={promotions} marketName={marketName} onOpenConditions={setConditionPromo} />
        </div>
      ) : (
        <div
          className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 transition-opacity duration-150 ${loading ? "opacity-40 pointer-events-none" : ""}`}
        >
          {promotions.map((promo) => (
            <PromoCard key={promo.id} promo={promo} onOpenConditions={setConditionPromo} />
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
      {conditionPromo && <ConditionsDialog key={conditionPromo.id} promo={conditionPromo} onClose={() => setConditionPromo(null)} />}
    </div>
  )
}
