import type { Metadata } from "next"
import { Geist } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans" })

export const metadata: Metadata = {
  title: "PromoAR — Descuentos de supermercados",
  description: "Todas las promociones bancarias de supermercados argentinos en un solo lugar",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={`${geist.variable} font-sans antialiased bg-slate-50 min-h-screen`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
