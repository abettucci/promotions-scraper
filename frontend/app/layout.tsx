import type { Metadata } from "next"
import { Newsreader, Public_Sans } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"
import { AuthProvider } from "@/components/AuthProvider"

const newsreader = Newsreader({ subsets: ["latin"], variable: "--font-newsreader" })
const publicSans = Public_Sans({ subsets: ["latin"], variable: "--font-public-sans" })

export const metadata: Metadata = {
  title: "PromoAR — Descuentos de supermercados",
  description: "Todas las promociones bancarias de supermercados argentinos en un solo lugar",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={`${newsreader.variable} ${publicSans.variable} font-sans antialiased min-h-screen`}>
        <Providers>
          <AuthProvider>
            {children}
          </AuthProvider>
        </Providers>
      </body>
    </html>
  )
}
