import test from "node:test"
import assert from "node:assert/strict"
import { argentinaDay, purchaseStatus, share } from "../lib/purchases.ts"

test("purchase day uses Argentina calendar rather than UTC date", () => {
  assert.equal(argentinaDay(new Date("2026-11-02T01:00:00Z")), "2026-11-01")
  assert.equal(argentinaDay(new Date("2026-11-02T04:00:00Z")), "2026-11-02")
})
test("unknown coverage is not displayed as zero or no promotion", () => {
  assert.equal(share(null), "Sin datos")
  assert.equal(share(0), "0%")
  assert.equal(purchaseStatus("insufficient", false), "Sin histórico verificable")
  assert.equal(purchaseStatus("observed", false), "Sin porcentaje registrado ese día")
  assert.equal(purchaseStatus("observed", true), "Día con promo publicada")
})
