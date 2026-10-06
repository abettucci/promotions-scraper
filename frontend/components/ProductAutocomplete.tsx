"use client"

import { useEffect, useId, useRef, useState } from "react"
import Image from "next/image"
import { Loader2, Package, Search, Tag } from "lucide-react"
import { api } from "@/lib/api"
import type { PriceSuggestResponse, PriceSuggestion } from "@/lib/types"

const fold = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()

/** Pone en negrita las palabras que empiezan con lo escrito ("heladera sam" → Heladera Samsung). */
function Highlight({ text, query }: { text: string; query: string }) {
  const tokens = fold(query).split(/\s+/).filter(Boolean)
  return (
    <>
      {text.split(/(\s+)/).map((word, index) => {
        const hit = !/^\s+$/.test(word) && tokens.some((token) => fold(word).startsWith(token))
        return hit ? <b key={index} className="font-bold text-[#102a4c]">{word}</b> : <span key={index}>{word}</span>
      })}
    </>
  )
}

/** Miniatura; si la tienda no la sirve se muestra un ícono en lugar de una imagen rota. */
function Thumb({ src }: { src: string }) {
  const [failed, setFailed] = useState(false)
  return (
    <span className="relative grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-lg border border-[#e5ebf2] bg-white">
      {src && !failed
        ? <Image src={src} alt="" fill sizes="44px" className="object-contain p-0.5" unoptimized onError={() => setFailed(true)} />
        : <Package className="h-5 w-5 text-[#b6c3d3]" aria-hidden="true" />}
    </span>
  )
}

export interface AutocompleteSelection {
  text: string
  /** Si eligió una categoría: se busca lo escrito y se filtra por ella. */
  categoryPath?: string[]
}

interface Props {
  value: string
  onChange: (value: string) => void
  onSelect: (selection: AutocompleteSelection) => void
}

