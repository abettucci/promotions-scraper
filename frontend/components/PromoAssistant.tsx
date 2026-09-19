"use client"

import { FormEvent, useState } from "react"
import Link from "next/link"
import { ArrowUp, Bot, ShieldCheck, Sparkles } from "lucide-react"
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
    <section className="relative overflow-hidden rounded-[1.5rem] border border-[#d8e5c5] bg-[#f6faef] p-4 shadow-[0_18px_42px_rgb(48_83_27_/_0.08)] sm:p-6" aria-labelledby="assistant-title">
      <div className="pointer-events-none absolute -right-16 -top-20 h-52 w-52 rounded-full bg-[#b8f36b]/35 blur-3xl" />
      <div className="relative grid gap-5 lg:grid-cols-[.72fr_1.28fr] lg:items-start">
        <div className="lg:pr-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#cfe7a9] bg-white/80 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.13em] text-[#31571d]">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Asistente de promos
          </div>
          <h2 id="assistant-title" className="display mt-3 max-w-sm text-2xl font-semibold tracking-[-0.055em] text-[#173b20] sm:text-3xl">Preguntá antes de pagar.</h2>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-[#49624a]">Te ayuda a comparar promos vigentes y a revisar exclusiones publicadas. No inventa condiciones ni procesa pagos.</p>
          <div className="mt-5 flex items-center gap-2 text-xs text-[#567050]">
            <ShieldCheck className="h-4 w-4 text-[#39722c]" aria-hidden="true" /> Solo consulta datos de promociones vigentes
          </div>
        </div>

        <div className="rounded-2xl border border-[#d7e6cb] bg-white/95 p-3 sm:p-4">
            <div className="mb-3 flex items-center justify-between gap-3 px-1">
              <p className="text-xs font-semibold text-[#365739]"><Bot className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" /> Consultas de supermercados y combustibles</p>
              <p className="text-[11px] text-[#6d806c]">{token ? "Mensajes no guardados" : "5 consultas por hora"}</p>
            </div>
            {messages.length > 0 && <div className="mb-3 max-h-64 space-y-2 overflow-y-auto pr-1" aria-live="polite">
              {messages.map((message, index) => <div key={`${message.role}-${index}`} className={`rounded-xl px-3 py-2 text-sm leading-relaxed ${message.role === "user" ? "ml-8 bg-[#173b20] text-white" : "mr-5 border border-[#e1ead9] bg-[#f8fbf5] text-[#29452d]"}`}>
                {message.text}
              </div>)}
              {loading && <div className="mr-5 rounded-xl border border-[#e1ead9] bg-[#f8fbf5] px-3 py-2 text-sm text-[#58705b]">Buscando en promociones vigentes…</div>}
            </div>}
            {error && <p role="alert" className="mb-3 rounded-lg bg-[#fff2ef] px-3 py-2 text-xs text-[#993f31]">{error}</p>}
            <form onSubmit={(event) => submit(event)} className="flex gap-2">
              <label className="sr-only" htmlFor="promo-question">Tu pregunta sobre promociones</label>
              <textarea id="promo-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={280} rows={2} placeholder="Ej. ¿El vino Alaris está excluido en Coto hoy?" className="min-h-12 flex-1 resize-none rounded-xl border border-[#d4e1ca] bg-[#fcfef9] px-3 py-2.5 text-sm text-[#173b20] outline-none placeholder:text-[#829080] focus:border-[#4f8e42] focus:ring-2 focus:ring-[#b8f36b]/70" />
              <button type="submit" disabled={!question.trim() || loading} className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-[#173b20] text-white transition-colors hover:bg-[#285a30] disabled:cursor-not-allowed disabled:opacity-45" aria-label="Enviar pregunta">
                <ArrowUp className="h-5 w-5" aria-hidden="true" />
              </button>
            </form>
            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLES.map((example) => <button key={example} type="button" disabled={loading} onClick={() => submit(undefined, example)} className="rounded-full border border-[#dbe7d2] bg-[#f8fbf5] px-2.5 py-1.5 text-left text-[11px] font-medium text-[#416345] transition-colors hover:border-[#9dcc78] hover:bg-[#eff9e6] disabled:opacity-50">{example}</button>)}
            </div>
            {!token && <p className="mt-3 px-1 text-[11px] leading-relaxed text-[#6d806c]">Modo público: compara promociones generales, sin tus medios de pago. <Link href="/login" className="font-semibold text-[#31571d] underline underline-offset-2 hover:text-[#173b20]">Iniciá sesión</Link> para una recomendación personalizada.</p>}
          </div>
        </div>
    </section>
  )
}
