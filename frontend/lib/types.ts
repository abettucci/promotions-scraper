export interface Promotion {
  id: number
  title: string
  discount: string | null
  bank: string | null
  wallet: string | null
  card_type: string | null
  payment_method: string | null
  store_types: string | null
  valid_days: string | null
  valid_from: string | null
  valid_until: string | null
  image_url: string | null
  tope: string | null
  acumulable: boolean | null
  is_active: boolean
  scraped_at: string
  supermarket_name: string
  exclusions: string[]
  requirements: string[]
  max_discount: string | null
  min_purchase: string | null
}

export interface PromotionsResponse {
  total: number
  page: number
  page_size: number
  pages: number
  data: Promotion[]
}

export interface TodayResponse {
  day: string
  total: number
  data: Promotion[]
}

export interface Bank {
  name: string
  count: number
}

export type Category = "supermarket" | "fuel"

export interface Supermarket {
  id: number
  name: string
  url: string
  category: Category
  last_scraped: string | null
  scrape_count: number
  active_promotions: number
}

export interface Stats {
  total_promotions: number
  total_banks: number
  total_supermarkets: number
  last_updated: string | null
  top_banks: { name: string; count: number }[]
  by_supermarket: { name: string; count: number }[]
}

export type PromotionState = "activa" | "proxima" | "finalizada"
export type Modality = "presencial" | "online"
export type DayCode = "lunes" | "martes" | "miércoles" | "jueves" | "viernes" | "sábado" | "domingo"

export interface FilterState {
  supermarket: string
  bank: string
  days: DayCode[]
  search: string
  discount_type: string
  state: PromotionState
  modality: Modality[]
  page: number
}

export interface PaymentMethod {
  name: string
  type: "bank" | "wallet" | "club"
}

export interface User {
  id: number
  email: string
  telegram_chat_id: string | null
  notify_daily: boolean
  notify_hour: number
  payment_methods: PaymentMethod[]
  created_at: string
}

export interface AuthResponse {
  token: string
  user: User
}

export interface PaymentMethodsCatalog {
  bank: string[]
  wallet: string[]
  club: string[]
}

export interface MyPromotionsResponse {
  total: number
  today_only: boolean
  by_supermarket: {
    supermarket: string
    promotions: Promotion[]
  }[]
}
