import test from 'node:test'
import assert from 'node:assert/strict'
import { bestQuote, groupWatchlistProducts, money, quoteDate } from '../lib/watchlist.ts'

test('groups products into distinct top-level categories and keeps uncategorized last', () => {
  const groups = groupWatchlistProducts([
    { id: 1, category_path: ['Bebidas', 'Vinos'] }, { id: 2, category: '/Almacén/Aderezos/' },
    { id: 3, category_path: ['Bebidas', 'Gaseosas'] }, { id: 4, category: '' },
  ])
  assert.deepEqual(groups.map((g) => [g.category, g.products.length]), [['Almacén', 1], ['Bebidas', 2], ['Otros', 1]])
})
test('zero and invalid prices never become a lowest quote; unknown is not free', () => {
  for (const price of [0, -1, NaN, Infinity]) assert.equal(bestQuote({ best_offer: { price } }), null)
  assert.equal(bestQuote({ baseline_price: 0 }), null)
  assert.equal(bestQuote({ best_offer: { price: 150 } }).price, 150)
})
test('monetary savings preserve cents and calendar dates do not shift to prior day', () => {
  assert.equal(money(1000.5), '$1.000,5')
  assert.equal(quoteDate('2026-11-01'), '01/11/2026')
})
