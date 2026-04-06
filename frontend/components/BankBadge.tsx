"use client"

import Image from "next/image"
import { getBankMeta } from "@/lib/bank-logos"
import { clsx } from "clsx"

interface Props {
  name: string | null | undefined
  size?: "sm" | "md"
  showLabel?: boolean
}

export function BankBadge({ name, size = "sm", showLabel = true }: Props) {
  const meta = getBankMeta(name)
  const avatarSize = size === "sm" ? "w-6 h-6 text-[9px]" : "w-9 h-9 text-xs"
  const imgPx = size === "sm" ? 24 : 36

  return (
    <span className="inline-flex items-center gap-1.5">
      {meta.logoUrl ? (
        <span className={clsx("rounded-full overflow-hidden shrink-0 flex items-center justify-center", avatarSize)} title={meta.label}>
          <Image
            src={meta.logoUrl}
            alt={meta.label}
            width={imgPx}
            height={imgPx}
            className="object-contain w-full h-full"
          />
        </span>
      ) : (
        <span
          className={clsx("rounded-full font-bold flex items-center justify-center shrink-0", avatarSize)}
          style={{ background: meta.color, color: meta.textColor }}
          title={meta.label}
        >
          {meta.initials}
        </span>
      )}
      {showLabel && (
        <span className="text-xs font-medium text-slate-700 truncate max-w-[110px]">{meta.label}</span>
      )}
    </span>
  )
}
