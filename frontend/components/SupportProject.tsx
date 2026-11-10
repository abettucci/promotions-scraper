import { Coffee, ExternalLink } from "lucide-react"

function getCafecitoUrl(): string | null {
  const value = process.env.NEXT_PUBLIC_CAFECITO_URL
  if (!value) return null
  try {
    const url = new URL(value)
    if (url.protocol !== "https:" || url.hostname !== "cafecito.app" || url.pathname.split("/").filter(Boolean).length !== 1) return null
    return url.toString()
  } catch {
    return null
  }
}

export function SupportProject() {
  const url = getCafecitoUrl()
  if (!url) return null
  return <section className="rounded-2xl border border-border bg-card px-6 py-8 text-center text-card-foreground sm:px-10 sm:py-10">
    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">PromoAR es un proyecto independiente</p>
    <h2 className="display mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">¿Te sirve para ahorrar?</h2>
    <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">Podés ayudar a sostener el relevamiento de precios y seguir sumando comercios.</p>
    <a href={url} target="_blank" rel="noopener noreferrer" className="mx-auto mt-6 inline-flex min-h-12 items-center gap-2 rounded-full bg-[#102a4c] px-6 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#1d4169]">
      <Coffee className="h-4 w-4 text-[#b8f36b]" /> Invitame un cafecito <ExternalLink className="h-4 w-4" />
    </a>
  </section>
}
