import type { Promotion } from "@/lib/types"

type ChannelPromotion = Pick<Promotion, "store_types">
type MethodPromotion = Pick<Promotion, "payment_method" | "card_type" | "title" | "wallet">

/**
 * Canal donde vale la promo. Antes la tabla marcaba "Solo online" con sólo
 * encontrar "online" en store_types, aunque también dijera "Tiendas".
 */
export function channelLabel(promo: ChannelPromotion): string | null {
  const stores = (promo.store_types || "").toLocaleLowerCase("es-AR")
  if (!stores) return null
  const online = /online|\.com|web|app/.test(stores)
  const physical = /tienda|sucursal|presencial|local|hiper|market|express|maxi|masgo/.test(stores)
  if (online && physical) return "Online y tiendas"
  if (online) return "Solo online"
  if (physical) return "Solo tiendas"
  return null
}

const METHOD_RULES: [RegExp, string][] = [
  [/todos los medios|cualquier (?:medio|tarjeta)|cualquier qr/i, "Cualquier medio"],
  [/\bqr\b/i, "QR"],
  [/\bnfc\b|sin contacto|contactless|apple pay|google pay/i, "NFC"],
  [/dinero en cuenta|saldo en cuenta|cuenta digital/i, "Dinero en cuenta"],
  [/tarjeta|cr[eé]dito|d[eé]bito|visa|mastercard|american express|amex|cabal|naranja/i, "Tarjeta"],
]

/** Formas de pago que exige la promo (QR, NFC, tarjeta, dinero en cuenta...). */
export function paymentMethods(promo: MethodPromotion): string[] {
  const source = [promo.payment_method, promo.card_type].filter(Boolean).join(" ")
  const found = METHOD_RULES.filter(([pattern]) => pattern.test(source)).map(([, label]) => label)
  // "Cualquier medio" ya cubre al resto; no lo mezclamos con métodos puntuales.
  if (found.includes("Cualquier medio")) return ["Cualquier medio"]
  // "QR MODO con Visa" o "NFC con Visa crédito": la tarjeta es el respaldo,
  // el método que hay que usar en la caja es el QR / NFC.
  if (found.includes("QR") || found.includes("NFC")) return found.filter((label) => label !== "Tarjeta")
  if (found.length > 0) return found
  // Billeteras sin medio informado se pagan desde su app (QR o saldo).
  if (promo.wallet && !promo.card_type) return ["App " + promo.wallet]
  return []
}

type EntityPromotion = Pick<Promotion, "bank" | "wallet" | "title" | "payment_method">

/**
 * Entidad a mostrar. Promos de programas propios o "todas las tarjetas"
 * (Comunidad Coto, Tarjetas de crédito) no tienen banco ni billetera: se
 * toma el inicio del título, que las fuentes arman como "<Entidad> <beneficio>".
 */
export function entityLabel(promo: EntityPromotion): string {
  if (promo.bank || promo.wallet) return (promo.bank || promo.wallet) as string
  const fromTitle = (promo.title || "").split(/\s+(?=(?:hasta\s+)?\d|\$)/i)[0]?.trim()
  return fromTitle || promo.payment_method || "Todos los medios de pago"
}
