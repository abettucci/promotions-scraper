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
  url: string | null
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

export interface PromotionDetails extends Promotion {
  /** Texto legal capturado desde la fuente oficial de la promoción. */
  terms_raw: string | null
  raw_text: string | null
  payment_methods: string[]
  tc_valid_days: string[]
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
  by_category?: Record<string, number>
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

export interface AssistantResponse {
  answer: string
}

// ── Comparador de precios ────────────────────────────────────────────────────
export interface PriceOfferPromo {
  id: number | null
  title: string | null
  discount: string | null
  entity: string
  tope: string | null
  min_purchase: string | null
  valid_days: string | null
  store_types: string | null
  requires_min_purchase: boolean
}

export interface PriceOffer {
  store: string
  store_name: string
  merchant: string | null
  title: string
  price: number
  list_price: number | null
  percentage_off: number | null
  url: string
  brand: string
  ean: string
  in_stock: boolean
  image: string
  installments: number
  final_price: number | null
  savings: number
  promo: PriceOfferPromo | null
  multibuy: PriceMultiBuy | null
  qty: number
  total: number | null
  deal: "multibuy" | "bank" | null
  category: string
}

export interface PriceMultiBuy {
  label: string
  kind: string
  min_qty: number
  /** false: etiqueta orientativa de campaña ("hasta 2do al 70%"), sin precio calculado */
  exact: boolean
  max_units: number | null
  unit_at_min?: number
}

export interface PriceGroup {
  key: string
  name: string
  brand: string
  ean: string
  image: string
  category: string
  category_path: string[]
  store_count: number
  offers: PriceOffer[]
}

export interface PriceFacet {
  name: string
  count: number
  children: { name: string; count: number }[]
}

export interface PriceSuggestion {
  key: string
  name: string
  brand: string
  image: string
  category: string
  category_path: string[]
  stores: number
}

export interface PriceSuggestResponse {
  query: string
  suggestions: PriceSuggestion[]
  categories: { name: string; path: string[]; count: number }[]
}

export interface PriceSearchResponse {
  query: string
  day?: string
  qty?: number
  facets?: PriceFacet[]
  groups: PriceGroup[]
  failed_stores: string[]
}

export interface PricePoint { date: string; min: number; avg: number; max: number; stores: number }

export interface PriceHistoryResponse {
  key: string
  days: number
  tracked: boolean
  name?: string
  points: PricePoint[]
  current: { store: string; store_name: string; price: number; date: string }[]
  summary: { today: number; lowest: number; lowest_date: string; highest: number; change_pct: number } | null
}

export interface PriceAlert {
  id: number
  product_key: string
  product_name: string
  query: string
  target_price: number | null
  baseline_price: number
}

export interface PriceAlertCreated {
  id: number
  key: string
  name: string
  price: number
  store_name: string
  target: number | null
  telegram_linked: boolean
}
