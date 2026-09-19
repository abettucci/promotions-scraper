import type { Metadata } from "next"
import "./globals.css"
import { Providers } from "./providers"
import { AuthProvider } from "@/components/AuthProvider"

export const metadata: Metadata = {
  title: "PromoAR — Promociones que valen la pena",
  description: "Promociones bancarias de supermercados y combustible, verificadas en un solo lugar.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="font-sans antialiased min-h-screen">
        <Providers>
          <AuthProvider>
            {children}
          </AuthProvider>
        </Providers>
      </body>
    </html>
  )
}
