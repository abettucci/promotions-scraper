import type {
  PromotionsResponse, TodayResponse, Bank, Supermarket, Stats, Promotion,
  User, AuthResponse, PaymentMethod, PaymentMethodsCatalog, MyPromotionsResponse,
} from "./types"

const API_BASE = typeof window !== "undefined" ? window.location.origin : "http://localhost:3000"

// ── GET helper ────────────────────────────────────────────────────────────────
async function fetchJSON<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
  token?: string | null,
): Promise<T> {
  const url = new URL(path, API_BASE)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v))
    })
  }
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch(url.toString(), { cache: "no-store", headers })
  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try { detail = JSON.parse(text)?.detail ?? text } catch {}
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

// ── POST / PUT helper ─────────────────────────────────────────────────────────
async function fetchMutation<T>(
  method: "POST" | "PUT",
  path: string,
  body: unknown,
  token?: string | null,
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
  const res = await fetch(new URL(path, API_BASE).toString(), {
    method,
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try { detail = JSON.parse(text)?.detail ?? text } catch {}
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  // ── Public endpoints ────────────────────────────────────────────────────────
  getPromotions: (params: {
    supermarket?: string; bank?: string; day?: string; search?: string
    discount_type?: string; active_today?: boolean; category?: string
    state?: string; modality?: string
    page?: number; page_size?: number
  }) => fetchJSON<PromotionsResponse>("/api/promotions", params as Record<string, string | number | boolean | undefined>),

  getPromotion: (id: number) => fetchJSON<Promotion>(`/api/promotions/${id}`),
  getTodayPromotions: () => fetchJSON<TodayResponse>("/api/promotions/today"),
  getBanks: (filters?: {
    supermarket?: string; day?: string; category?: string
    discount_type?: string; state?: string; modality?: string
  }) => fetchJSON<Bank[]>("/api/banks", filters as Record<string, string | undefined>),
  getSupermarkets: (category?: string) =>
    fetchJSON<Supermarket[]>("/api/supermarkets", category ? { category } : undefined),
  getStats: () => fetchJSON<Stats>("/api/stats"),
  getPaymentMethodsCatalog: () => fetchJSON<PaymentMethodsCatalog>("/api/catalog/payment-methods"),

  // ── Auth ────────────────────────────────────────────────────────────────────
  register: (email: string, password: string) =>
    fetchMutation<AuthResponse>("POST", "/api/auth/register", { email, password }),

  login: (email: string, password: string) =>
    fetchMutation<AuthResponse>("POST", "/api/auth/login", { email, password }),

  forgotPassword: (email: string) =>
    fetchMutation<{ ok: boolean }>("POST", "/api/auth/forgot-password", { email }),

  resetPassword: (token: string, new_password: string) =>
    fetchMutation<{ ok: boolean }>("POST", "/api/auth/reset-password", { token, new_password }),

  getMe: (token: string) => fetchJSON<User>("/api/auth/me", undefined, token),

  updateProfile: (token: string, data: { telegram_chat_id?: string; notify_daily?: boolean; notify_hour?: number }) =>
    fetchMutation<User>("PUT", "/api/auth/me", data, token),

  updatePaymentMethods: (token: string, methods: PaymentMethod[]) =>
    fetchMutation<User>("PUT", "/api/auth/me/payment-methods", { methods }, token),

  getMyPromotions: (token: string, today_only = true) =>
    fetchJSON<MyPromotionsResponse>("/api/auth/me/promotions", { today_only }, token),
}
