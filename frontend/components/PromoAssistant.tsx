"use client"

import { FormEvent, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowUp, BotMessageSquare, ShieldCheck, Sparkles, X } from "lucide-react"
import { api } from "@/lib/api"

type Message = { role: "user" | "assistant"; text: string }

const EXAMPLES = [
  "¿El vino Alaris está excluido en Coto hoy?",
  "¿En qué súper me conviene comprar vino hoy?",
  "¿Qué promos de combustible hay con Galicia?",
]

export function PromoAssistant({ token }: { token: string | null }) {
  const [question, setQuestion] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setIsOpen(false)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  async function submit(event?: FormEvent, suggested?: string) {
    event?.preventDefault()
    const nextQuestion = (suggested ?? question).trim()
    if (!nextQuestion || loading) return

    setLoading(true)
    setError("")
    setMessages((current) => [...current.slice(-5), { role: "user", text: nextQuestion }])
    setQuestion("")
    try {
      const result = token
        ? await api.askAssistant(token, nextQuestion)
        : await api.askPublicAssistant(nextQuestion)
      setMessages((current) => [...current, { role: "assistant", text: result.answer }])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "No se pudo consultar el asistente.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <aside className="fixed bottom-5 right-4 z-50 flex items-end gap-3 sm:bottom-7 sm:right-7" aria-label="Asistente de promociones">
      {!isOpen && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="assistant-greeting relative hidden max-w-[14.5rem] rounded-[1.35rem] border border-[#b9c8d7] bg-[#10233d] px-4 py-3 text-left text-sm font-medium leading-snug text-white shadow-[0_18px_40px_rgb(8_24_44_/_0.24)] transition-transform hover:-translate-y-0.5 sm:block"
          aria-label="Abrir el asistente de promociones"
        >
          <span className="block text-[#b8f36b]">Hola, soy PromoAR ✦</span>
          <span className="mt-0.5 block text-[#edf4fb]">¿Querés revisar una promo?</span>
        </button>
      )}

      {isOpen && (
        <section className="assistant-panel absolute bottom-0 right-0 flex w-[calc(100vw-2rem)] max-w-[27rem] flex-col overflow-hidden rounded-[1.6rem] border border-[#bdcddd] bg-[#f9fbfd] shadow-[0_26px_75px_rgb(8_24_44_/_0.28)] sm:w-[26rem]" aria-labelledby="assistant-title">
          <header className="relative overflow-hidden bg-[#102a4c] px-5 pb-4 pt-5 text-white">
            <div className="pointer-events-none absolute -right-10 -top-12 h-36 w-36 rounded-full bg-[#b8f36b]/20 blur-2xl" />
            <div className="relative flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-2xl bg-[#b8f36b] text-[#102a4c] shadow-[0_8px_18px_rgb(184_243_107_/_0.22)]">
                  <Sparkles className="h-5 w-5" aria-hidden="true" />
                </span>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#b8f36b]">Asistente de promos</p>
                  <h2 id="assistant-title" className="mt-0.5 text-base font-semibold tracking-[-0.03em]">Comprá con la información a la vista.</h2>
                </div>
              </div>
              <button type="button" onClick={() => setIsOpen(false)} className="grid h-9 w-9 place-items-center rounded-xl text-[#d7e3f0] transition-colors hover:bg-white/10 hover:text-white" aria-label="Cerrar asistente">
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </header>

          <div className="max-h-[min(31rem,calc(100vh-10rem))] overflow-y-auto p-4">
            <div className="mb-4 flex items-center gap-2 rounded-xl border border-[#dbe7d2] bg-[#f3faeb] px-3 py-2 text-xs text-[#38583d]">
              <ShieldCheck className="h-4 w-4 shrink-0 text-[#39722c]" aria-hidden="true" />
              {token ? "Respuesta basada en promos vigentes y tus medios vinculados." : "Modo público: 5 consultas por hora, sin medios de pago personales."}
            </div>

            {messages.length === 0 ? (
              <div className="pb-1">
                <p className="text-sm leading-relaxed text-[#50657a]">Preguntá por exclusiones, condiciones o dónde conviene comprar. Te respondo solo con la información scrapeada.</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {EXAMPLES.map((example) => (
                    <button key={example} type="button" onClick={() => submit(undefined, example)} className="rounded-full border border-[#d7e3ef] bg-white px-3 py-2 text-left text-[11px] font-semibold leading-snug text-[#244565] transition-colors hover:border-[#8ab45f] hover:bg-[#f3faeb]">
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-2.5" aria-live="polite">
                {messages.map((message, index) => (
                  <div key={`${message.role}-${index}`} className={`rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${message.role === "user" ? "ml-10 bg-[#102a4c] text-white" : "mr-5 border border-[#e0e8df] bg-white text-[#29452d]"}`}>
                    {message.text}
                  </div>
                ))}
                {loading && <div className="mr-5 rounded-2xl border border-[#e0e8df] bg-white px-3.5 py-2.5 text-sm text-[#58705b]">Revisando promociones vigentes…</div>}
              </div>
            )}

            {error && <p role="alert" className="mt-3 rounded-xl bg-[#fff1ef] px-3 py-2 text-xs leading-relaxed text-[#993f31]">{error}</p>}
          </div>

          <form onSubmit={(event) => submit(event)} className="border-t border-[#dbe4ee] bg-white p-3">
            <div className="flex gap-2">
              <label className="sr-only" htmlFor="promo-question">Tu pregunta sobre promociones</label>
              <textarea id="promo-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={280} rows={2} placeholder="Ej. ¿Los yogures están excluidos en Coto?" className="min-h-12 flex-1 resize-none rounded-xl border border-[#cddbe8] bg-[#fbfdff] px-3 py-2.5 text-sm text-[#173b20] outline-none placeholder:text-[#829080] focus:border-[#4f8e42] focus:ring-2 focus:ring-[#b8f36b]/70" />
              <button type="submit" disabled={!question.trim() || loading} className="grid h-12 w-12 shrink-0 place-items-center self-end rounded-xl bg-[#b8f36b] text-[#102a4c] transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-45" aria-label="Enviar pregunta">
                <ArrowUp className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            {!token && <p className="mt-2 px-1 text-[11px] leading-relaxed text-[#718294]">¿Querés recomendaciones según tus tarjetas? <Link href="/login" className="font-bold text-[#2758d8] underline underline-offset-2">Iniciá sesión</Link>.</p>}
          </form>
        </section>
      )}

      {!isOpen && <button type="button" onClick={() => setIsOpen(true)} className="assistant-launcher group relative grid h-16 w-16 shrink-0 place-items-center rounded-[1.45rem] bg-[#b8f36b] text-[#102a4c] shadow-[0_18px_36px_rgb(63_116_40_/_0.28)] transition-transform hover:-translate-y-1" aria-label="Abrir asistente" aria-expanded={false}>
        <span className="assistant-radar" /><span className="assistant-radar assistant-radar-delayed" />
        <BotMessageSquare className="relative h-7 w-7 transition-transform group-hover:scale-110" aria-hidden="true" />
      </button>}
    </aside>
  )
}
