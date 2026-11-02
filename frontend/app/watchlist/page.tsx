"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Check, ExternalLink, Loader2, MessageCircle, PackageSearch, RefreshCw, Save, Search, Store, Trash2 } from "lucide-react"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"
import { BasketComparison } from "@/components/BasketComparison"
import { bestQuote, groupWatchlistProducts, money, quoteDate } from "@/lib/watchlist"

const fold = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()

export default function WatchlistPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { token, user } = useAuthStore()
  const [selectedStores, setSelectedStores] = useState<string[] | null>(null)
  const [storeSearch, setStoreSearch] = useState("")
  const [showStorePicker, setShowStorePicker] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [refreshing, setRefreshing] = useState(false)
  const [progress, setProgress] = useState(0)
  const refreshController = useRef<AbortController | null>(null)

  useEffect(() => { if (!token) router.push("/login") }, [token, router])
  useEffect(() => () => { refreshController.current?.abort() }, [user?.id])

  const watchlist = useQuery({
    queryKey: ["watchlist", user?.id], queryFn: () => api.getWatchlist(token!),
    enabled: !!token && !!user, retry: false,
  })
  const supermarkets = useQuery({
    queryKey: ["supermarkets", "supermarket"], queryFn: () => api.getSupermarkets("supermarket"),
    enabled: !!token,
  })

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["watchlist", user?.id] }),
      queryClient.invalidateQueries({ queryKey: ["watchlist-basket", user?.id] }),
    ])
  }

  const saveStores = useMutation({
    mutationFn: () => api.updateWatchlistStores(selectedStores ?? watchlist.data?.stores ?? [], token!),
    onSuccess: async ({ stores }) => {
      setSelectedStores(null)
      setError("")
      setMessage(`Supermercados guardados (${stores.length}). La comparación y tu próximo digest usarán esta selección.`)
      await invalidate()
    },
    onError: (reason: Error) => { setMessage(""); setError(reason.message) },
  })
  const deleteProduct = useMutation({
    mutationFn: (id: number) => api.deletePriceAlert(id, token!),
    onSuccess: async () => { setError(""); setMessage("Producto eliminado de tu lista."); await invalidate() },
    onError: (reason: Error) => { setMessage(""); setError(reason.message) },
  })

  const data = watchlist.data
  const products = data?.products ?? []
  const categories = groupWatchlistProducts(products)
  const knownPrices = products.filter((p) => bestQuote(p)).length
  const storeSelection = selectedStores ?? data?.stores ?? []
  const storeLimit = data?.limits.stores ?? 12

  async function refreshPrices() {
    if (!token || refreshing || !products.length) return
    const controller = new AbortController()
    refreshController.current = controller
    setRefreshing(true)
    setProgress(0)
    setMessage("")
    setError("")
    let done = 0, missing = 0, failed = 0, cached = 0
    try {
      // Lotes chicos: cada request tiene trabajo acotado y cada ID se valida contra el dueño.
      const ids = products.map((p) => p.id)
      for (let index = 0; index < ids.length && !controller.signal.aborted; index += 3) {
        const response = await api.refreshWatchlistPrices(ids.slice(index, index + 3), token, controller.signal)
        done += response.results.length
        missing += response.results.filter((r) => r.status === "missing").length
        failed += response.results.filter((r) => r.status === "error").length
        cached += response.results.filter((r) => r.status === "cached").length
        setProgress(done)
        await invalidate()
      }
      if (!controller.signal.aborted) setMessage(`Revisión terminada: ${done} productos, ${missing} sin oferta reciente y ${failed} con error de consulta. ${cached} conservaron una consulta reciente en caché.`)
    } catch (reason) {
      if (controller.signal.aborted) setMessage("Actualización detenida. Se conservan los precios ya consultados.")
      else setError((reason as Error).message)
    } finally {
      if (refreshController.current === controller) {
        refreshController.current = null
        setRefreshing(false)
        await invalidate()
      }
    }
  }

  function toggleStore(name: string) {
    setMessage("")
    setError("")
    const current = selectedStores ?? data?.stores ?? []
    if (current.includes(name)) setSelectedStores(current.filter((s) => s !== name))
    else if (current.length < storeLimit) setSelectedStores([...current, name])
    else setError(`Podés guardar hasta ${storeLimit} supermercados.`)
  }

  if (!token || !user) return null
  const visibleStores = (supermarkets.data ?? []).filter((s) => fold(s.name).includes(fold(storeSearch)))

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-7xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
          <Link href="/" aria-label="Volver al inicio" className="text-muted-foreground hover:text-foreground"><ArrowLeft className="h-5 w-5" /></Link>
          <span className="display text-base font-semibold tracking-tight">PROMOAR</span><span className="text-muted-foreground">/ Mi lista habitual</span>
          <Link href="/precios" className="ml-auto text-sm font-semibold text-primary">Agregar productos →</Link>
        </div>
      </header>
      <main className="mx-auto max-w-7xl space-y-6 px-4 py-7 sm:px-6 sm:py-10">
        <section className="flex flex-wrap items-end justify-between gap-5">
          <div className="max-w-2xl"><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Tu radar de compras</p><h1 className="display text-3xl font-semibold tracking-tight sm:text-4xl">Tu lista, con números claros.</h1><p className="mt-3 text-sm leading-relaxed text-muted-foreground">Productos por categoría, menor precio online relevado y comparación de canasta con tus medios de pago. Sin contar precios desconocidos como cero.</p></div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={refreshPrices} disabled={refreshing || !products.length} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-accent px-4 text-sm font-semibold text-accent-foreground hover:opacity-90 disabled:opacity-50">
              {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} {refreshing ? `Consultando ${progress}/${products.length}` : "Actualizar precios"}
            </button>
            {refreshing && <button type="button" onClick={() => refreshController.current?.abort()} className="rounded-xl border border-border px-3 text-sm">Detener</button>}
          </div>
        </section>
        <div className="grid grid-cols-3 divide-x divide-border rounded-xl border border-border bg-card text-card-foreground">
          {[["Productos", products.length], ["Categorías", categories.length], ["Con precio reciente", `${knownPrices}/${products.length}`]].map(([label, value]) => <div key={label} className="p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-semibold">{value}</p></div>)}
        </div>
        {refreshing && <p role="status" aria-live="polite" className="text-sm text-muted-foreground">Las consultas pueden demorar. Las ofertas recientes se reutilizan y podés detener los siguientes lotes.</p>}
        {(message || error || watchlist.error) && <div role={error || watchlist.error ? "alert" : "status"} className="rounded-xl border border-border bg-card px-4 py-3 text-sm text-card-foreground">{error || (watchlist.error as Error | null)?.message || message}</div>}
        {data?.prices_available === false && <p role="status" className="rounded-xl border border-border p-4 text-sm text-muted-foreground">Tu lista está guardada, pero los precios están temporalmente no disponibles. No se reemplazaron por $0.</p>}
        {data && !data.telegram_linked && !user.whatsapp_opt_in && <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 text-card-foreground"><p className="flex items-center gap-2 text-sm"><MessageCircle className="h-4 w-4 text-primary" /> Tu lista se guarda. Vinculá un canal para recibir alertas.</p><Link href="/profile" className="text-sm font-semibold text-primary">Configurar avisos →</Link></div>}

        <BasketComparison token={token} userId={user.id} productCount={products.length} />

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
          <section aria-labelledby="products-heading" className="min-w-0 space-y-4">
            <header className="flex items-end justify-between gap-3"><div><h2 id="products-heading" className="display text-2xl font-semibold tracking-tight">Productos habituales</h2><p className="mt-1 text-xs text-muted-foreground">Menor precio publicado entre locales relevados, sin reintegros ni envío.</p></div><span className="rounded-full bg-secondary px-3 py-1 text-xs font-semibold text-secondary-foreground">{products.length}/{data?.limits.products ?? 100}</span></header>
            {watchlist.isLoading && <p role="status" className="flex items-center gap-2 py-5 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Cargando tu lista…</p>}
            {categories.map(({ category, products: items }) => <section key={category} aria-label={category} className="overflow-hidden rounded-xl border border-border bg-card text-card-foreground">
              <header className="flex items-center justify-between gap-3 border-b border-l-4 border-border border-l-accent bg-secondary px-4 py-4 text-secondary-foreground sm:px-5"><h3 className="display text-lg font-semibold">{category}</h3><span className="rounded-full bg-card px-2.5 py-1 text-xs font-semibold text-card-foreground">{items.length} productos</span></header>
              <ul className="divide-y divide-border">{items.map((product) => {
                const quote = bestQuote(product)
                const subcategory = product.category_path?.slice(1).join(" › ")
                return <li key={product.id} className="p-4 sm:px-5">
                  <div className="flex items-start justify-between gap-3"><div className="min-w-0 flex-1"><p className="text-base font-semibold leading-snug">{product.product_name}</p>{subcategory && <p className="mt-1 text-[11px] text-muted-foreground">{subcategory}</p>}</div><button type="button" disabled={deleteProduct.isPending || refreshing} onClick={() => deleteProduct.mutate(product.id)} aria-label={`Eliminar ${product.product_name}`} className="shrink-0 rounded-lg p-2 text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-40"><Trash2 className="h-4 w-4" /></button></div>
                  {quote ? <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm"><span className="font-semibold text-primary">{money(quote.price)}</span><a href={quote.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium hover:underline">{quote.store_name}<ExternalLink className="h-3 w-3" /></a><span className="text-xs text-muted-foreground">Online · consultado {quoteDate(quote.observed_at)}</span></div> : <p className="mt-2 text-sm text-muted-foreground">Sin precio reciente · actualizá para consultar tiendas.</p>}
                  <p className="mt-2 text-xs text-muted-foreground">{product.target_price && product.target_price > 0 ? `Avisar en ${money(product.target_price)} o menos` : "Avisar ante una baja"}{Number.isFinite(product.baseline_price) && product.baseline_price > 0 ? ` · referencia de alerta: ${money(product.baseline_price)}` : " · referencia de alerta pendiente"}</p>
                  {product.product_key.startsWith("title:") && <p className="mt-1 text-[11px] text-muted-foreground">Identificado por nombre: puede dejar de coincidir si la tienda cambia el título.</p>}
                </li>
              })}</ul>
            </section>)}
            {data && products.length === 0 && <div className="rounded-xl border border-dashed border-border bg-card p-8 text-center text-card-foreground"><PackageSearch className="mx-auto h-7 w-7 text-muted-foreground" /><p className="mt-3 font-semibold">Todavía no hay productos en tu lista</p><p className="mt-2 text-sm text-muted-foreground">Buscá un producto y elegí “Guardar y avisarme”.</p></div>}
            <Link href="/precios" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground"><Search className="h-4 w-4" /> Buscar y agregar productos</Link>
          </section>

          <aside className="rounded-xl border border-border bg-card p-5 text-card-foreground">
            <div className="flex items-center justify-between gap-3"><h2 className="display flex items-center gap-2 text-lg font-semibold"><Store className="h-5 w-5 text-primary" /> Mis supermercados</h2><span className="text-xs text-muted-foreground">{storeSelection.length}/{storeLimit}</span></div>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">Esta selección se usa en la comparación y el digest. Sin selección se consideran los locales disponibles.</p>
            <div className="mt-4 flex flex-wrap gap-2">{storeSelection.map((name) => <span key={name} className="rounded-lg bg-secondary px-2 py-1.5 text-xs font-medium text-secondary-foreground">{name}</span>)}</div>
            <button type="button" aria-expanded={showStorePicker} aria-controls="store-picker" onClick={() => setShowStorePicker(!showStorePicker)} className="mt-4 text-sm font-semibold text-primary">{showStorePicker ? "Cerrar selección" : "Editar supermercados"}</button>
            {showStorePicker && <div id="store-picker" className="mt-4 space-y-3"><label className="sr-only" htmlFor="store-search">Buscar supermercado</label><input id="store-search" value={storeSearch} onChange={(event) => setStoreSearch(event.target.value)} placeholder="Buscar supermercado…" className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" />
              {supermarkets.isLoading && <p className="text-xs text-muted-foreground">Cargando supermercados…</p>}
              {supermarkets.error && <p role="alert" className="text-xs text-muted-foreground">No pudimos cargar los supermercados.</p>}
              <div className="max-h-72 space-y-2 overflow-y-auto">{visibleStores.map((store) => { const active = storeSelection.includes(store.name); return <button key={store.id} type="button" aria-pressed={active} onClick={() => toggleStore(store.name)} className={`flex min-h-10 w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-xs font-semibold ${active ? "border-primary bg-secondary text-secondary-foreground" : "border-border hover:bg-secondary"}`}><span>{store.name}</span>{active && <Check className="h-4 w-4 shrink-0 text-primary" />}</button> })}</div>
              <div className="flex items-center justify-between gap-2 border-t border-border pt-3"><button type="button" disabled={!storeSelection.length} onClick={() => setSelectedStores([])} className="text-xs text-muted-foreground disabled:opacity-40">Limpiar</button><button type="button" disabled={saveStores.isPending || !data} onClick={() => saveStores.mutate()} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-primary px-3 text-xs font-semibold text-primary-foreground disabled:opacity-40">{saveStores.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Guardar</button></div>
            </div>}
            {selectedStores !== null && <p className="mt-3 text-xs font-semibold text-primary">Hay cambios sin guardar; la comparación conserva la selección guardada.</p>}
          </aside>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">Precios online orientativos. No incluyen envío ni garantizan el precio de una sucursal presencial. Las consultas reutilizan caché de fuentes de hasta dos horas; el botón conserva consultas propias menores a una hora.</p>
      </main>
    </div>
  )
}
