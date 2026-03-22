export interface SupermarketMeta {
  color: string
  textColor: string
  initials: string
  domain: string
}

const SUPERMARKET_META: Record<string, SupermarketMeta> = {
  carrefour: {
    color: "#004F9F",
    textColor: "#fff",
    initials: "CF",
    domain: "carrefour.com.ar",
  },
  día: {
    color: "#E31937",
    textColor: "#fff",
    initials: "DÍ",
    domain: "supermercadosdia.com.ar",
  },
  dia: {
    color: "#E31937",
    textColor: "#fff",
    initials: "DÍ",
    domain: "supermercadosdia.com.ar",
  },
  coto: {
    color: "#F5A623",
    textColor: "#000",
    initials: "CO",
    domain: "cotodigital.com.ar",
  },
  jumbo: {
    color: "#00A651",
    textColor: "#fff",
    initials: "JU",
    domain: "jumbo.com.ar",
  },
  cencosud: {
    color: "#00A651",
    textColor: "#fff",
    initials: "JU",
    domain: "jumbo.com.ar",
  },
  masonline: {
    color: "#FF6B00",
    textColor: "#fff",
    initials: "MO",
    domain: "masonline.com.ar",
  },
  changomás: {
    color: "#FF6B00",
    textColor: "#fff",
    initials: "CM",
    domain: "masonline.com.ar",
  },
  changomas: {
    color: "#FF6B00",
    textColor: "#fff",
    initials: "CM",
    domain: "masonline.com.ar",
  },
}

export function getSupermarketMeta(name: string | null | undefined): SupermarketMeta {
  if (!name) return { color: "#64748b", textColor: "#fff", initials: "??", domain: "" }
  const key = name.toLowerCase().trim()
  if (SUPERMARKET_META[key]) return SUPERMARKET_META[key]
  const found = Object.entries(SUPERMARKET_META).find(([k]) => key.includes(k) || k.includes(key))
  if (found) return found[1]
  const initials = name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()
  return { color: "#64748b", textColor: "#fff", initials, domain: "" }
}

export function getFaviconUrl(domain: string): string | null {
  if (!domain) return null
  return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`
}
