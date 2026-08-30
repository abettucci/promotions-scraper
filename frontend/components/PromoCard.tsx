"use client"

import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { BankBadge } from "./BankBadge"
import { DiscountBadge } from "./DiscountBadge"
import { DaysBadge } from "./DaysBadge"
import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react"
import type { Promotion } from "@/lib/types"
import { clsx } from "clsx"
import { SupermarketLogo } from "./SupermarketLogo"

interface Props {
  promo: Promotion
}

const SUPERMARKET_COLORS: Record<string, string> = {
  carrefour: "bg-blue-600",
  "supermercados día": "bg-red-500",
  "coto digital": "bg-yellow-500",
  "jumbo (cencosud)": "bg-green-600",
  "más online (changomás)": "bg-orange-500",
}

function supermarketColor(name: string) {
  const key = name.toLowerCase()
  for (const [k, v] of Object.entries(SUPERMARKET_COLORS)) {
    if (key.includes(k)) return v
  }
  return "bg-slate-500"
}

function safePromotionUrl(value: string | null): string | null {
  if (!value) return null

  try {
    const url = new URL(value)
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null
  } catch {
    return null
  }
}

export function PromoCard({ promo }: Props) {
  const [expanded, setExpanded] = useState(false)

  // Ensure these are always arrays to prevent .map() crash if API returns non-array
  const exclusions = Array.isArray(promo.exclusions) ? promo.exclusions : []
  const requirements = Array.isArray(promo.requirements) ? promo.requirements : []

  // Only show tope if it contains actual digits (filter out "$." or just symbols)
  const meaningfulTope = promo.tope && /\d/.test(promo.tope) ? promo.tope : null

  // Truncate long payment_method — Badge has whitespace-nowrap so JS truncation is safest
  const paymentMethodShort = promo.payment_method
    ? promo.payment_method.length > 40
      ? promo.payment_method.slice(0, 40) + "…"
      : promo.payment_method
    : null

  const entity = promo.bank || promo.wallet
  const promotionUrl = safePromotionUrl(promo.url)

  const formatDate = (d: string | null | undefined) => {
    if (!d) return null
    try {
      // Try ISO format YYYY-MM-DD
      let date = new Date(d + "T00:00:00")
      if (!isNaN(date.getTime())) {
        return date.toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" })
      }
      // Try DD/MM/YYYY or DD/MM/YY
      const parts = d.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/)
      if (parts) {
        let year = parseInt(parts[3])
        if (year < 100) year += 2000
        date = new Date(year, parseInt(parts[2]) - 1, parseInt(parts[1]))
        if (!isNaN(date.getTime())) {
          return date.toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" })
        }
      }
      return null
    } catch {
      return null
    }
  }

  const hasDetails =
    exclusions.length > 0 ||
    requirements.length > 0 ||
    !!meaningfulTope ||
    !!promo.min_purchase ||
    !!formatDate(promo.valid_from) ||
    !!formatDate(promo.valid_until)

  return (
    <Card className="group relative overflow-hidden rounded-[1.45rem] border-[#10243e]/12 bg-[#fffdf8] shadow-[3px_3px_0_rgb(16_36_62_/_0.12)] transition-all duration-200 hover:-translate-y-1 hover:shadow-[7px_8px_0_#ffd84d]">
      {/* Left accent bar */}
      <span
        className={clsx("absolute left-0 top-0 bottom-0 w-1", supermarketColor(promo.supermarket_name))}
      />

      <CardContent className="relative pl-5 pr-4 pt-4 pb-4 space-y-3">
        {/* Header row: supermarket logo + discount */}
        <div className="flex items-start justify-between gap-2">
          <SupermarketLogo name={promo.supermarket_name} showLabel={true} />
          {promo.discount && <DiscountBadge discount={promo.discount} className="max-w-[100px] scale-105 origin-top-right" />}
        </div>

        {/* Title */}
        <p className="text-[15px] font-black tracking-[-0.025em] text-[#10243e] leading-snug">
          {promo.title}
        </p>

        {/* Bank / Wallet + Days on the same row */}
        <div className="flex items-center gap-2 flex-wrap">
          {promo.bank && <BankBadge name={promo.bank} size="sm" showLabel={true} />}
          {promo.wallet && <BankBadge name={promo.wallet} size="sm" showLabel={true} />}
          {!promo.bank && !promo.wallet && entity && <BankBadge name={entity} size="sm" showLabel={true} />}
          <DaysBadge validDays={promo.valid_days} />
        </div>

        {/* Validity dates */}
        {(() => {
          const from = formatDate(promo.valid_from)
          const until = formatDate(promo.valid_until)
          if (!from && !until) return null
          const label = from && until
            ? `${from} — ${until}`
            : from ? `Desde ${from}` : `Hasta ${until}`
          return (
            <p className="text-[11px] font-medium text-[#687487]">
              <span className="font-medium">Vigencia:</span> {label}
            </p>
          )
        })()}

        {/* Card type + payment method */}
        {(promo.card_type || paymentMethodShort) && (
          <div className="flex flex-wrap gap-1">
            {promo.card_type && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5">
                {promo.card_type}
              </Badge>
            )}
            {paymentMethodShort && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5" title={promo.payment_method ?? ""}>
                {paymentMethodShort}
              </Badge>
            )}
          </div>
        )}

        {/* Tags: sucursales + tope + min compra + exclusiones */}
        {(promo.store_types || meaningfulTope || promo.min_purchase || exclusions.length > 0) && (
          <div className="flex flex-wrap gap-1">
            {promo.store_types && promo.store_types.split(',').map(s => s.trim()).filter(Boolean).map((store, i) => (
              <Badge key={i} variant="outline" className="text-[10px] px-1.5 py-0 h-5">
                {store}
              </Badge>
            ))}
            {meaningfulTope && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 border-amber-300 bg-amber-50 text-amber-700">
                Tope: {meaningfulTope}
              </Badge>
            )}
            {promo.min_purchase && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 border-slate-300 text-slate-600">
                Min: {promo.min_purchase}
              </Badge>
            )}
            {exclusions.length > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 border-rose-200 bg-rose-50 text-rose-600">
                Excluye productos
              </Badge>
            )}
          </div>
        )}

        {/* Ver detalles toggle + link a la promoción */}
        {(hasDetails || promotionUrl) && (
          <div className="flex items-center justify-between gap-2 border-t border-[#10243e]/8 pt-2 mt-1">
            {hasDetails ? (
              <button
                onClick={() => setExpanded((v) => !v)}
                className="flex items-center gap-1 text-[11px] font-bold text-[#10243e] underline decoration-[#ffd84d] decoration-2 underline-offset-4 hover:text-[#ef5845]"
              >
                {expanded ? (
                  <>
                    <ChevronUp className="w-3 h-3" /> Ocultar detalles
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-3 h-3" /> Ver detalles
                  </>
                )}
              </button>
            ) : (
              <span />
            )}

            {promotionUrl && (
              <a
                href={promotionUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[11px] font-bold text-[#10243e] hover:text-[#ef5845] whitespace-nowrap"
              >
                Ver promoción <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        )}

        {hasDetails && (
          <>
            {expanded && (
              <div className="mt-2 space-y-2 text-[11px] text-slate-600 border-t pt-2">
                {meaningfulTope && (
                  <p><span className="font-semibold">Tope:</span> {meaningfulTope}</p>
                )}
                {promo.min_purchase && (
                  <p><span className="font-semibold">Compra mínima:</span> {promo.min_purchase}</p>
                )}
                {(() => {
                  const from = formatDate(promo.valid_from)
                  const until = formatDate(promo.valid_until)
                  if (!from && !until) return null
                  const text = from && until
                    ? `${from} — ${until}`
                    : from ? `Desde ${from}` : `Hasta ${until}`
                  return <p><span className="font-semibold">Vigencia:</span>{" "}{text}</p>
                })()}
                {requirements.length > 0 && (
                  <div>
                    <p className="font-semibold mb-0.5">Requisitos:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      {requirements.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {exclusions.length > 0 && (
                  <div>
                    <p className="font-semibold mb-0.5">Exclusiones:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      {exclusions.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {promo.acumulable !== null && promo.acumulable !== undefined && (
                  <p>
                    <span className="font-semibold">Acumulable:</span>{" "}
                    {promo.acumulable ? "Sí" : "No"}
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
