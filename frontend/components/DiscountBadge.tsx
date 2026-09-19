"use client"

import { clsx } from "clsx"

interface Props {
  discount: string | null | undefined
  className?: string
}

function classify(discount: string) {
  const d = discount.toLowerCase()
  if (d.includes("cuota") || d.includes("csi")) return "cuotas"
  if (d.includes("cashback") || d.includes("reintegro")) return "cashback"
  if (d.includes("%")) return "percent"
  if (d.includes("x2") || d.includes("x3") || d.includes("2x1") || d.includes("3x2")) return "bundle"
  return "other"
}

const STYLES = {
  percent:  "bg-[#efffdc] text-[#36561a] border-[#b8f36b]",
  cuotas:   "bg-[#eef3ff] text-[#1f4ab8] border-[#b9c9fb]",
  cashback: "bg-[#f3efff] text-[#6344aa] border-[#d5c7fb]",
  bundle:   "bg-[#fff6df] text-[#765410] border-[#edd292]",
  other:    "bg-[#edf2f7] text-[#40536b] border-[#d4dee9]",
}

export function DiscountBadge({ discount, className }: Props) {
  if (!discount) return null
  const type = classify(discount)

  return (
    <span
      className={clsx(
        "inline-block rounded-lg border px-2 py-1 text-center text-[11px] font-semibold tracking-wide uppercase leading-tight",
        STYLES[type],
        className
      )}
    >
      {discount}
    </span>
  )
}
