"use client"

import { useState } from "react"
import Image from "next/image"
import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Loader2 } from "lucide-react"
import { api } from "@/lib/api"

export function PriceCatalog({ ean, onClearBarcode, onChoose }: {
  ean: string; onClearBarcode: () => void; onChoose: (key: string) => void
}) {
  const [rubric, setRubric] = useState("")
  const [sort, setSort] = useState("recent")
  const [page, setPage] = useState(1)
  const [input, setInput] = useState("")
  const [q, setQ] = useState("")
  const { data, error, isFetching } = useQuery({
    queryKey: ["price-catalog", ean, rubric, sort, page, q],
    queryFn: () => api.getPriceCatalog({ ean, rubric: ean ? "" : rubric, sort, page: ean ? 1 : page, q: ean ? "" : q }),
    staleTime: 60_000,
  })
  const { data: crawl } = useQuery({ queryKey: ["supermarket-catalog-status"],
    queryFn: api.getSupermarketCatalogStatus, staleTime: 120_000 })
  return <section id="catalogo" className="space-y-5 rounded-2xl border border-border bg-card p-4 text-card-foreground sm:p-6" aria-labelledby="catalog-title">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Catálogo relevado</p><h2 id="catalog-title" className="display mt-1 text-2xl font-semibold tracking-tight">Explorá antes de comprar.</h2><p className="mt-2 max-w-xl text-sm text-muted-foreground">Precios online confirmados en los últimos {data?.fresh_days ?? 3} días. No incluyen envío ni promociones bancarias.</p></div>
      <label className="text-xs text-muted-foreground">Ordenar por<select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1) }} className="mt-1 block rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"><option value="recent">Más recientes</option><option value="price_asc">Menor precio</option><option value="price_desc">Mayor precio</option><option value="name">Nombre</option></select></label>
    </div>
    {crawl && <details className="rounded-xl bg-secondary px-4 py-3 text-sm text-secondary-foreground">
      <summary className="cursor-pointer font-semibold">Estado del relevamiento de supermercados</summary>
      <p className="mt-2 text-xs">El catálogo se actualiza por partes. Las publicaciones sin precio válido o identificación estable pueden quedar afuera.</p>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">{crawl.stores.map((store) => <li key={store.store} className="text-xs">
        <b>{store.name}:</b> {!store.started_at ? "pendiente" : store.last_error_at ? "reintentando" : store.completed_at ? "recorrido terminado" : "en curso"}
        {store.started_at && <> · {store.records.toLocaleString("es-AR")} publicaciones revisadas</>}
      </li>)}</ul>
    </details>}
    {ean ? <div className="flex flex-wrap items-center gap-3 rounded-xl bg-secondary px-4 py-3 text-sm text-secondary-foreground"><span>Código leído: <b>{ean}</b></span><button type="button" onClick={onClearBarcode} className="font-semibold underline">Ver todo el catálogo</button></div> : <>
      <form onSubmit={(event) => { event.preventDefault(); setQ(input.trim()); setPage(1) }} className="flex gap-2"><label className="sr-only" htmlFor="catalog-search">Buscar en el catálogo relevado</label><input id="catalog-search" value={input} onChange={(event) => setInput(event.target.value)} maxLength={120} placeholder="Filtrar productos ya relevados…" className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm" /><button type="submit" className="rounded-xl bg-secondary px-4 text-sm font-semibold text-secondary-foreground">Filtrar</button></form>
      <div className="flex flex-wrap gap-2" aria-label="Rubros del catálogo"><button type="button" aria-pressed={!rubric} onClick={() => { setRubric(""); setPage(1) }} className={`rounded-full border px-3 py-2 text-xs font-semibold ${!rubric ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>Todos</button>{data?.facets.map((facet) => <button key={facet.name} type="button" aria-pressed={rubric === facet.name} onClick={() => { setRubric(facet.name); setPage(1) }} className={`rounded-full border px-3 py-2 text-xs font-semibold ${rubric === facet.name ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-secondary"}`}>{facet.name} ({facet.count})</button>)}</div>
    </>}
    {isFetching && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Consultando el catálogo…</p>}
    {error && <p role="alert" className="text-sm text-red-600">{(error as Error).message}</p>}
    {data && !isFetching && <>
      <p className="text-xs text-muted-foreground">{data.total} productos con precios recientes{!ean && " · El orden por precio no compara tamaños distintos como si fueran equivalentes."}</p>
      {data.products.length === 0 && <p className="rounded-xl bg-secondary p-5 text-sm text-secondary-foreground">{ean ? "No encontramos precios recientes para este código exacto. Podés buscar el producto por nombre arriba; no vamos a reemplazarlo por uno parecido." : "Todavía no hay productos recientes para este filtro. Probá la búsqueda en vivo de arriba. El catálogo se completa con la recolección programada."}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{data.products.map((product) => <button type="button" key={product.key} onClick={() => onChoose(product.key)} className="group flex flex-col items-start rounded-xl border border-border p-4 text-left transition-colors hover:border-primary focus-visible:outline-2 focus-visible:outline-ring">
        <div className="mb-3 flex w-full items-start justify-between gap-3"><span className="text-xs text-muted-foreground">{product.category_path.join(" › ") || "Otros"}</span>{product.image && <Image src={product.image} alt="" width={48} height={48} className="h-12 w-12 rounded-lg bg-white object-contain" unoptimized onError={(event) => { event.currentTarget.style.display = "none" }} />}</div>
        <h3 className="text-sm font-semibold leading-snug">{product.name}</h3><p className="mt-3 text-xl font-semibold tracking-tight">Desde ${Math.round(product.price).toLocaleString("es-AR")}</p><p className="mt-1 text-xs text-muted-foreground">{product.store_count} tienda{product.store_count !== 1 && "s"} · confirmado {product.observed_at.split("-").reverse().join("/")}</p><span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary">Comparar y guardar <ArrowRight className="h-3 w-3" /></span>
      </button>)}</div>
      {!ean && data.total > data.page_size && <div className="flex items-center justify-between gap-3"><button type="button" disabled={page === 1} onClick={() => setPage(page-1)} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">Anterior</button><span className="text-xs text-muted-foreground">Página {page} de {Math.ceil(data.total/data.page_size)}</span><button type="button" disabled={page*data.page_size >= data.total} onClick={() => setPage(page+1)} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">Siguiente</button></div>}
    </>}
  </section>
}
