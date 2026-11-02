import test from 'node:test'
import assert from 'node:assert/strict'
import { runCameraSession } from '../lib/camera-session.ts'

const deferred = () => { let resolve; const promise = new Promise((done) => { resolve = done }); return { promise, resolve } }
const setup = () => {
  const abort = new AbortController()
  let stopped = 0
  const stream = { getTracks: () => [{ stop: () => { stopped++ } }] }
  return { abort, stream, stopped: () => stopped }
}

test('closing while permission is pending releases a subsequently granted camera', async () => {
  const state = setup(), permission = deferred()
  const task = runCameraSession({ signal: state.abort.signal, acquire: () => permission.promise,
    decode: async () => { assert.fail('must not start decoding after close') }, validate: () => true, onRead: () => assert.fail() })
  state.abort.abort()
  permission.resolve(state.stream)
  await task
  assert.equal(state.stopped(), 1)
})

test('closing during decoder setup stops tracks immediately and later decoder controls too', async () => {
  const state = setup(), ready = deferred(), entered = deferred()
  let decoderStopped = 0
  const task = runCameraSession({ signal: state.abort.signal, acquire: async () => state.stream,
    decode: async () => { entered.resolve(); return ready.promise }, validate: () => true, onRead: () => assert.fail() })
  await entered.promise
  state.abort.abort()
  assert.equal(state.stopped(), 1)
  ready.resolve(() => { decoderStopped++ })
  await task
  assert.equal(decoderStopped, 1)
})

test('valid result is emitted once, invalid QR payloads ignored, stream stops on success', async () => {
  const state = setup(), received = []
  let emit
  await runCameraSession({ signal: state.abort.signal, acquire: async () => state.stream,
    decode: async (_, onCode) => { emit = onCode; return () => {} }, validate: (code) => code === 'valid', onRead: (code) => received.push(code) })
  emit('https://unknown.test')
  emit('valid')
  emit('valid')
  assert.deepEqual(received, ['valid'])
  assert.equal(state.stopped(), 1)
})

test('permission denial is surfaced for manual-entry fallback', async () => {
  const state = setup()
  await assert.rejects(runCameraSession({ signal: state.abort.signal,
    acquire: async () => { throw new DOMException('Denied', 'NotAllowedError') },
    decode: async () => assert.fail(), validate: () => true, onRead: () => assert.fail() }), { name: 'NotAllowedError' })
  assert.equal(state.stopped(), 0)
})

test('closing an active camera stops both decoder and tracks', async () => {
  const state = setup()
  let decoderStopped = 0
  await runCameraSession({ signal: state.abort.signal, acquire: async () => state.stream,
    decode: async () => () => { decoderStopped++ }, validate: () => true, onRead: () => assert.fail() })
  state.abort.abort()
  assert.equal(decoderStopped, 1)
  assert.equal(state.stopped(), 1)
})
