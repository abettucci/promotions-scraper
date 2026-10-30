"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft, BellRing, Check, Loader2, MessageCircle, PackageSearch,
  Save, Search, Store, Trash2,
} from "lucide-react"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"

const ars = (value: number) => `$${Math.round(value).toLocaleString("es-AR")}`

export default function WatchlistPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { token, user } = useAuthStore()
  const [selectedStores, setSelectedStores] = useState<string[] | null>(null)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  useEffect(() => {
    if (!token) router.push("/login")
  }, [token, router])

  const watchlist = useQuery({
    queryKey: ["watchlist"],
    queryFn: () => api.getWatchlist(token!),
    enabled: !!token,
  })
  const supermarkets = useQuery({
    queryKey: ["supermarkets", "supermarket"],
    queryFn: () => api.getSupermarkets("supermarket"),
    enabled: !!token,
  })

  const saveStores = useMutation({
    mutationFn: () => api.updateWatchlistStores(selectedStores ?? watchlist.data?.stores ?? [], token!),
    onSuccess: async ({ stores }) => {
      setSelectedStores(stores)
      setError("")
      setMessage("Supermercados guardados. Tu próximo digest usará esta lista.")
      await queryClient.invalidateQueries({ queryKey: ["watchlist"] })
    },
    onError: (reason: Error) => { setMessage(""); setError(reason.message) },
  })

  const deleteProduct = useMutation({
    mutationFn: (id: number) => api.deletePriceAlert(id, token!),
    onSuccess: async () => {
      setError("")
      setMessage("Producto eliminado de tu lista.")
      await queryClient.invalidateQueries({ queryKey: ["watchlist"] })
    },
    onError: (reason: Error) => { setMessage(""); setError(reason.message) },
  })

  if (!token || !user) return null

  const data = watchlist.data
  const storeLimit = data?.limits.stores ?? 12
  const productLimit = data?.limits.products ?? 100
  const storeSelection = selectedStores ?? data?.stores ?? []

  function toggleStore(name: string) {
    setMessage("")
    setError("")
    setSelectedStores((current) => {
      const selection = current ?? watchlist.data?.stores ?? []
      if (selection.includes(name)) return selection.filter((store) => store !== name)
      if (selection.length >= storeLimit) {
        setError(`Podés guardar hasta ${storeLimit} supermercados.`)
        return selection
      }
      return [...selection, name]
    })
  }

  return (
    <div className="min-h-dvh bg-[#f5f7fb] text-[#102a4c]">
      <header className="sticky top-0 z-30 border-b border-[#dbe4ee]/80 bg-[#f5f7fb]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4 sm:px-6">
          <Link href="/" aria-label="Volver al inicio" className="text-[#52657d] transition-colors hover:text-[#102a4c]">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <span className="display text-base font-semibold tracking-[-0.05em]">PROMOAR</span>
          <span className="text-[#cbd8e6]">/</span>
          <span className="text-sm text-[#52657d]">Mi lista habitual</span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-7 sm:px-6 sm:py-10">
        <section className="relative overflow-hidden rounded-[1.65rem] bg-[#102a4c] px-6 py-8 text-white sm:px-9 sm:py-10">
          <div className="pointer-events-none absolute -right-12 -top-20 h-64 w-64 rounded-full border-[42px] border-[#b8f36b]/10" />
          <div className="relative max-w-2xl">
            <p className="mb-4 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.13em] text-[#b8f36b]">
              <BellRing className="h-3.5 w-3.5" /> Tu radar de compras
            </p>
            <h1 className="display text-3xl font-semibold leading-tight tracking-[-0.055em] sm:text-5xl">
              Guardá lo que comprás. Te avisamos cuándo conviene.
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-[#d9e3ef] sm:text-base">
              Elegí tus supermercados y productos habituales. El digest se concentra en esos comercios y las alertas detectan bajas o un mejor precio final con tus medios de pago.
            </p>
          </div>
        </section>

        {(message || error) && (
          <div role="status" className={`flex items-start gap-2 rounded-xl border px-4 py-3 text-sm ${error ? "border-[#f0c7c3] bg-[#fff5f4] text-[#9c4138]" : "border-[#c9e7a3] bg-[#f4ffec] text-[#31551e]"}`}>
            {error ? <BellRing className="mt-0.5 h-4 w-4 shrink-0" /> : <Check className="mt-0.5 h-4 w-4 shrink-0" />}
            {error || message}
          </div>
        )}

        {!data?.telegram_linked && (
          <div className="flex flex-col gap-3 rounded-2xl border border-[#bfd0e1] bg-white px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#edf3ff] text-[#2758d8]"><MessageCircle className="h-4 w-4" /></span>
              <div>
                <p className="text-sm font-semibold">Falta vincular Telegram</p>
                <p className="mt-0.5 text-xs leading-relaxed text-[#52657d]">La lista se guarda igual, pero necesitás un Chat ID para recibir los avisos.</p>
              </div>
            </div>
            <Link href="/profile" className="text-sm font-semibold text-[#2758d8] hover:text-[#102a4c]">Vincular ahora →</Link>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[1.05fr_.95fr]">
          <section className="overflow-hidden rounded-2xl border border-[#dbe4ee] bg-white shadow-[0_14px_36px_rgb(16_42_76_/_0.06)]">
            <header className="flex items-start justify-between gap-4 border-b border-[#e5ebf2] px-5 py-5">
              <div className="flex items-start gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#efffdc] text-[#3d6626]"><Store className="h-5 w-5" /></span>
                <div>
                  <h2 className="display text-xl font-semibold tracking-[-0.04em]">Mis supermercados</h2>
                  <p className="mt-1 text-xs leading-relaxed text-[#52657d]">Si elegís alguno, el digest diario mostrará sólo estos comercios.</p>
                </div>
              </div>
              <span className="shrink-0 rounded-full bg-[#edf2f7] px-2.5 py-1 text-xs font-semibold text-[#52657d]">{storeSelection.length}/{storeLimit}</span>
            </header>
            <div className="p-5">
              {supermarkets.isLoading ? (
                <p className="flex items-center gap-2 py-5 text-sm text-[#52657d]"><Loader2 className="h-4 w-4 animate-spin" /> Cargando supermercados…</p>
              ) : (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {(supermarkets.data ?? []).map((store) => {
                    const active = storeSelection.includes(store.name)
                    return (
                      <button key={store.id} type="button" onClick={() => toggleStore(store.name)} aria-pressed={active}
                        className={`min-h-12 rounded-xl border px-3 py-2 text-left text-xs font-semibold transition-all ${active ? "border-[#102a4c] bg-[#102a4c] text-white shadow-sm" : "border-[#dbe4ee] bg-[#f9fbfd] text-[#40536b] hover:border-[#91a4b9] hover:bg-white"}`}>
                        <span className="flex items-center justify-between gap-2"><span>{store.name}</span>{active && <Check className="h-3.5 w-3.5 shrink-0 text-[#b8f36b]" />}</span>
                      </button>
                    )
                  })}
                </div>
              )}
              <div className="mt-5 flex items-center justify-between border-t border-[#e5ebf2] pt-4">
                <button type="button" onClick={() => setSelectedStores([])} disabled={!storeSelection.length} className="text-xs font-semibold text-[#71839a] hover:text-[#102a4c] disabled:opacity-40">Limpiar</button>
                <button type="button" onClick={() => saveStores.mutate()} disabled={saveStores.isPending || watchlist.isLoading}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#102a4c] px-4 text-sm font-semibold text-white transition-colors hover:bg-[#183b67] disabled:opacity-60">
                  {saveStores.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Guardar supers
                </button>
              </div>
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-[#dbe4ee] bg-white shadow-[0_14px_36px_rgb(16_42_76_/_0.06)]">
            <header className="flex items-start justify-between gap-4 border-b border-[#e5ebf2] px-5 py-5">
              <div className="flex items-start gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#edf3ff] text-[#2758d8]"><PackageSearch className="h-5 w-5" /></span>
                <div>
                  <h2 className="display text-xl font-semibold tracking-[-0.04em]">Productos habituales</h2>
                  <p className="mt-1 text-xs leading-relaxed text-[#52657d]">Te avisamos si baja el precio o aparece una promo que mejora el precio final.</p>
                </div>
              </div>
              <span className="shrink-0 rounded-full bg-[#edf2f7] px-2.5 py-1 text-xs font-semibold text-[#52657d]">{data?.products.length ?? 0}/{productLimit}</span>
            </header>
            <div className="p-5">
              {watchlist.isLoading ? (
                <p className="flex items-center gap-2 py-5 text-sm text-[#52657d]"><Loader2 className="h-4 w-4 animate-spin" /> Cargando productos…</p>
              ) : data?.products.length ? (
                <ul className="divide-y divide-[#e5ebf2]">
                  {data.products.map((product) => (
                    <li key={product.id} className="flex items-start justify-between gap-4 py-3 first:pt-0">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{product.product_name}</p>
                        <p className="mt-1 text-xs text-[#52657d]">
                          {product.target_price ? `Avisar en ${ars(product.target_price)} o menos` : "Avisar ante una baja"}
                          {` · referencia ${ars(product.baseline_price)}`}
                        </p>
                      </div>
                      <button type="button" onClick={() => deleteProduct.mutate(product.id)} disabled={deleteProduct.isPending}
                        aria-label={`Eliminar ${product.product_name}`} className="rounded-lg p-2 text-[#8a9ab0] transition-colors hover:bg-[#fff1ef] hover:text-[#a9362a] disabled:opacity-50">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="rounded-xl border border-dashed border-[#cbd8e6] bg-[#f9fbfd] px-4 py-7 text-center">
                  <PackageSearch className="mx-auto h-6 w-6 text-[#91a4b9]" />
                  <p className="mt-2 text-sm font-semibold">Tu lista todavía está vacía</p>
                  <p className="mt-1 text-xs text-[#71839a]">Buscá un producto, compará precios y guardalo desde el resultado exacto.</p>
                </div>
              )}
              <Link href="/precios" className="mt-5 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-xl bg-[#b8f36b] px-4 text-sm font-semibold text-[#102a4c] transition-colors hover:bg-[#d4ff9e]">
                <Search className="h-4 w-4" /> Buscar y agregar producto
              </Link>
            </div>
          </section>
        </div>

        <p className="px-1 text-xs leading-relaxed text-[#71839a]">
          Las alertas se revisan periódicamente sobre precios online publicados. El precio final con promociones es estimado y puede depender de topes, stock y condiciones del comercio.
        </p>
      </main>
    </div>
  )
}
