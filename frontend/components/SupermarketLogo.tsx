"use client"

import { useState } from "react"
import { getSupermarketMeta, getFaviconUrl } from "@/lib/supermarket-logos"

interface Props {
  name: string | null | undefined
  showLabel?: boolean
}

export function SupermarketLogo({ name, showLabel = true }: Props) {
  const [imgFailed, setImgFailed] = useState(false)
  const meta = getSupermarketMeta(name)
  const faviconUrl = getFaviconUrl(meta.domain)

  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="w-5 h-5 rounded-sm flex items-center justify-center shrink-0 overflow-hidden"
        style={{ background: imgFailed || !faviconUrl ? meta.color : "transparent" }}
        title={name ?? ""}
      >
        {!imgFailed && faviconUrl ? (
          <img
            src={faviconUrl}
            alt={name ?? ""}
            width={20}
            height={20}
            className="w-5 h-5 object-contain"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <span
            className="text-[8px] font-bold leading-none"
            style={{ color: meta.textColor }}
          >
            {meta.initials}
          </span>
        )}
      </span>
      {showLabel && (
        <span className="text-[11px] text-slate-500 font-medium truncate max-w-[120px]">
          {name}
        </span>
      )}
    </span>
  )
}
