/** Own the stream even if permission or decoder setup resolves after the dialog closes. */
export async function runCameraSession({ signal, acquire, decode, validate, onRead }: {
  signal: AbortSignal; acquire: () => Promise<MediaStream>
  decode: (stream: MediaStream, onCode: (text: string) => void) => Promise<() => void>
  validate: (text: string) => boolean; onRead: (text: string) => void
}): Promise<void> {
  let stream: MediaStream | undefined, stop: (() => void) | undefined, accepted = false
  const release = () => { const stopNow = stop; stop = undefined; stopNow?.(); stream?.getTracks().forEach((track) => track.stop()); stream = undefined }
  signal.addEventListener("abort", release, { once: true })
  try {
    if (signal.aborted) return
    stream = await acquire()
    if (signal.aborted) { release(); return }
    stop = await decode(stream, (code) => { if (signal.aborted || accepted || !validate(code)) return; accepted = true; release(); onRead(code) })
    if (signal.aborted || accepted) release()
  } catch (error) { release(); signal.removeEventListener("abort", release); if (!signal.aborted) throw error }
  finally { if (signal.aborted || accepted) signal.removeEventListener("abort", release) }
}
