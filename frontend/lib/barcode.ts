/** GTIN checksum, including EAN-8/13 and UPC-A. Never strip zeroes before validation. */
export function validGtin(value: string): boolean {
  if (![8, 12, 13, 14].includes(value.length) || !/^[0-9]+$/.test(value) || /^0+$/.test(value)) return false
  const sum = [...value.slice(0, -1)].reverse().reduce((total, digit, index) => total + Number(digit) * (index % 2 === 0 ? 3 : 1), 0)
  return (10 - sum % 10) % 10 === Number(value.at(-1))
}
