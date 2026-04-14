"use client"

import { useEffect } from "react"
import { useAuthStore } from "@/lib/auth"
import { api } from "@/lib/api"

/**
 * Al montar, si hay token en localStorage lo verifica contra la API
 * y carga el perfil del usuario. Si el token expiró, hace logout.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { token, setUser, logout } = useAuthStore()

  useEffect(() => {
    if (!token) return
    api.getMe(token)
      .then((user) => setUser(user))
      .catch(() => logout())
  }, [token, setUser, logout])

  return <>{children}</>
}
