"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { ScanBarcode, X } from "lucide-react"
import { validGtin } from "@/lib/barcode"
import { runCameraSession } from "@/lib/camera-session"

function Camera({ onRead }: { onRead: (value: string) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState("")
  useEffect(() => {
    const controller = new AbortController()
    const read = async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("unsupported")
        const { BrowserMultiFormatReader } = await import("@zxing/browser")
        await runCameraSession({
          signal: controller.signal,
          acquire: () => navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" } } }),
          decode: async (stream, onCode) => {
            if (!video.current) throw new Error("preview-closed")
            const controls = await new BrowserMultiFormatReader().decodeFromStream(stream, video.current,
              (result) => { if (result) onCode(result.getText()) })
            return () => controls.stop()
          },
          validate: validGtin, onRead,
        })
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof DOMException && err.name === "NotAllowedError"
          ? "No se habilitó la cámara. Podés permitirla en tu navegador o ingresar el código abajo."
          : "No pudimos abrir la cámara. Usá HTTPS y verificá que no esté ocupada, o ingresá el código abajo.")
      }
    }
    void read()
    const hide = () => { if (document.hidden) { controller.abort(); setError("La cámara se pausó al salir de la pestaña. Cerrá y volvé a abrir el escáner.") } }
    document.addEventListener("visibilitychange", hide)
    return () => { controller.abort(); document.removeEventListener("visibilitychange", hide) }
  }, [onRead])
  return <div className="space-y-2">
    <video ref={video} muted playsInline className="aspect-[4/3] w-full rounded-xl bg-black object-cover" aria-label="Vista previa de la cámara para leer el código" />
    <p role="status" className="text-sm text-muted-foreground">{error || "Apuntá al código de barras del envase. Buscamos coincidencias exactas, no productos parecidos."}</p>
  </div>
}

export function BarcodeScanner({ onRead }: { onRead: (value: string) => void }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState("")
  const [error, setError] = useState("")
  const dialog = useRef<HTMLDialogElement>(null)
  const callback = useRef(onRead)
  useEffect(() => { callback.current = onRead }, [onRead])
  // A stable callback prevents reopening the camera on unrelated parent renders.
  const accept = useCallback((code: string) => { setOpen(false); callback.current(code) }, [])
  useEffect(() => {
    if (open) dialog.current?.showModal()
    else dialog.current?.close()
  }, [open])
  return <>
    <button type="button" onClick={() => { setError(""); setOpen(true) }} className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/40 px-4 text-sm font-semibold text-white hover:bg-white/10">
      <ScanBarcode className="h-5 w-5" /> Escanear
    </button>
    <dialog ref={dialog} onClose={() => setOpen(false)} aria-labelledby="scan-title" className="m-auto w-[calc(100%_-_2rem)] max-w-lg rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-xl backdrop:bg-black/60">
      <header className="mb-4 flex items-center justify-between gap-4">
        <h2 id="scan-title" className="display text-xl font-semibold">Escaneá el producto</h2>
        <button type="button" onClick={() => setOpen(false)} aria-label="Cerrar escáner" className="rounded-lg p-2 hover:bg-secondary"><X className="h-5 w-5" /></button>
      </header>
      {open && <Camera onRead={accept} />}
      <p className="my-3 text-xs text-muted-foreground">La imagen se procesa en tu celular. No grabamos ni enviamos fotos; solo consultamos el número leído.</p>
      <form onSubmit={(event) => { event.preventDefault(); if (validGtin(value)) accept(value); else setError("Revisá el código completo: 8, 12, 13 o 14 dígitos, incluido el dígito verificador.") }} className="space-y-2">
        <label htmlFor="barcode-manual" className="text-sm font-medium">También podés escribir el código</label>
        <div className="flex gap-2"><input id="barcode-manual" value={value} onChange={(event) => setValue(event.target.value.replace(/[^0-9]/g, "").slice(0, 14))} inputMode="numeric" maxLength={14} className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2" />
          <button type="submit" className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground">Buscar</button></div>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      </form>
    </dialog>
  </>
}
