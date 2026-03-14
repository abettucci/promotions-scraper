"use client"

import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { BankBadge } from "./BankBadge"
import { DiscountBadge } from "./DiscountBadge"
import { DaysBadge } from "./DaysBadge"
import { ChevronDown, ChevronUp, Store } from "lucide-react"
import type { Promotion } from "@/lib/types"
import { clsx } from "clsx"

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
  const hasDetails =
    (promo.exclusions?.length > 0) ||
    (promo.requirements?.length > 0) ||
    promo.tope ||
    promo.min_purchase

  const entity = promo.bank || promo.wallet

  return (
    <Card className="relative overflow-hidden hover:shadow-md transition-shadow duration-200 border-slate-200">
      {/* Left accent bar */}
      <span
        className={clsx("absolute left-0 top-0 bottom-0 w-1", supermarketColor(promo.supermarket_name))}
      />

      <CardContent className="pl-4 pr-4 pt-3 pb-3 space-y-2">
        {/* Header row: supermarket + discount */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <Store className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span className="text-[11px] text-slate-500 font-medium truncate">
              {promo.supermarket_name}
            </span>
          </div>
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
        {(promo.card_type || promo.payment_method) && (
          <div className="flex flex-wrap gap-1">
            {promo.card_type && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5">
                {promo.card_type}
              </Badge>
            )}
            {promo.payment_method && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5">
                {promo.payment_method}
              </Badge>
            )}
          </div>
        )}

        {/* Days */}
        <DaysBadge validDays={promo.valid_days} />

        {/* Tope */}
        {promo.tope && !expanded && (
          <p className="text-[11px] text-slate-500">
            <span className="font-medium">Tope:</span> {promo.tope}
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
                {promo.tope && (
                  <p><span className="font-semibold">Tope:</span> {promo.tope}</p>
                )}
                {promo.min_purchase && (
                  <p><span className="font-semibold">Compra mínima:</span> {promo.min_purchase}</p>
                )}
                {promo.requirements && promo.requirements.length > 0 && (
                  <div>
                    <p className="font-semibold mb-0.5">Requisitos:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      {promo.requirements.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {promo.exclusions && promo.exclusions.length > 0 && (
                  <div>
                    <p className="font-semibold mb-0.5">Exclusiones:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      {promo.exclusions.map((e, i) => (
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
