export function argentinaDay(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Argentina/Buenos_Aires", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now)
  return ["year", "month", "day"].map((type) => parts.find((part) => part.type === type)?.value).join("-")
}

export function purchaseStatus(status: string, hasPromo: boolean) {
  return status !== "observed" ? "Sin histórico verificable" : hasPromo ? "Día con promo publicada" : "Sin porcentaje registrado ese día"
}

export function share(value: number | null): string {
  return value === null ? "Sin datos" : `${value.toLocaleString("es-AR", { maximumFractionDigits: 2 })}%`
}
