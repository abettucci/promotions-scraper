"use client"

import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { BankBadge } from "./BankBadge"
import { DiscountBadge } from "./DiscountBadge"
import { DaysBadge } from "./DaysBadge"
import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react"
import type { Promotion } from "@/lib/types"
import { SupermarketLogo } from "./SupermarketLogo"

interface Props {
  promo: Promotion
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
    <Card className="group relative overflow-hidden rounded-2xl border-[#dbe4ee] bg-white py-0 shadow-[0_10px_28px_rgb(16_42_76_/_0.06)] transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:border-[#9cb5d0] hover:shadow-[0_16px_36px_rgb(16_42_76_/_0.12)]">
      <CardContent className="relative space-y-3 px-5 py-5">
        {/* Header row: supermarket logo + discount */}
        <div className="flex items-start justify-between gap-2">
          <SupermarketLogo name={promo.supermarket_name} showLabel={true} />
          {promo.discount && <DiscountBadge discount={promo.discount} className="max-w-[100px] scale-105 origin-top-right" />}
        </div>

        {/* Title */}
          <p className="text-[15px] font-semibold tracking-[-0.025em] text-[#102a4c] leading-snug">
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
            <p className="text-[11px] font-medium text-[#52657d]">
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
        {(promo.store_types || meaningfulTope || promo.min_purchase || requirements.length > 0 || exclusions.length > 0) && (
          <div className="flex flex-wrap gap-1">
            {promo.store_types && promo.store_types.split(',').map(s => s.trim()).filter(Boolean).map((store, i) => (
              <Badge key={i} variant="outline" className="text-[10px] px-1.5 py-0 h-5">
                {store}
              </Badge>
            ))}
            {meaningfulTope && (
              <Badge variant="outline" className="h-5 border-[#b8f36b] bg-[#efffdc] px-1.5 py-0 text-[10px] text-[#36561a]">
                Tope: {meaningfulTope}
              </Badge>
            )}
            {promo.min_purchase && (
              <Badge variant="outline" className="h-5 border-[#cbd8e6] px-1.5 py-0 text-[10px] text-[#52657d]">
                Min: {promo.min_purchase}
              </Badge>
            )}
            {requirements.length > 0 && (
              <Badge variant="outline" className="h-5 border-[#b9c9fb] bg-[#eef3ff] px-1.5 py-0 text-[10px] text-[#1f4ab8]">
                Requiere condición
              </Badge>
            )}
            {exclusions.length > 0 && (
              <Badge variant="outline" className="h-5 border-[#f0b7b2] bg-[#fff3f2] px-1.5 py-0 text-[10px] text-[#8f2d28]">
                Excluye productos
              </Badge>
            )}
          </div>
        )}

        {requirements.length > 0 && (
          <p className="rounded-lg border border-[#d7e1f8] bg-[#f5f8ff] px-3 py-2 text-[11px] leading-relaxed text-[#34517d]">
            <span className="font-semibold text-[#1f4ab8]">Condición:</span> {requirements[0]}
          </p>
        )}

        {/* Ver detalles toggle + link a la promoción */}
        {(hasDetails || promotionUrl) && (
          <div className="mt-1 flex items-center justify-between gap-2 border-t border-[#e5ebf2] pt-3">
            {hasDetails ? (
              <button
                onClick={() => setExpanded((v) => !v)}
                className="flex min-h-7 items-center gap-1 text-[11px] font-semibold text-[#2758d8] hover:text-[#102a4c]"
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
                className="flex min-h-7 items-center gap-1 text-[11px] font-semibold text-[#2758d8] hover:text-[#102a4c] whitespace-nowrap"
              >
                Ver promoción <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        )}

        {hasDetails && (
          <>
            {expanded && (
              <div className="mt-2 space-y-2 border-t border-[#e5ebf2] pt-3 text-[11px] text-[#52657d]">
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
