"use client"

import { Suspense, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react"

function ResetPasswordContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token") || ""

  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (password.length < 6) {
      setError("La contraseña debe tener al menos 6 caracteres")
      return
    }
    if (password !== confirm) {
      setError("Las contraseñas no coinciden")
      return
    }
    if (!token) {
      setError("Falta el token. Volvé a pedir el link de recuperación.")
      return
    }

    setLoading(true)
    try {
      await api.resetPassword(token, password)
      setSuccess(true)
      setTimeout(() => router.push("/login"), 2500)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al resetear la contraseña")
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="flex items-start gap-2 text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-3 text-sm">
        <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
        <div>
          Link inválido — falta el token. Pedí un nuevo link desde{" "}
          <Link href="/forgot-password" className="underline font-medium">
            recuperar contraseña
          </Link>.
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="flex items-start gap-2 text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-3 text-sm">
        <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
        <div>
          <p className="font-medium">Contraseña actualizada</p>
          <p className="text-emerald-600 mt-1">Te llevamos al login...</p>
        </div>
      </div>
    )
  }

  return (
    <>
      {error && (
        <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm mb-4">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-1.5">Nueva contraseña</label>
          <Input
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
            autoFocus
            minLength={6}
          />
        </div>
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-1.5">Confirmar contraseña</label>
          <Input
            type="password"
            placeholder="••••••••"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            autoComplete="new-password"
            minLength={6}
          />
        </div>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Guardando...</>
          ) : (
            "Cambiar contraseña"
          )}
        </Button>
      </form>
    </>
  )
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <Link href="/" className="text-xl font-black text-slate-900 tracking-tight">PromoAR</Link>
        </div>
      </header>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
            <h1 className="text-2xl font-bold text-slate-900 mb-1">Crear nueva contraseña</h1>
            <p className="text-sm text-slate-500 mb-6">
              Ingresá una nueva contraseña para tu cuenta.
            </p>

            <Suspense fallback={<div className="text-sm text-slate-400">Cargando...</div>}>
              <ResetPasswordContent />
            </Suspense>

            <p className="text-center text-sm text-slate-500 mt-6">
              <Link href="/login" className="text-blue-600 hover:underline">
                Volver al login
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
