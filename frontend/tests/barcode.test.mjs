import test from 'node:test'
import assert from 'node:assert/strict'
import { validGtin } from '../lib/barcode.ts'

test('GTIN supports leading zeroes, EAN-8, EAN-13 and UPC without network calls', () => {
  for (const code of ['4006381333931', '04006381333931', '036000291452', '96385074']) assert.ok(validGtin(code), code)
})
test('GTIN rejects invalid checksum, URL/QR payloads, empty and all-zero identifiers', () => {
  for (const code of ['4006381333932', '', '00000000', 'https://example.test/', '１２３４５６７８']) assert.ok(!validGtin(code), code)
})
