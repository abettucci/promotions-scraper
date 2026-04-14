"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { User, PaymentMethod } from "./types"

interface AuthState {
  user: User | null
  token: string | null
  setAuth: (token: string, user: User) => void
  setUser: (user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      setAuth: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null }),
    }),
    {
      name: "promoar-auth",
      // Solo persistir el token; el user se recarga desde la API al iniciar
      partialize: (state) => ({ token: state.token }),
    }
  )
)
