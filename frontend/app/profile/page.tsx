"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/auth"
import { PaymentMethodSelector } from "@/components/PaymentMethodSelector"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { PaymentMethod } from "@/lib/types"
import {
  ArrowLeft, Save, Loader2, CheckCircle2, AlertCircle,
  Bell, BellOff, MessageCircle, CreditCard,
} from "lucide-react"

export default function ProfilePage() {
  const router = useRouter()
  const { user, token, setUser, logout } = useAuthStore()
  const qc = useQueryClient()

  // Redirect if not logged in
  useEffect(() => {
    if (!token) router.push("/login")
  }, [token, router])

  // Catalog of available payment methods
  const { data: catalog } = useQuery({
    queryKey: ["catalog"],
    queryFn: api.getPaymentMethodsCatalog,
    enabled: !!token,
  })

  const [selectedMethods, setSelectedMethods] = useState<PaymentMethod[]>(() => user?.payment_methods ?? [])
  const [telegramChatId, setTelegramChatId] = useState(user?.telegram_chat_id ?? "")
  const [notifyDaily, setNotifyDaily] = useState(user?.notify_daily ?? true)
  const [notifyHour, setNotifyHour] = useState(user?.notify_hour ?? 9)
  const [successMsg, setSuccessMsg] = useState("")
  const [errorMsg, setErrorMsg] = useState("")

  // Sync state when user loads
  useEffect(() => {
    if (user) {
      setSelectedMethods(user.payment_methods ?? [])
      setTelegramChatId(user.telegram_chat_id ?? "")
      setNotifyDaily(user.notify_daily)
      setNotifyHour(user.notify_hour)
    }
  }, [user?.id])

  const saveMethods = useMutation({
    mutationFn: () => api.updatePaymentMethods(token!, selectedMethods),
    onSuccess: (updated) => { setUser(updated); flash("✅ Métodos de pago guardados") },
    onError: (e: Error) => setErrorMsg(e.message),
  })

  const saveTelegram = useMutation({
    mutationFn: () => api.updateProfile(token!, {
      telegram_chat_id: telegramChatId.trim() || undefined,
      notify_daily: notifyDaily,
      notify_hour: notifyHour,
    }),
    onSuccess: (updated) => { setUser(updated); flash("✅ Configuración de Telegram guardada") },
    onError: (e: Error) => setErrorMsg(e.message),
  })

  function flash(msg: string) {
    setSuccessMsg(msg)
    setErrorMsg("")
    setTimeout(() => setSuccessMsg(""), 3000)
  }

  if (!token || !user) return null

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-sm">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-slate-400 hover:text-slate-600 transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <span className="text-xl font-black text-slate-900 tracking-tight">PromoAR</span>
            <span className="text-slate-300">/</span>
            <span className="text-sm text-slate-500">Mi perfil</span>
          </div>
          <button onClick={logout} className="text-xs text-red-500 hover:text-red-700 transition-colors">
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        {/* Feedback messages */}
        {successMsg && (
          <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-sm">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            {successMsg}
          </div>
        )}
        {errorMsg && (
          <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {errorMsg}
          </div>
        )}

        {/* Account info */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Cuenta</h2>
          <p className="text-slate-800 font-medium">{user.email}</p>
          <p className="text-xs text-slate-400 mt-1">
            Miembro desde {new Date(user.created_at).toLocaleDateString("es-AR", { year: "numeric", month: "long" })}
          </p>
        </div>

        {/* Payment methods */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-blue-600" />
              <h2 className="text-base font-semibold text-slate-800">Mis tarjetas y billeteras</h2>
            </div>
            <span className="text-xs text-slate-400 bg-slate-100 px-2.5 py-1 rounded-full">
              {selectedMethods.length} seleccionado{selectedMethods.length !== 1 ? "s" : ""}
            </span>
          </div>

          <p className="text-sm text-slate-500 mb-5">
            Seleccioná los bancos, billeteras y clubes que tenés. Filtraremos las promos que aplican para vos.
          </p>

          {catalog ? (
            <PaymentMethodSelector
              catalog={catalog}
              selected={selectedMethods}
              onChange={setSelectedMethods}
            />
          ) : (
            <div className="flex items-center gap-2 text-slate-400 text-sm py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Cargando catálogo...
            </div>
          )}

          <div className="flex items-center justify-between mt-6 pt-5 border-t border-slate-100">
            {selectedMethods.length > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setSelectedMethods([])}>
                Limpiar selección
              </Button>
            )}
            <Button
              className="ml-auto"
              onClick={() => saveMethods.mutate()}
              disabled={saveMethods.isPending}
            >
              {saveMethods.isPending
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Guardando...</>
                : <><Save className="w-4 h-4" /> Guardar métodos</>}
            </Button>
          </div>
        </div>

        {/* Telegram config */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center gap-2 mb-5">
            <MessageCircle className="w-5 h-5 text-blue-500" />
            <h2 className="text-base font-semibold text-slate-800">Notificaciones por Telegram</h2>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-sm text-blue-700 mb-5 space-y-1">
            <p className="font-medium">¿Cómo obtener tu Chat ID?</p>
            <ol className="list-decimal list-inside space-y-0.5 text-blue-600">
              <li>Abrí Telegram y buscá <strong>@userinfobot</strong></li>
              <li>Enviá cualquier mensaje</li>
              <li>Copiá el número que aparece en «Id»</li>
            </ol>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1.5">
                Chat ID de Telegram
              </label>
              <Input
                type="text"
                placeholder="ej: 123456789"
                value={telegramChatId}
                onChange={(e) => setTelegramChatId(e.target.value)}
              />
              <p className="text-xs text-slate-400 mt-1">
                También podés usar el ID de un grupo (número negativo)
              </p>
            </div>

            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
              <div className="flex items-center gap-2">
                {notifyDaily
                  ? <Bell className="w-4 h-4 text-emerald-600" />
                  : <BellOff className="w-4 h-4 text-slate-400" />}
                <span className="text-sm font-medium text-slate-700">Digest diario</span>
              </div>
              <button
                type="button"
                onClick={() => setNotifyDaily((v) => !v)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  notifyDaily ? "bg-emerald-500" : "bg-slate-300"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    notifyDaily ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            {notifyDaily && (
              <div>
                <label className="text-sm font-medium text-slate-700 block mb-1.5">
                  Hora de envío
                </label>
                <select
                  value={notifyHour}
                  onChange={(e) => setNotifyHour(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                >
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i}>
                      {String(i).padStart(2, "0")}:00 hs
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="flex justify-end mt-6 pt-5 border-t border-slate-100">
            <Button
              onClick={() => saveTelegram.mutate()}
              disabled={saveTelegram.isPending}
            >
              {saveTelegram.isPending
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Guardando...</>
                : <><Save className="w-4 h-4" /> Guardar Telegram</>}
            </Button>
          </div>
        </div>

        {/* Quick link */}
        {selectedMethods.length > 0 && (
          <div className="text-center pb-4">
            <Button variant="outline" asChild>
              <Link href="/my-promotions">Ver mis promociones de hoy →</Link>
            </Button>
          </div>
        )}
      </main>
    </div>
  )
}
