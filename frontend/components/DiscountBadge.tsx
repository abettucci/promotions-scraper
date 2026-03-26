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
  percent:  "bg-emerald-100 text-emerald-800 border-emerald-200",
  cuotas:   "bg-blue-100 text-blue-800 border-blue-200",
  cashback: "bg-violet-100 text-violet-800 border-violet-200",
  bundle:   "bg-amber-100 text-amber-800 border-amber-200",
  other:    "bg-slate-100 text-slate-700 border-slate-200",
}

export function DiscountBadge({ discount, className }: Props) {
  if (!discount) return null
  const type = classify(discount)

  return (
    <span
      className={clsx(
        "inline-block text-center px-2 py-0.5 rounded-full border text-[11px] font-semibold tracking-wide uppercase leading-tight",
        STYLES[type],
        className
      )}
    >
      {discount}
    </span>
  )
}
