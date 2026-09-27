import type { Promotion } from "@/lib/types"

type BenefitPromotion = Pick<Promotion, "discount" | "title" | "requirements">

/**
 * Devuelve un beneficio comparable incluso para filas históricas incompletas.
 * La fuente de Coto puede haber guardado las cuotas dentro de requisitos en
 * ejecuciones previas; no debemos convertirlas en el genérico "Beneficio".
 */
export function benefitLabel(promo: BenefitPromotion): string {
  const published = promo.discount?.replace(/\s+/g, " ").trim()
  if (published) return published

  const source = [promo.title, ...(Array.isArray(promo.requirements) ? promo.requirements : [])]
    .filter(Boolean)
    .join(" ")
  const cuotas = source.match(/(?:hasta\s+)?(\d{1,2})(?:\s*(?:-|a)\s*(\d{1,2}))?\s*cuotas?\s+sin\s+inter[eé]s/i)
  if (cuotas) return `${cuotas[1]}${cuotas[2] ? `-${cuotas[2]}` : ""} cuotas sin interés`

  const percentage = source.match(/(\d{1,3})\s*%\s*(?:de\s+)?(descuento|reintegro|cashback|devoluci[oó]n)/i)
  if (percentage) return `${percentage[1]}% ${percentage[2].toLocaleLowerCase("es-AR")}`

  return "Beneficio no informado"
}
