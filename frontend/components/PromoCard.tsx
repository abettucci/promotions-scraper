"use client"

import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { BankBadge } from "./BankBadge"
import { DiscountBadge } from "./DiscountBadge"
import { DaysBadge } from "./DaysBadge"
import { ChevronDown, ChevronUp } from "lucide-react"
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
    <Card className="relative overflow-hidden hover:shadow-md transition-shadow duration-200 border-slate-200">
      {/* Left accent bar */}
      <span
        className={clsx("absolute left-0 top-0 bottom-0 w-1", supermarketColor(promo.supermarket_name))}
      />

      <CardContent className="pl-4 pr-4 pt-3 pb-3 space-y-2">
        {/* Header row: supermarket logo + discount */}
        <div className="flex items-start justify-between gap-2">
          <SupermarketLogo name={promo.supermarket_name} showLabel={true} />
          {promo.discount && <DiscountBadge discount={promo.discount} className="shrink-0" />}
        </div>

        {/* Title */}
        <p className="text-sm font-semibold text-slate-800 leading-snug line-clamp-2">
          {promo.title}
        </p>

        {/* Bank / Wallet */}
        {entity && (
          <BankBadge name={entity} size="sm" showLabel={true} />
        )}

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

        {/* Store types (online / presencial) */}
        {promo.store_types && (
          <p className="text-[11px] text-slate-500 truncate">
            <span className="font-medium">Modalidad:</span> {promo.store_types}
          </p>
        )}

        {/* Days */}
        <DaysBadge validDays={promo.valid_days} />

        {/* Tope */}
        {meaningfulTope && !expanded && (
          <p className="text-[11px] text-slate-500">
            <span className="font-medium">Tope:</span> {meaningfulTope}
          </p>
        )}

        {/* Expandable T&C section */}
        {hasDetails && (
          <>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 font-medium mt-1"
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
