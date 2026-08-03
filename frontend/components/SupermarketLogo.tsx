"use client"

import { useState } from "react"

interface SupermarketMeta {
  color: string
  textColor: string
  initials: string
  domain: string
}

const SUPERMARKET_META: Record<string, SupermarketMeta> = {
  carrefour:    { color: "#004F9F", textColor: "#fff", initials: "CF", domain: "carrefour.com.ar" },
  día:          { color: "#E31937", textColor: "#fff", initials: "DÍ", domain: "supermercadosdia.com.ar" },
  dia:          { color: "#E31937", textColor: "#fff", initials: "DÍ", domain: "supermercadosdia.com.ar" },
  coto:         { color: "#F5A623", textColor: "#000", initials: "CO", domain: "cotodigital.com.ar" },
  jumbo:        { color: "#00A651", textColor: "#fff", initials: "JU", domain: "jumbo.com.ar" },
  cencosud:     { color: "#00A651", textColor: "#fff", initials: "JU", domain: "jumbo.com.ar" },
  masonline:    { color: "#FF6B00", textColor: "#fff", initials: "MO", domain: "masonline.com.ar" },
  changomás:    { color: "#FF6B00", textColor: "#fff", initials: "CM", domain: "masonline.com.ar" },
  changomas:    { color: "#FF6B00", textColor: "#fff", initials: "CM", domain: "masonline.com.ar" },
}

function getSupermarketMeta(name: string | null | undefined): SupermarketMeta {
  if (!name) return { color: "#64748b", textColor: "#fff", initials: "??", domain: "" }
  const key = name.toLowerCase().trim()
  if (SUPERMARKET_META[key]) return SUPERMARKET_META[key]
  const found = Object.entries(SUPERMARKET_META).find(([k]) => key.includes(k) || k.includes(key))
  if (found) return found[1]
  const initials = name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()
  return { color: "#64748b", textColor: "#fff", initials, domain: "" }
}

interface Props {
  name: string | null | undefined
  showLabel?: boolean
}

export function SupermarketLogo({ name, showLabel = true }: Props) {
  const [imgFailed, setImgFailed] = useState(false)
  const meta = getSupermarketMeta(name)
  const faviconUrl = meta.domain
    ? `https://www.google.com/s2/favicons?domain=${meta.domain}&sz=32`
    : null

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
          <span className="text-[8px] font-bold leading-none" style={{ color: meta.textColor }}>
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