import type { PromotionsResponse, TodayResponse, Bank, Supermarket, Stats, Promotion } from "./types"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function fetchJSON<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(BASE_URL + path)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v))
      }
    })
  }
  const res = await fetch(url.toString(), { next: { revalidate: 300 } })
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  getPromotions: (params: {
    supermarket?: string
    bank?: string
    day?: string
    search?: string
    discount_type?: string
    active_today?: boolean
    page?: number
    page_size?: number
  }) => fetchJSON<PromotionsResponse>("/api/promotions", params as Record<string, string | number | boolean | undefined>),

  getPromotion: (id: number) => fetchJSON<Promotion>(`/api/promotions/${id}`),

  getTodayPromotions: () => fetchJSON<TodayResponse>("/api/promotions/today"),

  getBanks: () => fetchJSON<Bank[]>("/api/banks"),

  getSupermarkets: () => fetchJSON<Supermarket[]>("/api/supermarkets"),

  getStats: () => fetchJSON<Stats>("/api/stats"),
}
