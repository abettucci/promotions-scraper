"use client"

import { useState } from "react"
import Link from "next/link"
import { Bell, Check, Loader2 } from "lucide-react"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"
import type { PriceAlertCreated } from "@/lib/types"

const ars = (value: number) => `$${Math.round(value).toLocaleString("es-AR")}`

export function PriceAlertButton({ query, productKey }: { query: string; productKey: string }) {
  const { token } = useAuthStore()
  const [open, setOpen] = useState(false)
  const [target, setTarget] = useState("")
  const [state, setState] = useState<{ loading: boolean; error: string | null; created: PriceAlertCreated | null }>({
    loading: false, error: null, created: null,
  })

  if (!token) {
    return <Link href="/login" className="inline-flex items-center gap-1.5 text-xs font-bold text-[#2758d8] hover:text-[#102a4c]"><Bell className="h-3.5 w-3.5" /> Iniciá sesión para crear una alerta</Link>
  }
  if (state.created) {
    const { created } = state
    return (
      <p className="inline-flex flex-wrap items-center gap-1.5 text-xs text-[#3d6626]">
        <Check className="h-3.5 w-3.5" />
        Alerta creada: hoy el más barato es {ars(created.price)} en {created.store_name}.
        {created.target ? ` Te aviso al llegar a ${ars(created.target)}.` : " Te aviso ante cualquier baja."}
        {!created.telegram_linked && <> <Link href="/profile" className="font-bold underline">Vinculá Telegram</Link> para recibir el aviso.</>}
      </p>
    )
  }

  const submit = async () => {
    const parsed = target.trim() ? Number(target.replace(/\./g, "").replace(",", ".")) : undefined
    if (parsed !== undefined && (!Number.isFinite(parsed) || parsed <= 0)) {
      setState((prev) => ({ ...prev, error: "Ingresá un precio válido o dejalo vacío." }))
      return
    }
    setState({ loading: true, error: null, created: null })
    try {
      const created = await api.createPriceAlert({ query, key: productKey, target_price: parsed }, token)
      setState({ loading: false, error: null, created })
    } catch (error) {
      setState({ loading: false, error: (error as Error).message, created: null })
    }
  }

  if (!open) {
    return <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 text-xs font-bold text-[#2758d8] hover:text-[#102a4c]"><Bell className="h-3.5 w-3.5" /> Avisarme si baja</button>
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="sr-only" htmlFor={`target-${productKey}`}>Precio objetivo</label>
      <input
        id={`target-${productKey}`} value={target} onChange={(event) => setTarget(event.target.value)} inputMode="numeric"
        placeholder="Precio objetivo (opcional)"
        className="h-8 w-48 rounded-lg border border-[#cbd8e6] bg-white px-2.5 text-xs text-[#102a4c] focus:outline-none focus:ring-2 focus:ring-[#b8f36b]"
      />
      <button type="button" onClick={submit} disabled={state.loading} className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-[#102a4c] px-3 text-xs font-semibold text-white hover:bg-[#183b67] disabled:opacity-60">
        {state.loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Bell className="h-3.5 w-3.5" />} Crear alerta
      </button>
      {state.error && <span className="text-xs text-[#9c4138]">{state.error}</span>}
    </div>
  )
}
