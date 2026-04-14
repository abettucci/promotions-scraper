"use client"

import { useState, useRef, useEffect } from "react"
import Link from "next/link"
import { useAuthStore } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { User, LogOut, Settings, ChevronDown, CreditCard } from "lucide-react"

export function UserMenu() {
  const { user, logout } = useAuthStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Cerrar al hacer click fuera
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/login">Iniciar sesión</Link>
        </Button>
        <Button size="sm" asChild>
          <Link href="/register">Registrarse</Link>
        </Button>
      </div>
    )
  }

  const initials = user.email.slice(0, 2).toUpperCase()
  const methodCount = user.payment_methods?.length ?? 0

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors"
      >
        <span className="flex items-center justify-center w-7 h-7 rounded-full bg-blue-600 text-white text-xs font-bold">
          {initials}
        </span>
        <span className="hidden sm:block max-w-[140px] truncate">{user.email}</span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-56 bg-white rounded-xl border border-slate-200 shadow-lg z-50 py-1 overflow-hidden">
          {/* User info */}
          <div className="px-4 py-3 border-b border-slate-100">
            <p className="text-xs text-slate-500">Conectado como</p>
            <p className="text-sm font-medium text-slate-800 truncate">{user.email}</p>
            {methodCount > 0 && (
              <p className="text-xs text-blue-600 mt-0.5 flex items-center gap-1">
                <CreditCard className="w-3 h-3" />
                {methodCount} método{methodCount !== 1 ? "s" : ""} configurado{methodCount !== 1 ? "s" : ""}
              </p>
            )}
          </div>

          {/* Links */}
          <Link
            href="/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Settings className="w-4 h-4 text-slate-400" />
            Mi perfil
          </Link>

          <Link
            href="/my-promotions"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <User className="w-4 h-4 text-slate-400" />
            Mis promociones
          </Link>

          <div className="border-t border-slate-100 mt-1">
            <button
              onClick={() => { logout(); setOpen(false) }}
              className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors w-full"
            >
              <LogOut className="w-4 h-4" />
              Cerrar sesión
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
