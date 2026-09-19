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
        className="flex min-h-9 items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium text-[#102a4c] transition-colors hover:bg-[#edf2f7]"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#102a4c] text-xs font-bold text-[#b8f36b]">
          {initials}
        </span>
        <span className="hidden sm:block max-w-[140px] truncate">{user.email}</span>
        <ChevronDown className="h-3.5 w-3.5 text-[#71839a]" />
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-xl border border-[#dbe4ee] bg-white py-1 shadow-[0_16px_40px_rgb(16_42_76_/_0.16)]">
          {/* User info */}
          <div className="border-b border-[#e5ebf2] px-4 py-3">
            <p className="text-xs text-[#71839a]">Conectado como</p>
            <p className="truncate text-sm font-medium text-[#102a4c]">{user.email}</p>
            {methodCount > 0 && (
              <p className="mt-0.5 flex items-center gap-1 text-xs text-[#2758d8]">
                <CreditCard className="w-3 h-3" />
                {methodCount} método{methodCount !== 1 ? "s" : ""} configurado{methodCount !== 1 ? "s" : ""}
              </p>
            )}
          </div>

          {/* Links */}
          <Link
            href="/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-[#40536b] transition-colors hover:bg-[#f5f8fc]"
          >
            <Settings className="h-4 w-4 text-[#71839a]" />
            Mi perfil
          </Link>

          <Link
            href="/my-promotions"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-[#40536b] transition-colors hover:bg-[#f5f8fc]"
          >
            <User className="h-4 w-4 text-[#71839a]" />
            Mis promociones
          </Link>

          <div className="mt-1 border-t border-[#e5ebf2]">
            <button
              onClick={() => { logout(); setOpen(false) }}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-[#a9362a] transition-colors hover:bg-[#fff3f2]"
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
