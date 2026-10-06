"use client"

import { Fragment } from "react"

// "**negrita**" y URLs sueltas. El texto llega como texto plano de la API: se
// arma con elementos de React (nunca con HTML), así que no hay inyección posible.
const INLINE = /(\*\*[^*]+\*\*|https?:\/\/[^\s]+)/g
const LINK_LINE = /^(.*?):\s*(https?:\/\/\S+)$/

function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(INLINE).map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) return <strong key={index} className="font-semibold text-[#17361b]">{part.slice(2, -2)}</strong>
        if (/^https?:\/\//.test(part)) return <a key={index} href={part} target="_blank" rel="noopener noreferrer" className="break-all font-semibold text-[#2758d8] underline">{part}</a>
        return <Fragment key={index}>{part}</Fragment>
      })}
    </>
  )
}

export function AssistantMessage({ text }: { text: string }) {
  const lines = text.split("\n")
  return (
    <div className="space-y-1.5">
      {lines.map((line, index) => {
        if (!line.trim()) return <div key={index} className="h-1" />
        const link = line.match(LINK_LINE)
        if (link) {
          return <p key={index}><a href={link[2]} target="_blank" rel="noopener noreferrer" className="font-semibold text-[#2758d8] underline">{link[1]} ↗</a></p>
        }
        if (line.startsWith("• ")) {
          return (
            <p key={index} className="flex gap-2 rounded-lg bg-[#f4f8f1] px-2.5 py-1.5">
              <span aria-hidden="true" className="text-[#5a8a3a]">•</span>
              <span className="min-w-0 break-words"><Inline text={line.slice(2)} /></span>
            </p>
          )
        }
        const note = /^(Ordenado|Mostrando|Comparo|Precios online|Tip:)/.test(line)
        return <p key={index} className={note ? "text-xs italic text-[#6d806f]" : undefined}><Inline text={line} /></p>
      })}
    </div>
  )
}
