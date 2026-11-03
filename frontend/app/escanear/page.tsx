"use client"

import { useState } from "react"
import Link from "next/link"
import { ArrowLeft, Barcode, Camera, ShieldCheck } from "lucide-react"
import { BarcodeScanner } from "@/components/BarcodeScanner"
import { BarcodePriceLookup } from "@/components/BarcodePriceLookup"

export default function EscanearPage() {
  const [ean, setEan] = useState("")
  return <div className="min-h-dvh bg-background text-foreground">
    <header className="sticky top-0 z-30 border-b border-border/80 bg-background/90 backdrop-blur-xl"><div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4 sm:px-6"><Link href="/" className="text-muted-foreground hover:text-foreground" aria-label="Volver a promociones"><ArrowLeft className="h-5 w-5" /></Link><span className="display font-semibold tracking-tight">PROMOAR</span><span className="text-muted-foreground">/ Escanear producto</span><Link href="/precios" className="ml-auto text-sm font-semibold text-primary">Comparar por nombre</Link></div></header>
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 sm:py-10">
      <section className="relative overflow-hidden rounded-[1.75rem] bg-[#102a4c] px-6 py-8 text-white sm:px-10 sm:py-11"><div className="pointer-events-none absolute -right-16 -top-20 h-72 w-72 rounded-full border border-[#b8f36b]/15 sm:h-96 sm:w-96" /><div className="relative max-w-2xl"><p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#b8f36b]"><Barcode className="h-4 w-4" /> Precio e historial por código</p><h1 className="display mt-4 text-3xl font-semibold leading-tight tracking-[-0.05em] sm:text-5xl">Escaneá antes de llevarlo.</h1><p className="mt-4 max-w-xl text-sm leading-relaxed text-[#d9e3ef] sm:text-base">Leemos el EAN del envase y buscamos ese mismo producto en supermercados. Compará precios publicados y el historial observado.</p><div className="mt-6 flex flex-wrap items-center gap-3"><BarcodeScanner onRead={setEan} /><span className="text-xs text-[#d9e3ef]">También podés ingresar el código manualmente.</span></div></div></section>
      <div className="flex items-start gap-3 rounded-2xl border border-border bg-card p-4 text-card-foreground"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" /><p className="text-sm leading-relaxed text-muted-foreground"><b className="text-foreground">Privacidad y precisión.</b> La cámara se procesa en el dispositivo. Solo enviamos el número EAN. Una coincidencia exige el mismo código; si una tienda no publica ese producto, no mostramos uno parecido.</p></div>
      {ean ? <BarcodePriceLookup ean={ean} /> : <section className="grid gap-4 rounded-2xl border border-dashed border-border bg-card/60 p-6 text-card-foreground sm:grid-cols-[auto_1fr] sm:items-center sm:p-8"><span className="grid h-14 w-14 place-items-center rounded-2xl bg-secondary text-primary"><Camera className="h-7 w-7" /></span><div><h2 className="font-semibold">Apuntá al código de barras del producto</h2><p className="mt-1 text-sm text-muted-foreground">Usá la cámara trasera, acercá el envase y mantenelo dentro del recuadro. Si el código está dañado, escribilo desde “Escanear”.</p></div></section>}
    </main>
  </div>
}
