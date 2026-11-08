"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import Image from "next/image"
import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, ExternalLink, Pill, Search } from "lucide-react"
import { api } from "@/lib/api"
import type { PriceGroup, PriceOffer } from "@/lib/types"

const STORES = [
  { key: "farmacity", label: "Farmacity" },
  { key: "farmaplus", label: "FarmaPlus" },
  { key: "drahorro", label: "Dr. Ahorro" },
  { key: "preciosderemedios", label: "Precios de Remedios" },
]
const SUPPLEMENT_STORES = [{ key: "supleradar", label: "SupleRadar" }]

const price = (amount: number) => `$${Math.round(amount).toLocaleString("es-AR")}`
const storePrice = (offer: PriceOffer) => offer.final_price ?? offer.price

export default function PharmacyPage() {
  const [input, setInput] = useState("")
  const [query, setQuery] = useState("")
  const [productType, setProductType] = useState<"pharmacy" | "supplements">("pharmacy")
  const [store, setStore] = useState("")
  const [rubric, setRubric] = useState("")
  const [sort, setSort] = useState("price")

  const { data, isFetching, error } = useQuery({
    queryKey: ["pharmacy-prices", query, productType],
    queryFn: () => api.searchPrices({ q: query, category: productType, limit: 30 }),
    enabled: query.length >= 2,
    staleTime: 5 * 60 * 1000,
  })

  const availableStores = productType === "pharmacy" ? STORES : SUPPLEMENT_STORES
  const rubrics = useMemo(() => {
    const values = new Set((data?.groups ?? []).map((group) => group.category_path?.[0]).filter((value): value is string => !!value))
    return [...values].sort((a, b) => a.localeCompare(b, "es"))
  }, [data])

  const groups = useMemo(() => {
    const filtered: { group: PriceGroup; offers: PriceOffer[]; min: number }[] = []
    for (const group of data?.groups ?? []) {
      if (rubric && group.category_path?.[0] !== rubric) continue
      const offers = group.offers
        .filter((offer) => !store || offer.store === store)
        .sort((a, b) => storePrice(a) - storePrice(b))
      if (!offers.length) continue
      filtered.push({ group, offers, min: storePrice(offers[0]) })
    }
    return filtered.sort((a, b) => sort === "name" ? a.group.name.localeCompare(b.group.name, "es") : a.min - b.min)
  }, [data, rubric, sort, store])

  function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setQuery(input.trim().slice(0, 120))
  }

  return <div className="min-h-dvh bg-[#f5f7fb]">
    <header className="sticky top-0 z-30 border-b border-[#dbe4ee]/80 bg-[#f5f7fb]/90 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
        <Link href="/" className="text-[#52657d] hover:text-[#102a4c]" aria-label="Volver al inicio"><ArrowLeft className="h-5 w-5" /></Link>
        <span className="display text-base font-semibold tracking-[-0.05em] text-[#102a4c]">PROMOAR</span>
        <span className="text-[#cbd8e6]">/</span>
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#102a4c]"><Pill className="h-4 w-4" /> Farmacia</span>
        <Link href="/precios" className="ml-auto text-sm font-semibold text-primary">Todos los precios</Link>
      </div>
    </header>

    <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-10">
      <section className="rounded-[1.5rem] bg-[#102a4c] px-6 py-8 text-white sm:px-10">
        <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#b8f36b]"><Pill className="h-4 w-4" /> Comparador de farmacias</p>
        <h1 className="display mt-3 text-3xl font-semibold leading-tight tracking-[-0.05em] sm:text-5xl">Encontrá el mejor precio.</h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[#d9e3ef] sm:text-base">Buscá medicamentos, cuidado personal y suplementos. Compará precios entre farmacias y fuentes disponibles.</p>
        <form onSubmit={search} className="mt-6 flex flex-col gap-2 sm:flex-row">
          <label className="sr-only" htmlFor="pharmacy-query">Producto de farmacia</label>
          <input id="pharmacy-query" value={input} onChange={(event) => setInput(event.target.value)} maxLength={120} minLength={2} placeholder="Ej.: ibuprofeno, crema, vitamina D…" className="h-12 min-w-0 flex-1 rounded-xl border border-white/20 bg-white px-4 text-sm text-[#102a4c] placeholder:text-[#71839a]" />
          <button type="submit" disabled={input.trim().length < 2} className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[#b8f36b] px-5 text-sm font-semibold text-[#102a4c] hover:bg-[#d4ff9e] disabled:opacity-50"><Search className="h-4 w-4" /> Buscar</button>
        </form>
      </section>

      <section className="space-y-4 rounded-2xl border border-[#dbe4ee] bg-white p-4 sm:p-6" aria-label="Filtros de farmacia">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="text-xs font-semibold uppercase tracking-widest text-[#71839a]">Filtros</p><h2 className="mt-1 text-lg font-semibold text-[#102a4c]">Elegí dónde y qué comparar</h2></div>
          <label className="text-xs font-medium text-[#52657d]">Ordenar por<select value={sort} onChange={(event) => setSort(event.target.value)} className="ml-2 rounded-lg border border-[#cbd8e6] bg-white px-3 py-2 text-sm text-[#102a4c]"><option value="price">Menor precio</option><option value="name">Nombre</option></select></label>
        </div>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2" aria-label="Tipo de producto">
            <button type="button" aria-pressed={productType === "pharmacy"} onClick={() => { setProductType("pharmacy"); setStore(""); setRubric("") }} className={`rounded-full border px-3 py-2 text-xs font-semibold ${productType === "pharmacy" ? "border-[#102a4c] bg-[#102a4c] text-white" : "border-[#cbd8e6] text-[#52657d]"}`}>Farmacias</button>
            <button type="button" aria-pressed={productType === "supplements"} onClick={() => { setProductType("supplements"); setStore(""); setRubric("") }} className={`rounded-full border px-3 py-2 text-xs font-semibold ${productType === "supplements" ? "border-[#102a4c] bg-[#102a4c] text-white" : "border-[#cbd8e6] text-[#52657d]"}`}>Suplementos</button>
          </div>
          <div className="flex flex-wrap gap-2" aria-label="Filtrar por farmacia">
            <button type="button" aria-pressed={!store} onClick={() => setStore("")} className={`rounded-full border px-3 py-2 text-xs font-semibold ${!store ? "border-[#102a4c] bg-[#102a4c] text-white" : "border-[#cbd8e6] text-[#52657d]"}`}>Todas</button>
            {availableStores.map((item) => <button key={item.key} type="button" aria-pressed={store === item.key} onClick={() => setStore(store === item.key ? "" : item.key)} className={`rounded-full border px-3 py-2 text-xs font-semibold ${store === item.key ? "border-[#102a4c] bg-[#102a4c] text-white" : "border-[#cbd8e6] text-[#52657d]"}`}>{item.label}</button>)}
          </div>
          {rubrics.length > 0 && <div className="flex flex-wrap gap-2" aria-label="Filtrar por rubro">
            <button type="button" aria-pressed={!rubric} onClick={() => setRubric("")} className={`rounded-full border px-3 py-2 text-xs font-semibold ${!rubric ? "border-[#2758d8] bg-[#edf3ff] text-[#173e9b]" : "border-[#cbd8e6] text-[#52657d]"}`}>Todos los rubros</button>
            {rubrics.map((item) => <button key={item} type="button" aria-pressed={rubric === item} onClick={() => setRubric(rubric === item ? "" : item)} className={`rounded-full border px-3 py-2 text-xs font-semibold ${rubric === item ? "border-[#2758d8] bg-[#edf3ff] text-[#173e9b]" : "border-[#cbd8e6] text-[#52657d]"}`}>{item}</button>)}
          </div>}
        </div>
      </section>

      {isFetching && <p role="status" className="rounded-xl bg-white px-4 py-5 text-sm text-[#52657d]">Consultando las farmacias…</p>}
      {error && <p role="alert" className="rounded-xl border border-[#f0c7c3] bg-[#fff5f4] px-4 py-3 text-sm text-[#9c4138]">{(error as Error).message}</p>}
      {!query && <p className="rounded-xl bg-white px-4 py-6 text-center text-sm text-[#52657d]">Buscá un producto para ver precios y aplicar filtros por farmacia y rubro.</p>}
      {data && !isFetching && <>
        <p className="text-sm text-[#52657d]">{groups.length} productos encontrados{store ? ` en ${availableStores.find((item) => item.key === store)?.label}` : ""}</p>
        {groups.length === 0 ? <p className="rounded-xl bg-white px-4 py-6 text-center text-sm text-[#52657d]">No encontramos <b>{data.query}</b> con esos filtros. Probá otra búsqueda o elegí otra farmacia.</p> :
          <div className="grid gap-4 md:grid-cols-2">{groups.map(({ group, offers }) => <article key={group.key} className="overflow-hidden rounded-2xl border border-[#dbe4ee] bg-white shadow-sm">
            <div className="flex items-start gap-3 border-b border-[#e5ebf2] p-4">
              {group.image && <Image src={group.image} alt="" width={56} height={56} unoptimized className="h-14 w-14 shrink-0 rounded-lg bg-white object-contain" />}
              <div className="min-w-0"><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#71839a]">{group.category_path?.join(" · ") || group.brand || "Farmacia"}</p><h3 className="mt-1 font-semibold leading-snug text-[#102a4c]">{group.name}</h3></div>
            </div>
            <ul className="divide-y divide-[#e5ebf2]">{offers.map((offer) => <li key={`${offer.store}-${offer.url}`} className="flex items-center justify-between gap-3 p-4">
              <div className="min-w-0"><p className="text-sm font-semibold text-[#102a4c]">{offer.store_name}</p><p className="mt-0.5 text-lg font-bold text-[#102a4c]">{price(storePrice(offer))}</p>{offer.savings > 0 && <p className="text-xs font-semibold text-[#3d6626]">Ahorro estimado {price(offer.savings)}</p>}</div>
              <a href={offer.url} target="_blank" rel="noopener noreferrer" className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-[#2758d8]">Ver producto <ExternalLink className="h-3.5 w-3.5" /></a>
            </li>)}</ul>
          </article>)}</div>}
        {data.failed_stores.length > 0 && <p className="text-xs text-[#71839a]">No respondieron: {data.failed_stores.join(", ")}.</p>}
        <p className="text-xs leading-relaxed text-[#71839a]">Precios publicados por cada tienda; pueden cambiar según sucursal y disponibilidad. Los precios de referencia de medicamentos no son cotizaciones de una sucursal.</p>
      </>}
    </main>
  </div>
}
