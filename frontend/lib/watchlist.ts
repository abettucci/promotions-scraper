import type { PriceAlert } from "./types"

export const money = (value: number) => "$" + value.toLocaleString("es-AR", { maximumFractionDigits: 2 })

export function groupWatchlistProducts(products: PriceAlert[]) {
  const groups = new Map<string, PriceAlert[]>()
  for (const product of products) {
    const category = product.category_path?.[0] || product.category?.split("/").map((s) => s.trim()).find(Boolean) || "Otros"
    groups.set(category, [...(groups.get(category) || []), product])
  }
  return [...groups].sort(([a], [b]) => a === "Otros" ? 1 : b === "Otros" ? -1 : a.localeCompare(b, "es"))
    .map(([category, items]) => ({ category, products: items }))
}

export function bestQuote(product: PriceAlert) {
  const quote = product.best_offer
  return quote && Number.isFinite(quote.price) && quote.price > 0 ? quote : null
}

export function quoteDate(value: string) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.split("-").reverse().join("/")
  const date = new Date(value)
  return Number.isFinite(date.getTime()) ? date.toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "fecha no disponible"
}
