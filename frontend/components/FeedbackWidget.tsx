"use client"

import { useState } from "react"
import { MessageSquare, X } from "lucide-react"
import { api } from "@/lib/api"

type Rating = "love" | "like" | "neutral" | "improve"

const OPTIONS: { value: Rating; label: string; emoji: string }[] = [
  { value: "love", label: "Me encanta", emoji: "😍" },
  { value: "like", label: "Me gusta", emoji: "😊" },
  { value: "neutral", label: "Regular", emoji: "😐" },
  { value: "improve", label: "Puede mejorar", emoji: "😕" },
]

export function FeedbackWidget() {
  const [open, setOpen] = useState(false)
  const [rating, setRating] = useState<Rating | null>(null)
  const [comment, setComment] = useState("")
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle")

  async function submit() {
    if (!rating) return
    setStatus("sending")
    try {
      await api.sendFeedback({ rating, comment: comment.trim(), page: window.location.pathname })
      setStatus("sent")
      setComment("")
      setRating(null)
    } catch {
      setStatus("error")
    }
  }

  function close() {
    setOpen(false)
    setStatus("idle")
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-3 sm:bottom-6 sm:right-6">
      {open && (
        <section
          role="dialog"
          aria-label="Ayudanos a mejorar"
          className="w-[min(20rem,calc(100vw-2.5rem))] rounded-2xl border border-[#cbd8e6] bg-white p-5 text-[#102a4c] shadow-[0_12px_28px_rgb(16_42_76_/_0.16)] dark:border-[#2a3f5c] dark:bg-[#0f1f36] dark:text-[#e8eef6]"
        >
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-base font-semibold">¿Cómo calificarías tu experiencia?</h2>
            <button type="button" onClick={close} aria-label="Cerrar" className="rounded-lg p-1 hover:bg-black/5">
              <X className="h-4 w-4" />
            </button>
          </div>

          {status === "sent" ? (
            <p className="mt-4 text-sm">¡Gracias! Lo leemos para mejorar PromoAR.</p>
          ) : (
            <>
              <div className="mt-4 grid grid-cols-2 gap-2">
                {OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setRating(option.value)}
                    aria-pressed={rating === option.value}
                    className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-sm transition-colors ${
                      rating === option.value ? "border-[#102a4c] bg-[#efffdc] text-[#102a4c]" : "border-[#cbd8e6] hover:border-[#102a4c]"
                    }`}
                  >
                    <span aria-hidden>{option.emoji}</span> {option.label}
                  </button>
                ))}
              </div>

              <label className="mt-4 block text-sm font-medium" htmlFor="feedback-comment">
                ¿Querés contarnos algo más? <span className="font-normal text-[#52657d]">(opcional)</span>
              </label>
              <textarea
                id="feedback-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value.slice(0, 500))}
                rows={3}
                className="mt-2 w-full rounded-xl border border-[#cbd8e6] bg-white px-3 py-2 text-sm text-[#102a4c] outline-none focus:border-[#102a4c] dark:bg-[#0b1829] dark:text-[#e8eef6]"
              />

              {status === "error" && <p className="mt-2 text-xs text-[#8f2d28]">No pudimos enviar tu feedback. Probá de nuevo.</p>}

              <button
                type="button"
                onClick={submit}
                disabled={!rating || status === "sending"}
                className="mt-4 w-full rounded-full bg-[#102a4c] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1d4169] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {status === "sending" ? "Enviando…" : "Enviar"}
              </button>
            </>
          )}
        </section>
      )}

      <button
        type="button"
        onClick={() => (open ? close() : setOpen(true))}
        aria-expanded={open}
        className="inline-flex min-h-11 items-center gap-2 rounded-2xl border border-[#cbd8e6] bg-white px-4 text-sm font-semibold text-[#102a4c] shadow-[0_12px_28px_rgb(16_42_76_/_0.16)] transition-all hover:-translate-y-0.5 hover:border-[#102a4c] focus-visible:outline-none"
      >
        <MessageSquare className="h-4 w-4" /> Ayudanos a mejorar
      </button>
    </div>
  )
}
