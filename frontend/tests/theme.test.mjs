import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const css = read('app/globals.css')
const page = read('app/my-promotions/page.tsx')

function luminance(hex) {
  return hex.match(/\w\w/g).map((pair) => parseInt(pair, 16) / 255)
    .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    .reduce((total, value, index) => total + value * [0.2126, 0.7152, 0.0722][index], 0)
}

test('dark semantic text pairs meet WCAG AA normal-text contrast', () => {
  const tokens = Object.fromEntries([...css.match(/\.dark \{([\s\S]*?)\}/)[1]
    .matchAll(/--([\w-]+): #([0-9a-f]{6});/g)].map((match) => [match[1], match[2]]))
  for (const [bg, fg] of [['background', 'foreground'], ['card', 'card-foreground'],
    ['secondary', 'secondary-foreground'], ['muted', 'muted-foreground'], ['accent', 'accent-foreground']]) {
    const values = [luminance(tokens[bg]), luminance(tokens[fg])].sort((a, b) => b - a)
    assert.ok((values[0] + 0.05) / (values[1] + 0.05) >= 4.5, `${bg}/${fg}`)
  }
})

test('personal promotions pair semantic background and foreground', () => {
  assert.ok(page.includes('min-h-screen bg-background text-foreground'))
  assert.ok(page.includes('tracking-tight text-foreground'))
  assert.ok(!page.includes('xl:grid-cols-4'))
  assert.ok(css.includes('white-space: normal;'))
})

test('habitual list has a labelled main navigation entry, also visible on mobile', () => {
  const home = read('app/page.tsx')
  const nav = home.match(/<nav[\s\S]*?<\/nav>/)[0]
  assert.ok(nav.includes('href="/watchlist"'))
  assert.ok(nav.includes('<span>Lista habitual</span>'))
  assert.ok(home.includes('Armá tu lista de súper habitual'))
})
