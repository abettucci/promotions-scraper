import type { Metadata } from "next"
import "./globals.css"
import { Providers } from "./providers"
import { AuthProvider } from "@/components/AuthProvider"
import { ThemeToggle } from "@/components/ThemeToggle"

export const metadata: Metadata = {
  title: "PromoAR — Promociones que valen la pena",
  description: "Promociones bancarias de supermercados y combustible, verificadas en un solo lugar.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try { const saved = localStorage.getItem('promoar-theme'); const dark = saved ? saved === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches; document.documentElement.classList.toggle('dark', dark); document.documentElement.style.colorScheme = dark ? 'dark' : 'light'; } catch (_) {}`,
          }}
        />
      </head>
      <body className="font-sans antialiased min-h-screen">
        <Providers>
          <AuthProvider>
            {children}
          </AuthProvider>
        </Providers>
        <ThemeToggle />
      </body>
    </html>
  )
}
