"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, CalendarDays, Loader2, Plus, ReceiptText, RefreshCw, Trash2 } from "lucide-react"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"
import { argentinaDay, purchaseStatus, share } from "@/lib/purchases"
import { money, quoteDate } from "@/lib/watchlist"
import type { PurchaseInput } from "@/lib/types"

const inputClass = "mt-1.5 min-h-11 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"

export default function PurchasesPage() {
  const { user, token } = useAuthStore()
  const router = useRouter()
  const client = useQueryClient()
  const [period, setPeriod] = useState<{ date_from?: string; date_to?: string }>({})
  const [page, setPage] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const requestId = useRef<string | null>(null)
  const formRef = useRef<HTMLFormElement | null>(null)

  useEffect(() => { if (!token) router.push("/login") }, [token, router])
  const options = useQuery({ queryKey: ["purchase-options", user?.id], queryFn: () => api.getPurchaseOptions(token!), enabled: !!token && !!user, retry: false })
  const report = useQuery({ queryKey: ["purchases", user?.id, period, page], queryFn: () => api.getPurchases(token!, { ...period, page }), enabled: !!token && !!user, retry: false })
  async function invalidate() { await client.invalidateQueries({ queryKey: ["purchases", user?.id] }) }
  function failure(reason: Error) { setMessage(""); setError(reason.message.includes("[object Object]") ? "Revisá los campos: fecha pasada, montos positivos y descuento no mayor al monto original." : reason.message) }
  const save = useMutation({ mutationFn: (body: PurchaseInput) => api.createPurchase(token!, body), onError: failure,
    onSuccess: async () => { requestId.current = null; formRef.current?.reset(); setError(""); setMessage("Compra guardada. El cruce usa el histórico, no las promociones de hoy."); setPage(1); await invalidate() } })
  const remove = useMutation({ mutationFn: (id: string) => api.deletePurchase(token!, id), onError: failure,
    onSuccess: async () => { setConfirmDelete(null); setError(""); setMessage("Compra eliminada de tus métricas."); await invalidate() } })
  const refresh = useMutation({ mutationFn: () => api.refreshPurchaseHistory(token!), onError: failure,
    onSuccess: async () => { setError(""); setMessage("Histórico disponible sincronizado. No se inventaron fechas ni condiciones faltantes."); await invalidate() } })

  if (!user || !token) return null
  const data = report.data, summary = data?.summary
  return <div className="min-h-dvh bg-background text-foreground">
    <header className="border-b border-border bg-card"><div className="mx-auto flex min-h-16 max-w-6xl items-center gap-3 px-4 sm:px-6"><Link href="/" aria-label="Volver al inicio" className="text-muted-foreground"><ArrowLeft className="h-5 w-5" /></Link><span className="display font-semibold">PROMOAR</span><span className="text-muted-foreground">/ Mis compras</span><Link href="/watchlist" className="ml-auto text-sm font-semibold text-primary">Mi lista habitual →</Link></div></header>
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6 sm:py-10">
      <section className="flex flex-wrap items-end justify-between gap-5"><div className="max-w-2xl"><p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Después de comprar</p><h1 className="display mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">¿Compraste en día de promo?</h1><p className="mt-3 text-sm leading-relaxed text-muted-foreground">Cruzá tus compras realizadas con las condiciones observadas ese día. Un porcentaje publicado no equivale a un descuento cobrado.</p></div><button type="button" aria-expanded={showForm} aria-controls="purchase-form" onClick={() => setShowForm(!showForm)} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground"><Plus className="h-4 w-4" />{showForm ? "Cerrar carga" : "Registrar compra"}</button></section>

      {showForm && <section id="purchase-form" className="rounded-2xl border border-border bg-card p-5 sm:p-6"><h2 className="display text-xl font-semibold">Registrar una compra realizada</h2><p className="mt-2 text-xs leading-relaxed text-muted-foreground">Carga manual. No se importan consumos bancarios ni se guardan números de tarjeta. El monto original es el total antes de descuento o reintegro.</p>
        {options.error && <p role="alert" className="mt-3 text-sm text-destructive">No pudimos cargar el catálogo. <button onClick={() => options.refetch()} type="button" className="underline">Reintentar</button></p>}
        <form ref={formRef} onChange={() => { requestId.current = null }} onSubmit={(event) => {
          event.preventDefault(); if (save.isPending) return
          const form = new FormData(event.currentTarget), value = (name: string) => String(form.get(name) || "")
          requestId.current ??= crypto.randomUUID()
          save.mutate({ request_id: requestId.current, purchased_on: value("purchased_on"), merchant: value("merchant"), amount: value("amount"), received_discount: value("received_discount") || null, bank: value("bank"), wallet: value("wallet"), card_type: value("card_type") as PurchaseInput["card_type"], modality: value("modality") as PurchaseInput["modality"] })
        }} className="mt-5">
          <fieldset disabled={save.isPending} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="text-xs font-semibold">Fecha de compra<input name="purchased_on" type="date" min="2000-01-01" max={argentinaDay()} defaultValue={argentinaDay()} required className={inputClass} /></label>
            <label className="text-xs font-semibold">Comercio<select name="merchant" required defaultValue="" className={inputClass}><option value="" disabled>Elegí el comercio</option>{options.data?.merchants.map((name) => <option key={name}>{name}</option>)}</select></label>
            <label className="text-xs font-semibold">Monto original · ARS<input name="amount" type="number" min="0.01" max="1000000000" step="0.01" inputMode="decimal" required placeholder="Ej.: 50000" className={inputClass} /></label>
            <label className="text-xs font-semibold">Banco utilizado<select name="bank" defaultValue="" className={inputClass}><option value="">No informado / no aplica</option>{options.data?.banks.map((name) => <option key={name}>{name}</option>)}</select></label>
            <label className="text-xs font-semibold">Billetera utilizada<select name="wallet" defaultValue="" className={inputClass}><option value="">No informada / no aplica</option>{options.data?.wallets.map((name) => <option key={name}>{name}</option>)}</select></label>
            <label className="text-xs font-semibold">Tipo de pago<select name="card_type" defaultValue="unknown" className={inputClass}><option value="unknown">No informado</option><option value="credit">Crédito</option><option value="debit">Débito</option><option value="account">Dinero en cuenta</option><option value="cash">Efectivo</option></select></label>
            <label className="text-xs font-semibold">Modalidad<select name="modality" defaultValue="unknown" className={inputClass}><option value="unknown">No informada</option><option value="online">Online</option><option value="in_store">Presencial</option></select></label>
            <label className="text-xs font-semibold">Descuento/reintegro ya recibido · ARS<input name="received_discount" type="number" min="0" max="1000000000" step="0.01" inputMode="decimal" placeholder="Opcional; 0 si confirmás que no hubo" className={inputClass} /></label>
            <div className="flex items-end"><button type="submit" disabled={save.isPending || !options.data} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-accent px-5 text-sm font-semibold text-accent-foreground disabled:opacity-50">{save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ReceiptText className="h-4 w-4" />}Guardar y cruzar</button></div>
          </fieldset>
        </form>
      </section>}

      {(message || error) && <p role={error ? "alert" : "status"} className="rounded-xl border border-border bg-card p-4 text-sm">{error || message}</p>}
      <section className="rounded-2xl border border-border bg-card p-5"><form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); setPeriod({ date_from: String(form.get("from") || "") || undefined, date_to: String(form.get("to") || "") || undefined }); setPage(1) }} className="flex flex-wrap items-end gap-3"><label className="text-xs font-semibold">Desde<input aria-label="Desde" name="from" type="date" max={argentinaDay()} className={inputClass} /></label><label className="text-xs font-semibold">Hasta<input aria-label="Hasta" name="to" type="date" max={argentinaDay()} className={inputClass} /></label><button type="submit" className="min-h-11 rounded-lg border border-border px-4 text-sm font-semibold">Filtrar</button><button type="button" disabled={refresh.isPending} onClick={() => refresh.mutate()} className="ml-auto inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-primary disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${refresh.isPending ? "animate-spin" : ""}`} />Actualizar cruce</button></form><p className="mt-3 text-xs text-muted-foreground">Sin filtros: últimos 90 días. {data && `${quoteDate(data.from)} al ${quoteDate(data.to)}.`} El cruce no ejecuta un nuevo scrapeo.</p></section>
      {report.isFetching && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Revisando el histórico…</p>}
      {report.error && <p role="alert" className="text-sm text-destructive">{report.error.message} <button type="button" className="underline" onClick={() => report.refetch()}>Reintentar</button></p>}
      {summary && <>
        <section aria-label="Métricas de compras" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[{ label: "Compras registradas", value: summary.purchase_count, help: `${money(summary.total_amount)} de monto original` }, { label: "Compras en día de promo", value: summary.promo_day_count, help: `${share(summary.promo_day_share_pct)} de las ${summary.with_history_count} con histórico verificable` }, { label: "Sin histórico verificable", value: summary.without_history_count, help: "No cuentan como compras sin promoción" }, { label: "Ahorro recibido declarado", value: money(summary.declared_savings), help: `${summary.declared_savings_count} compras informadas · tasa efectiva ${share(summary.declared_effective_pct)}` }].map((item) => <article key={item.label} className="rounded-xl border border-border bg-card p-5"><p className="text-xs font-medium text-muted-foreground">{item.label}</p><p className="mt-2 text-3xl font-semibold tracking-tight">{item.value}</p><p className="mt-2 text-xs leading-relaxed text-muted-foreground">{item.help}</p></article>)}
        </section>
        <section className="grid gap-5 rounded-2xl border border-border bg-card p-5 sm:grid-cols-2 sm:p-6"><div><h2 className="display text-lg font-semibold">¿Qué porcentajes estaban publicados?</h2><p className="mt-2 text-xs leading-relaxed text-muted-foreground">Una compra se cuenta una sola vez. Si había porcentajes diferentes, se agrupa en “Varios porcentajes”; no se elige el mayor como si lo hubieras recibido.</p><p className="mt-3 text-sm">{summary.possible_payment_count} compras con coincidencia parcial del medio declarado.</p></div><div>{summary.by_published_percentage.length ? <table className="w-full text-sm"><caption className="sr-only">Compras por porcentaje publicado</caption><thead className="border-b border-border text-xs text-muted-foreground"><tr><th scope="col" className="pb-2 text-left">Porcentaje publicado</th><th scope="col" className="pb-2 text-right">Compras</th></tr></thead><tbody>{summary.by_published_percentage.map((row) => <tr key={row.label} className="border-b border-border last:border-0"><td className="py-2.5 font-medium">{row.label}</td><td className="py-2.5 text-right">{row.purchases}</td></tr>)}</tbody></table> : <p className="text-sm text-muted-foreground">Todavía no hay coincidencias verificables con una promo porcentual.</p>}</div></section>
      </>}

      <section aria-labelledby="purchases-heading"><h2 id="purchases-heading" className="display mb-4 text-2xl font-semibold">Tus compras y la evidencia</h2><div className="space-y-3">{data?.purchases.map((purchase) => <article key={purchase.id} className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="flex items-center gap-2 text-xs text-muted-foreground"><CalendarDays className="h-3.5 w-3.5" />{quoteDate(purchase.purchased_on)}</p><h3 className="mt-1 text-lg font-semibold">{purchase.merchant}</h3><p className="mt-1 text-xs text-muted-foreground">{[purchase.bank, purchase.wallet, { credit: "Crédito", debit: "Débito", account: "Dinero en cuenta", cash: "Efectivo", unknown: "Pago no informado" }[purchase.card_type], { online: "Online", in_store: "Presencial", unknown: "Modalidad no informada" }[purchase.modality]].filter(Boolean).join(" · ")}</p></div><div className="text-right"><p className="text-xl font-semibold">{money(purchase.amount)}</p><p className="mt-1 text-xs text-muted-foreground">{purchase.received_discount !== null ? `Recibido declarado: ${money(purchase.received_discount)}` : "Descuento recibido sin informar"}</p></div></div>
        <p className="mt-3 inline-flex rounded-lg bg-secondary px-3 py-1.5 text-xs font-semibold text-secondary-foreground">{purchaseStatus(purchase.history_status, purchase.has_percentage_promo)}</p>
        {purchase.promotions.length > 0 && <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold text-primary">Ver {purchase.promotion_count} beneficios observados y sus condiciones</summary><div className="mt-3 space-y-3">{purchase.promotions.map((promo) => <div key={promo.revision} className="rounded-lg border border-border p-3"><p className="font-semibold">{promo.discount || "Beneficio sin porcentaje"} · {promo.bank || promo.wallet || promo.title}</p><p className="mt-1 text-xs text-muted-foreground">{promo.title}</p><p className="mt-1 text-xs text-muted-foreground">{promo.evidence === "scrape" ? "Observación versionada" : "Snapshot recuperado: no verifica el pasado"} · {promo.payment_match === "possible" ? "Posible coincidencia del medio; falta validar requisitos" : promo.payment_match === "different" ? "No coincide con el medio o canal declarado" : "Faltan datos para cruzar el medio"}</p><p className="mt-2 text-xs">Tope: {promo.tope || "no informado"} · Mínimo: {promo.min_purchase || "no informado"} · Canal: {promo.store_types || "no informado"}</p><p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">Requisitos: {promo.requirements.join(" · ") || "No informados"}</p><p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">Exclusiones: {promo.exclusions.join(" · ") || "No informadas; no implica que no existan"}</p></div>)}{purchase.promotion_count > purchase.promotions.length && <p className="text-xs text-muted-foreground">Se muestran las primeras {purchase.promotions.length} coincidencias.</p>}</div></details>}
        <div className="mt-4 flex justify-end border-t border-border pt-3">{confirmDelete === purchase.id ? <div className="flex flex-wrap items-center gap-3 text-xs"><span>¿Eliminar esta compra de tus métricas?</span><button type="button" disabled={remove.isPending} onClick={() => remove.mutate(purchase.id)} className="font-semibold text-destructive">Sí, eliminar</button><button type="button" onClick={() => setConfirmDelete(null)} className="text-muted-foreground">Cancelar</button></div> : <button type="button" onClick={() => setConfirmDelete(purchase.id)} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"><Trash2 className="h-3.5 w-3.5" />Eliminar compra</button>}</div>
      </article>)}</div>
      {data && data.total === 0 && <div className="rounded-xl border border-dashed border-border p-8 text-center"><ReceiptText className="mx-auto h-8 w-8 text-muted-foreground" /><p className="mt-3 font-semibold">No hay compras registradas en este período</p><p className="mt-2 text-sm text-muted-foreground">“Registrar compra” carga consumos reales. Tu lista habitual no se considera una compra realizada.</p></div>}
      {data && data.total > data.page_size && <nav aria-label="Páginas de compras" className="mt-4 flex items-center justify-between text-sm"><button type="button" disabled={page === 1} onClick={() => setPage(page-1)} className="rounded-lg border border-border px-3 py-2 disabled:opacity-40">Anterior</button><span>{page} / {Math.ceil(data.total/data.page_size)}</span><button type="button" disabled={page*data.page_size >= data.total} onClick={() => setPage(page+1)} className="rounded-lg border border-border px-3 py-2 disabled:opacity-40">Siguiente</button></nav>}
      </section>
      {data && <details className="rounded-xl border border-border p-5 text-xs leading-relaxed text-muted-foreground"><summary className="cursor-pointer font-semibold text-foreground">Cómo interpretar esta métrica y qué datos faltan</summary><p className="mt-3">Observaciones versionadas disponibles: {data.history.first_day ? `${quoteDate(data.history.first_day)} al ${quoteDate(data.history.last_day || data.history.first_day)}` : "todavía no hay"}. La cobertura puede tener huecos por día y comercio.</p><ul className="mt-2 list-disc space-y-2 pl-4">{data.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>}
    </main>
  </div>
}
