export type UserRole = "smb" | "growth" | "ca_firm" | "admin"
export type Plan = "free" | "smb" | "growth" | "ca_firm"
export type SubscriptionStatus =
  | "active"
  | "cancelled"
  | "past_due"
  | "trialing"
  | "inactive"
export type ScanStatus = "uploaded" | "processing" | "completed" | "failed"
export type MismatchType =
  | "missing_in_3b"
  | "missing_in_1"
  | "value_mismatch"
  | "tax_mismatch"
export type PaymentStatus = "created" | "paid" | "failed" | "refunded"

export interface User {
  id: string
  email: string
  full_name: string
  phone: string | null
  account_type: UserRole
  is_active: boolean
  is_verified: boolean
  created_at: string
}

export interface Organization {
  id: string
  business_name: string
  gstin: string
  state_code: string
  plan: Plan
  subscription_status: SubscriptionStatus
  invoice_limit: number
  invoices_used_this_month: number
  has_active_subscription: boolean
  is_invoice_limit_reached: boolean
  billing_cycle_start: string | null
  billing_cycle_end: string | null
}

export interface Mismatch {
  id: string
  invoice_number: string
  supplier_gstin: string
  supplier_name: string | null
  mismatch_type: MismatchType
  gstr1_taxable_value: string
  gstr3b_taxable_value: string
  gstr1_tax_amount: string
  gstr3b_tax_amount: string
  rupee_difference: string
  ai_explanation: string | null
}

export interface Scan {
  id: string
  scan_month: string
  status: ScanStatus
  total_invoices_scanned: number
  total_mismatches: number
  total_rupee_risk: string
  is_paid: boolean
  created_at: string
  completed_at: string | null
  processing_duration_seconds: number | null
  error_message: string | null
}

export interface ScanPreview {
  scan_id: string
  total_mismatches: number
  total_rupee_risk: string
  is_paid: boolean
  scan_month: string
  total_invoices_scanned: number
  preview_mismatches: Mismatch[]
}

export interface ScanReport {
  scan_id: string
  scan_month: string
  total_invoices_scanned: number
  total_mismatches: number
  total_rupee_risk: string
  total_unique_suppliers: number
  mismatches: Mismatch[]
  created_at: string
  warnings: string[]
}

export interface UsageStats {
  total_scans: number
  total_mismatches_found: number
  total_rupee_risk_found: string
  scans_this_month: number
  invoices_used_this_month: number
  invoice_limit: number
}

export interface RazorpayOrder {
  order_id: string
  amount: number
  amount_rupees: string
  currency: string
  key_id: string
  scan_id: string
}

export interface ApiResponse<T> {
  status: "success" | "error"
  data?: T
  error?: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface AuthResponse {
  tokens: AuthTokens
  user: {
    user: User
    organization: Organization
  }
}

export interface ScanListResponse {
  scans: Scan[]
  total: number
  page: number
  limit: number
}
