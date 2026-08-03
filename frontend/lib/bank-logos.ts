// Maps bank/wallet names to their brand colors and initials
// When official logos are available they can be added as image URLs

export interface BankMeta {
  color: string       // Background color for avatar
  textColor: string   // Text color for avatar initials
  initials: string
  label: string       // Display name
  type: "bank" | "wallet" | "fintech" | "card"
  logoUrl?: string    // Optional path to official logo image (in /public/logos/)
}

const BANK_META: Record<string, BankMeta> = {
  galicia: { color: "#E31837", textColor: "#fff", initials: "GA", label: "Galicia", type: "bank" },
  santander: { color: "#CC0000", textColor: "#fff", initials: "SA", label: "Santander", type: "bank" },
  bbva: { color: "#004481", textColor: "#fff", initials: "BB", label: "BBVA", type: "bank" },
  macro: { color: "#FFB81C", textColor: "#000", initials: "MA", label: "Macro", type: "bank" },
  icbc: { color: "#C8102E", textColor: "#fff", initials: "IC", label: "ICBC", type: "bank" },
  hsbc: { color: "#DB0011", textColor: "#fff", initials: "HS", label: "HSBC", type: "bank" },
  ciudad: { color: "#003DA5", textColor: "#fff", initials: "CI", label: "Ciudad", type: "bank" },
  nacion: { color: "#0033A0", textColor: "#fff", initials: "BN", label: "Nación", type: "bank" },
  patagonia: { color: "#00843D", textColor: "#fff", initials: "PA", label: "Patagonia", type: "bank" },
  credicoop: { color: "#F5A623", textColor: "#000", initials: "CC", label: "Credicoop", type: "bank" },
  supervielle: { color: "#FF6B00", textColor: "#fff", initials: "SU", label: "Supervielle", type: "bank" },
  frances: { color: "#004481", textColor: "#fff", initials: "FR", label: "Francés", type: "bank" },
  itau: { color: "#EC7000", textColor: "#fff", initials: "IT", label: "Itaú", type: "bank" },
  comafi: { color: "#0047AB", textColor: "#fff", initials: "CO", label: "Comafi", type: "bank" },
  piano: { color: "#2C3E50", textColor: "#fff", initials: "PI", label: "Piano", type: "bank" },
  bind: { color: "#3498DB", textColor: "#fff", initials: "BI", label: "BIND", type: "bank" },
  // Wallets / Fintechs
  "mercado pago": { color: "#009EE3", textColor: "#fff", initials: "MP", label: "Mercado Pago", type: "wallet", logoUrl: "/logos/mercadopago.png" },
  mercadopago: { color: "#009EE3", textColor: "#fff", initials: "MP", label: "Mercado Pago", type: "wallet", logoUrl: "/logos/mercadopago.png" },
  "uala": { color: "#9B51E0", textColor: "#fff", initials: "UA", label: "Ualá", type: "wallet" },
  "naranja x": { color: "#FF4713", textColor: "#fff", initials: "NX", label: "Naranja X", type: "fintech" },
  naranjax: { color: "#FF4713", textColor: "#fff", initials: "NX", label: "Naranja X", type: "fintech" },
  modo: { color: "#3700B3", textColor: "#fff", initials: "MO", label: "MODO", type: "wallet", logoUrl: "/logos/modo.png" },
  "personal pay": { color: "#00BCD4", textColor: "#fff", initials: "PP", label: "Personal Pay", type: "wallet" },
  "cuenta dni": { color: "#1565C0", textColor: "#fff", initials: "DN", label: "Cuenta DNI", type: "wallet" },
  "claro pay": { color: "#E60000", textColor: "#fff", initials: "CP", label: "Claro Pay", type: "wallet" },
}

export function getBankMeta(name: string | null | undefined): BankMeta {
  if (!name) return { color: "#64748b", textColor: "#fff", initials: "??", label: name ?? "Desconocido", type: "bank" }
  const key = name.toLowerCase().trim()
  // Exact match
  if (BANK_META[key]) return { ...BANK_META[key], label: name }
  // Partial match
  const found = Object.entries(BANK_META).find(([k]) => key.includes(k) || k.includes(key))
  if (found) return { ...found[1], label: name }
  // Default: generate initials from name
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()
  return { color: "#64748b", textColor: "#fff", initials, label: name, type: "bank" }
}