export function ProductAutocomplete({ value, onChange, onSelect }: Props) {
  const listId = useId()
  const wrapperRef = useRef<HTMLDivElement>(null)
  // Último texto que escribió la persona: las sugerencias sólo se piden si el
  // valor actual salió de tipear (no de elegir un ejemplo o una sugerencia).
  const typedRef = useRef<string | null>(null)
  const [open, setOpen] = useState(false)
  const [loadingLive, setLoadingLive] = useState(false)
  const [data, setData] = useState<PriceSuggestResponse | null>(null)
  const [active, setActive] = useState(-1)

  // Primero el índice local (instantáneo) y después la consulta en vivo a las tiendas.
  useEffect(() => {
    if (typedRef.current !== value || value.trim().length < 2) {
      setData(null)
      return
    }
    const controller = new AbortController()
    // Si la persona ya envió el formulario o eligió algo (typedRef = null), las
    // respuestas que venían en camino no deben reabrir el menú.
    const stale = () => controller.signal.aborted || typedRef.current !== value
    const timer = setTimeout(async () => {
      try {
        if (stale()) return
        const fast = await api.suggestPrices(value.trim(), false, controller.signal)
        if (stale()) return
        setData(fast)
        setOpen(true)
        setLoadingLive(true)
        const live = await api.suggestPrices(value.trim(), true, controller.signal)
        if (stale()) return
        setData(live)
      } catch {
        /* cancelado o sin respuesta: se mantiene lo que ya se mostró */
      } finally {
        if (!controller.signal.aborted) setLoadingLive(false)
      }
    }, 200)
    return () => {
      clearTimeout(timer)
      controller.abort()
      setLoadingLive(false)
    }
  }, [value])

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", close)
    return () => document.removeEventListener("mousedown", close)
  }, [])

  const categories = data?.categories ?? []
  const suggestions = data?.suggestions ?? []
  const options: ({ kind: "category"; label: string; path: string[] } | { kind: "product"; item: PriceSuggestion })[] = [
    ...categories.map((c) => ({ kind: "category" as const, label: c.name, path: c.path })),
    ...suggestions.map((item) => ({ kind: "product" as const, item })),
  ]
  const showList = open && (options.length > 0 || loadingLive)

  const choose = (index: number) => {
    const option = options[index]
    if (!option) return
    setOpen(false)
    typedRef.current = null
    if (option.kind === "category") onSelect({ text: value.trim(), categoryPath: option.path })
    else {
      onChange(option.item.name)
      onSelect({ text: option.item.name })
    }
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && active < 0) { typedRef.current = null; setOpen(false); setLoadingLive(false); return }  // envía el formulario
    if (!showList) return
    if (event.key === "ArrowDown") { event.preventDefault(); setActive((i) => (i + 1) % options.length) }
    else if (event.key === "ArrowUp") { event.preventDefault(); setActive((i) => (i <= 0 ? options.length - 1 : i - 1)) }
    else if (event.key === "Escape") setOpen(false)
    else if (event.key === "Enter" && active >= 0) { event.preventDefault(); choose(active) }
  }

  return (
    <div ref={wrapperRef} className="relative flex-1">
      <label htmlFor="price-query" className="sr-only">Producto</label>
      <input
        id="price-query" value={value} maxLength={120} autoComplete="off"
        onChange={(event) => { typedRef.current = event.target.value; onChange(event.target.value); setActive(-1) }}
        onFocus={() => data && setOpen(true)} onKeyDown={onKeyDown}
        role="combobox" aria-expanded={showList} aria-controls={listId} aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        placeholder="Ej.: leche La Serenísima 1 L"
        className="h-12 w-full rounded-xl border border-white/20 bg-white px-4 text-base text-[#102a4c] placeholder:text-[#8a9ab0] focus:outline-none focus:ring-2 focus:ring-[#b8f36b]"
      />
      {showList && (
        <ul id={listId} role="listbox" aria-label="Sugerencias de productos"
          className="absolute left-0 right-0 top-[calc(100%+6px)] z-40 max-h-[26rem] overflow-y-auto rounded-xl border border-[#dbe4ee] bg-white py-1 text-left shadow-[0_18px_40px_rgb(16_42_76_/_0.18)]">
          {options.map((option, index) => (
            <li key={option.kind === "category" ? `c-${option.label}` : option.item.key} id={`${listId}-${index}`} role="option" aria-selected={active === index}
              onMouseDown={(event) => { event.preventDefault(); choose(index) }} onMouseEnter={() => setActive(index)}
              className={`flex cursor-pointer items-center gap-3 px-3 py-2 ${active === index ? "bg-[#f1f6fd]" : ""}`}>
              {option.kind === "category" ? (
                <>
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-[#eef3ff] text-[#2758d8]"><Tag className="h-5 w-5" aria-hidden="true" /></span>
                  <span className="min-w-0 text-sm text-[#52657d]">Ver todo en <b className="text-[#102a4c]">{option.label}</b></span>
                </>
              ) : (
                <>
                  <Thumb src={option.item.image} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-[#52657d]"><Highlight text={option.item.name} query={value} /></span>
                    <span className="block truncate text-xs text-[#8a9ab0]">
                      {[option.item.brand, option.item.category_path.slice(-2).join(" › ")].filter(Boolean).join(" · ")}
                      {option.item.stores > 0 && ` · ${option.item.stores} ${option.item.stores === 1 ? "tienda" : "tiendas"}`}
                    </span>
                  </span>
                </>
              )}
            </li>
          ))}
          {loadingLive && (
            <li role="presentation" className="flex items-center gap-2 px-3 py-2 text-xs text-[#8a9ab0]">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> Buscando en las tiendas…
            </li>
          )}
        </ul>
      )}
      <Search className="pointer-events-none absolute right-3 top-1/2 hidden h-4 w-4 -translate-y-1/2 text-[#b6c3d3] sm:block" aria-hidden="true" />
    </div>
  )
}
