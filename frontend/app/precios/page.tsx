"use client"

import { useState } from "react"
import Link from "next/link"
import Image from "next/image"
import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, ExternalLink, Loader2, Search, ShoppingCart, Tv, Dumbbell } from "lucide-react"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"
import { BankBadge } from "@/components/BankBadge"
import type { PriceGroup, PriceOffer } from "@/lib/types"

const CATEGORIES = [
  { value: "", label: "Todo", icon: Search },
  { value: "supermarket", label: "Súper", icon: ShoppingCart },
  { value: "electro", label: "Electro y hogar", icon: Tv },
  { value: "supplements", label: "Suplementos", icon: Dumbbell },
]

const EXAMPLES = ["leche La Serenísima 1 L", "aceite Cocinero 1,5 L", "heladera Samsung no frost", "smart tv 50 Samsung"]

const ars = (value: number) => `$${Math.round(value).toLocaleString("es-AR")}`

function OfferRow({ offer, best }: { offer: PriceOffer; best: boolean }) {
  const final = offer.final_price ?? offer.price
  const promo = offer.promo
  return (
    <tr className={best ? "bg-[#f4ffec]" : "transition-colors hover:bg-[#f5f8fc]"}>
      <td className="px-4 py-3 align-top sm:px-5">
        <p className="text-sm font-semibold text-[#102a4c]">{offer.store_name}</p>
        {best && <span className="mt-1 inline-block rounded-full bg-[#b8f36b] px-2 py-0.5 text-[10px] font-bold text-[#102a4c]">MÁS BARATO HOY</span>}
      </td>
      <td className="px-3 py-3 align-top text-sm text-[#102a4c]">
        <p className="font-semibold">{ars(offer.price)}</p>
        {offer.percentage_off && offer.list_price && (
          <p className="text-xs text-[#8a9ab0]"><span className="line-through">{ars(offer.list_price)}</span> −{offer.percentage_off}%</p>
        )}
        {offer.installments > 0 && <p className="text-xs text-[#52657d]">{offer.installments} cuotas sin interés</p>}
      </td>
      <td className="px-3 py-3 align-top">
        {promo && offer.savings > 0 ? (
          <div className="space-y-1">
            <div className="flex items-center gap-2"><BankBadge name={promo.entity} size="sm" showLabel /></div>
            <p className="text-xs font-semibold text-[#3d6626]">{promo.discount}{promo.tope ? ` · tope ${promo.tope}` : ""}</p>
            {promo.requires_min_purchase && <p className="text-xs text-[#8f2d28]">Compra mínima {promo.min_purchase}</p>}
            {promo.store_types && promo.store_types.toLowerCase() !== "online, tiendas" && <p className="text-xs text-[#52657d]">{promo.store_types}</p>}
          </div>
        ) : <span className="text-xs text-[#8a9ab0]">Sin promo bancaria hoy</span>}
      </td>
      <td className="px-3 py-3 align-top">
        <p className="text-base font-bold text-[#102a4c]">{ars(final)}</p>
        {offer.savings > 0 && <p className="text-xs font-semibold text-[#3d6626]">Ahorrás {ars(offer.savings)}</p>}
      </td>
      <td className="px-4 py-3 align-top sm:px-5">
        <a href={offer.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 whitespace-nowrap text-xs font-bold text-[#2758d8] hover:text-[#102a4c]">
          Ver en la tienda <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </td>
    </tr>
  )
}

function OfferItem({ offer, best }: { offer: PriceOffer; best: boolean }) {
  const final = offer.final_price ?? offer.price
  const promo = offer.promo
  return (
    <li className={`px-4 py-3 ${best ? "bg-[#f4ffec]" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#102a4c]">{offer.store_name}</p>
          {best && <span className="mt-1 inline-block rounded-full bg-[#b8f36b] px-2 py-0.5 text-[10px] font-bold text-[#102a4c]">MÁS BARATO HOY</span>}
        </div>
        <div className="text-right">
          <p className="text-base font-bold text-[#102a4c]">{ars(final)}</p>
          {offer.savings > 0 && <p className="text-xs text-[#8a9ab0] line-through">{ars(offer.price)}</p>}
        </div>
      </div>
      {promo && offer.savings > 0 ? (
        <p className="mt-1 text-xs text-[#3d6626]">
          <b>{promo.discount}</b> con {promo.entity}{promo.tope ? ` · tope ${promo.tope}` : ""}
          {promo.requires_min_purchase && <span className="text-[#8f2d28]"> · mín. {promo.min_purchase}</span>}
        </p>
      ) : <p className="mt-1 text-xs text-[#8a9ab0]">Sin promo bancaria hoy{offer.installments > 0 ? ` · ${offer.installments} cuotas sin interés` : ""}</p>}
      <a href={offer.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs font-bold text-[#2758d8]">
        Ver en la tienda <ExternalLink className="h-3 w-3" />
      </a>
    </li>
  )
}

function GroupCard({ group }: { group: PriceGroup }) {
  const offers = group.offers
  const cheapest = offers[0]
  const priciest = offers[offers.length - 1]
  const spread = priciest && cheapest ? (priciest.final_price ?? priciest.price) - (cheapest.final_price ?? cheapest.price) : 0
  return (
    <section className="overflow-hidden rounded-2xl border border-[#dbe4ee] bg-white shadow-[0_14px_36px_rgb(16_42_76_/_0.07)]">
      <header className="flex items-center gap-4 border-b border-[#e5ebf2] px-4 py-4 sm:px-5">
        {group.image && (
          <span className="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-white">
            <Image src={group.image} alt="" fill sizes="64px" className="object-contain" unoptimized />
          </span>
        )}
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#52657d]">{group.brand || "Producto"}{group.ean ? ` · EAN ${group.ean}` : ""}</p>
          <h3 className="display text-lg font-semibold leading-snug tracking-[-0.03em] text-[#102a4c]">{group.name}</h3>
          <p className="text-xs text-[#52657d]">
            En {group.store_count} {group.store_count === 1 ? "tienda" : "tiendas"}
            {spread > 0 && <> · hasta <b>{ars(spread)}</b> de diferencia</>}
          </p>
        </div>
      </header>
      {/* Mobile: una tarjeta por tienda; desde sm, tabla comparativa. */}
      <ul className="divide-y divide-[#e5ebf2] sm:hidden">
        {offers.map((offer, index) => <OfferItem key={`${offer.store}-${index}`} offer={offer} best={index === 0 && offers.length > 1} />)}
      </ul>
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full min-w-[720px] table-fixed border-collapse text-left">
          <colgroup>
            <col className="w-[150px]" /><col className="w-[150px]" /><col /><col className="w-[140px]" /><col className="w-[150px]" />
          </colgroup>
          <thead className="bg-[#edf2f7] text-[10px] font-semibold uppercase tracking-[0.13em] text-[#52657d]">
            <tr>
              <th className="px-4 py-2.5 sm:px-5">Tienda</th>
              <th className="px-3 py-2.5">Precio online</th>
              <th className="px-3 py-2.5">Mejor promo de hoy</th>
              <th className="px-3 py-2.5">Precio final</th>
              <th className="px-4 py-2.5 sm:px-5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5ebf2]">
            {offers.map((offer, index) => <OfferRow key={`${offer.store}-${index}`} offer={offer} best={index === 0 && offers.length > 1} />)}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function PreciosPage() {
  const { token, user } = useAuthStore()
  const [input, setInput] = useState("")
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("")
  const [mine, setMine] = useState(false)

  const { data, isFetching, error } = useQuery({
    queryKey: ["prices", query, category, mine],
    queryFn: () => api.searchPrices({ q: query, category: category || undefined, mine: mine || undefined }, token),
    enabled: query.trim().length >= 2,
    staleTime: 5 * 60 * 1000,
  })

  const submit = (value: string) => {
    setInput(value)
    setQuery(value.trim())
  }

  return (
    <div className="min-h-dvh bg-[#f5f7fb]">
      <header className="sticky top-0 z-30 border-b border-[#dbe4ee]/80 bg-[#f5f7fb]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <Link href="/" className="text-[#52657d] hover:text-[#102a4c]" aria-label="Volver al inicio"><ArrowLeft className="h-5 w-5" /></Link>
          <span className="display text-base font-semibold tracking-[-0.05em] text-[#102a4c]">PROMOAR</span>
          <span className="text-[#cbd8e6]">/</span>
          <span className="text-sm text-[#52657d]">Comparador de precios</span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-10">
        <section className="rounded-[1.5rem] bg-[#102a4c] px-6 py-8 text-white sm:px-10">
          <h1 className="display text-3xl font-semibold leading-tight tracking-[-0.05em] sm:text-5xl">¿Dónde está más barato hoy?</h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[#d9e3ef] sm:text-base">
            Comparamos el precio online en Carrefour, Coto, Día, Jumbo, Disco, Vea, ChangoMás, Frávega, Naldo, Easy, Cetrogar, On City y Coppel, y le restamos la mejor promo bancaria vigente hoy.
          </p>
          <form onSubmit={(event) => { event.preventDefault(); submit(input) }} className="mt-6 flex flex-col gap-2 sm:flex-row">
            <label htmlFor="price-query" className="sr-only">Producto</label>
            <input
              id="price-query" value={input} onChange={(event) => setInput(event.target.value)} maxLength={120}
              placeholder="Ej.: leche La Serenísima 1 L"
              className="h-12 w-full rounded-xl sm:flex-1 border border-white/20 bg-white px-4 text-base text-[#102a4c] placeholder:text-[#8a9ab0] focus:outline-none focus:ring-2 focus:ring-[#b8f36b]"
            />
            <button type="submit" disabled={input.trim().length < 2} className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#b8f36b] px-5 text-sm font-semibold text-[#102a4c] transition-colors hover:bg-[#d4ff9e] disabled:opacity-50">
              <Search className="h-4 w-4" /> Comparar
            </button>
          </form>
          <div className="mt-4 flex flex-wrap gap-2">
            {CATEGORIES.map(({ value, label, icon: Icon }) => (
              <button key={value || "all"} type="button" onClick={() => setCategory(value)} aria-pressed={category === value}
                className={`inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition-colors ${category === value ? "bg-[#b8f36b] text-[#102a4c]" : "bg-white/10 text-white hover:bg-white/20"}`}>
                <Icon className="h-3.5 w-3.5" /> {label}
              </button>
            ))}
            {user && (
              <label className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg bg-white/10 px-3 text-xs font-semibold">
                <input type="checkbox" checked={mine} onChange={(event) => setMine(event.target.checked)} className="accent-[#b8f36b]" />
                Solo promos de mis medios de pago
              </label>
            )}
          </div>
        </section>

        {!query && (
          <div className="flex flex-wrap items-center gap-2 text-sm text-[#52657d]">
            Probá con:
            {EXAMPLES.map((example) => (
              <button key={example} type="button" onClick={() => submit(example)} className="rounded-full border border-[#cbd8e6] bg-white px-3 py-1 text-xs font-semibold text-[#102a4c] hover:border-[#102a4c]">{example}</button>
            ))}
          </div>
        )}

        {isFetching && <p className="flex items-center gap-2 text-sm text-[#52657d]"><Loader2 className="h-4 w-4 animate-spin" /> Consultando las tiendas…</p>}
        {error && <p className="rounded-xl border border-[#f0c7c3] bg-[#fff5f4] px-4 py-3 text-sm text-[#9c4138]">{(error as Error).message}</p>}

        {data && !isFetching && (
          <>
            {data.groups.length === 0 ? (
              <p className="rounded-xl bg-white px-4 py-6 text-center text-sm text-[#52657d]">No encontramos <b>{data.query}</b>. Probá con marca y tamaño.</p>
            ) : (
              <div className="space-y-5">{data.groups.map((group) => <GroupCard key={group.key} group={group} />)}</div>
            )}
            <p className="text-xs leading-relaxed text-[#73836e]">
              Precios online publicados por cada tienda; pueden variar por sucursal y no incluyen envío. El precio final es estimado con la mejor promo bancaria vigente hoy (reintegros y topes según cada banco).
              {data.failed_stores.length > 0 && <> No respondieron: {data.failed_stores.join(", ")}.</>}
            </p>
          </>
        )}
      </main>
    </div>
  )
}
