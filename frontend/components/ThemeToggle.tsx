"use client"

import { Moon, Sun } from "lucide-react"

const THEME_KEY = "promoar-theme"

function setDarkMode(enabled: boolean) {
  const root = document.documentElement
  root.classList.toggle("dark", enabled)
  root.style.colorScheme = enabled ? "dark" : "light"
}

export function ThemeToggle() {
  function toggleTheme() {
    const next = !document.documentElement.classList.contains("dark")
    setDarkMode(next)
    window.localStorage.setItem(THEME_KEY, next ? "dark" : "light")
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="theme-toggle fixed bottom-5 left-5 z-40 grid h-11 w-11 place-items-center rounded-2xl border border-[#cbd8e6] bg-white text-[#102a4c] shadow-[0_12px_28px_rgb(16_42_76_/_0.16)] transition-all hover:-translate-y-0.5 hover:border-[#102a4c] focus-visible:outline-none sm:bottom-6 sm:left-6"
      aria-label="Cambiar entre modo claro y oscuro"
      title="Cambiar tema"
    >
      <Sun className="theme-toggle-sun hidden h-4 w-4" aria-hidden="true" />
      <Moon className="theme-toggle-moon h-4 w-4" aria-hidden="true" />
      <span className="sr-only">Cambiar entre modo claro y oscuro</span>
    </button>
  )
}
