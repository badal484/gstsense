export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export const API_ROUTES = {
  AUTH: {
    REGISTER: "/api/v1/auth/register",
    LOGIN: "/api/v1/auth/login",
    REFRESH: "/api/v1/auth/refresh",
    LOGOUT: "/api/v1/auth/logout",
    ME: "/api/v1/auth/me",
    FORGOT_PASSWORD: "/api/v1/auth/forgot-password",
    RESET_PASSWORD: "/api/v1/auth/reset-password",
  },
  SCANS: {
    UPLOAD: "/api/v1/scans/upload",
    STATUS: (id: string) => `/api/v1/scans/${id}/status`,
    PREVIEW: (id: string) => `/api/v1/scans/${id}/preview`,
    REPORT: (id: string) => `/api/v1/scans/${id}/report`,
    DOWNLOAD: (id: string) => `/api/v1/scans/${id}/download`,
    LIST: "/api/v1/scans/",
  },
  PAYMENTS: {
    CREATE_ORDER: "/api/v1/payments/create-order",
    VERIFY: "/api/v1/payments/verify",
    WEBHOOK: "/api/v1/payments/webhook",
  },
  ORGANIZATIONS: {
    ME: "/api/v1/organizations/me",
    STATS: "/api/v1/organizations/me/stats",
  },
  ITC: {
    UPLOAD: "/api/v1/itc/upload",
    SUMMARY: "/api/v1/itc/summary/latest",
    STATUS: (id: string) => `/api/v1/itc/${id}/status`,
    ANALYSIS: (id: string) => `/api/v1/itc/${id}/analysis`,
    LIST: "/api/v1/itc/",
  },
  NOTICES: {
    UPLOAD: "/api/v1/notices/upload",
    LIST: "/api/v1/notices/",
    DETAIL: (id: string) => `/api/v1/notices/${id}`,
    DRAFT: (id: string) => `/api/v1/notices/${id}/draft`,
    VERIFY: (id: string) => `/api/v1/notices/${id}/verify-credentials`,
    DOWNLOAD: (id: string) => `/api/v1/notices/${id}/download`,
    APPROVE: (id: string) => `/api/v1/notices/${id}/approve`,
    SHARE: (id: string) => `/api/v1/notices/${id}/share`,
  },
  DASHBOARD: "/api/v1/dashboard/",
  CA_FIRMS: {
    REGISTER: "/api/v1/ca-firms/",
    ME: "/api/v1/ca-firms/me",
    UPDATE: "/api/v1/ca-firms/me",
    DASHBOARD: "/api/v1/ca-firms/me/dashboard",
    REPORT: "/api/v1/ca-firms/me/report",
    CLIENTS: "/api/v1/ca-firms/clients",
    CLIENT: (orgId: string) => `/api/v1/ca-firms/clients/${orgId}`,
    COMMISSIONS: "/api/v1/ca-firms/commissions",
    COMMISSION_SUMMARY: "/api/v1/ca-firms/commissions/summary",
    MARK_PAID: (id: string) => `/api/v1/ca-firms/commissions/${id}/mark-paid`,
    BRANDING: (subdomain: string) => `/api/v1/ca-firms/branding/${subdomain}`,
  },
} as const

export const ROUTES = {
  HOME: "/",
  LOGIN: "/login",
  SIGNUP: "/signup",
  DASHBOARD: "/dashboard",
  SCAN: "/scan",
  SCAN_PROCESSING: "/scan/processing",
  SCAN_PREVIEW: "/scan/preview",
  SCAN_REPORT: (id: string) => `/scan/report/${id}`,
  ITC: "/itc",
  ITC_DETAIL: (id: string) => `/itc/${id}`,
  NOTICES: "/notices",
  NOTICE_DETAIL: (id: string) => `/notices/${id}`,
  CA: "/ca",
  CA_CLIENTS: "/ca/clients",
  CA_COMMISSIONS: "/ca/commissions",
  SETTINGS: "/settings",
} as const

export const PLAN_LIMITS = {
  free: { invoices: 500, label: "Free" },
  smb: { invoices: 1500, label: "SMB" },
  growth: { invoices: 5000, label: "Growth" },
  ca_firm: { invoices: 50000, label: "CA Firm" },
} as const

export const PLAN_PRICES = {
  smb: 999,
  growth: 2499,
  ca_firm: 9999,
} as const

export const ONE_TIME_SCAN_PRICE = 499

export const MISMATCH_TYPE_LABELS: Record<string, string> = {
  missing_in_3b: "Missing in GSTR-3B",
  missing_in_1: "Missing in GSTR-1",
  value_mismatch: "Value Mismatch",
  tax_mismatch: "Tax Mismatch",
}

export const MISMATCH_TYPE_COLORS: Record<string, string> = {
  missing_in_3b: "bg-red-100 text-red-800",
  missing_in_1: "bg-red-100 text-red-800",
  value_mismatch: "bg-amber-100 text-amber-800",
  tax_mismatch: "bg-amber-100 text-amber-800",
}

export const GST_DEADLINES = {
  GSTR1: 11,
  GSTR3B: 20,
}

export const POLL_INTERVAL_MS = 3000
export const MAX_FILE_SIZE_MB = 50
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
export const ACCEPTED_FILE_TYPES = {
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
}
