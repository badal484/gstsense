import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios"
import { API_BASE_URL, API_ROUTES } from "./constants"
import type {
  ApiResponse,
  AuthResponse,
  AuthTokens,
  User,
  Organization,
  ScanPreview,
  ScanReport,
  ScanListResponse,
  RazorpayOrder,
  UsageStats,
} from "@/types"

const TOKEN_KEY = "gstsense_access_token"
const REFRESH_TOKEN_KEY = "gstsense_refresh_token"

export const tokenStorage = {
  getToken: (): string | null => {
    if (typeof window === "undefined") return null
    return localStorage.getItem(TOKEN_KEY)
  },
  setToken: (token: string): void => {
    localStorage.setItem(TOKEN_KEY, token)
    // Write cookie so Next.js middleware can gate dashboard routes
    document.cookie = `access_token=${token}; path=/; max-age=900; SameSite=Lax`
  },
  getRefreshToken: (): string | null => {
    if (typeof window === "undefined") return null
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  },
  setRefreshToken: (token: string): void => {
    localStorage.setItem(REFRESH_TOKEN_KEY, token)
  },
  clearAll: (): void => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    document.cookie = "access_token=; path=/; max-age=0; SameSite=Lax"
  },
}

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
})

let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token))
  refreshSubscribers = []
}

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStorage.getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    config.headers["X-Request-ID"] = crypto.randomUUID()
    return config
  },
  (error) => Promise.reject(error),
)

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config

    if (axios.isCancel(error)) {
      return Promise.reject(new Error("Request cancelled."))
    }

    if (error.code === "ECONNABORTED") {
      return Promise.reject(
        new Error("Request timed out. Check your connection and try again."),
      )
    }

    if (!error.response) {
      return Promise.reject(
        new Error("Network error. Check your internet connection."),
      )
    }

    if (error.response.status === 401 && !originalRequest._retry) {
      const refreshToken = tokenStorage.getRefreshToken()

      if (!refreshToken) {
        tokenStorage.clearAll()
        if (typeof window !== "undefined") {
          window.location.href = "/login"
        }
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((newToken: string) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            resolve(api(originalRequest))
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        // Use raw axios (not the api instance) to avoid re-entering this interceptor
        const resp = await axios.post<ApiResponse<AuthTokens>>(
          `${API_BASE_URL}${API_ROUTES.AUTH.REFRESH}`,
          { refresh_token: refreshToken },
          { headers: { "Content-Type": "application/json" } },
        )
        const tokens = resp.data.data
        if (!tokens) throw new Error("No tokens in refresh response")

        tokenStorage.setToken(tokens.access_token)
        tokenStorage.setRefreshToken(tokens.refresh_token)
        onRefreshed(tokens.access_token)

        originalRequest.headers.Authorization = `Bearer ${tokens.access_token}`
        return api(originalRequest)
      } catch {
        tokenStorage.clearAll()
        refreshSubscribers = []
        if (typeof window !== "undefined") {
          window.location.href = "/login"
        }
        return Promise.reject(error)
      } finally {
        isRefreshing = false
      }
    }

    const message =
      error.response?.data?.error?.message ||
      (error.response?.status >= 500
        ? "Something went wrong. Please try again."
        : error.message)

    return Promise.reject(new Error(message))
  },
)

export const authApi = {
  register: (data: {
    full_name: string
    email: string
    password: string
    gstin: string
  }): Promise<AxiosResponse<ApiResponse<AuthResponse>>> =>
    api.post(API_ROUTES.AUTH.REGISTER, data),

  login: (
    email: string,
    password: string,
  ): Promise<AxiosResponse<ApiResponse<AuthResponse>>> =>
    api.post(API_ROUTES.AUTH.LOGIN, { email, password }),

  refresh: (
    refresh_token: string,
  ): Promise<AxiosResponse<ApiResponse<AuthTokens>>> =>
    api.post(API_ROUTES.AUTH.REFRESH, { refresh_token }),

  logout: (): Promise<AxiosResponse<ApiResponse<{ message: string }>>> =>
    api.post(API_ROUTES.AUTH.LOGOUT),

  me: (): Promise<
    AxiosResponse<ApiResponse<{ user: User; organization: Organization }>>
  > => api.get(API_ROUTES.AUTH.ME),

  forgotPassword: (
    email: string,
  ): Promise<AxiosResponse<ApiResponse<{ message: string }>>> =>
    api.post(API_ROUTES.AUTH.FORGOT_PASSWORD, { email }),

  resetPassword: (
    token: string,
    new_password: string,
  ): Promise<AxiosResponse<ApiResponse<{ message: string }>>> =>
    api.post(API_ROUTES.AUTH.RESET_PASSWORD, { token, new_password }),
}

export const scanApi = {
  upload: (
    gstr1File: File,
    gstr3bFile: File,
    scanMonth?: string,
  ): Promise<AxiosResponse<ApiResponse<{ scan_id: string; status: string }>>> => {
    const form = new FormData()
    form.append("gstr1_file", gstr1File)
    form.append("gstr3b_file", gstr3bFile)
    if (scanMonth) form.append("scan_month", scanMonth)
    return api.post(API_ROUTES.SCANS.UPLOAD, form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000,
    })
  },

  getStatus: (
    scanId: string,
  ): Promise<AxiosResponse<ApiResponse<{ scan_id: string; status: string }>>> =>
    api.get(API_ROUTES.SCANS.STATUS(scanId)),

  getPreview: (
    scanId: string,
  ): Promise<AxiosResponse<ApiResponse<ScanPreview>>> =>
    api.get(API_ROUTES.SCANS.PREVIEW(scanId)),

  getReport: (
    scanId: string,
  ): Promise<AxiosResponse<ApiResponse<ScanReport>>> =>
    api.get(API_ROUTES.SCANS.REPORT(scanId)),

  downloadReport: async (scanId: string): Promise<{ download_url?: string }> => {
    const resp = await api.get<{ download_url?: string }>(
      API_ROUTES.SCANS.DOWNLOAD(scanId),
    )
    return resp.data
  },

  listScans: (
    page = 1,
    limit = 10,
  ): Promise<AxiosResponse<ApiResponse<ScanListResponse>>> =>
    api.get(API_ROUTES.SCANS.LIST, { params: { page, limit } }),
}

export const paymentApi = {
  createOrder: (
    scanId: string,
  ): Promise<AxiosResponse<ApiResponse<RazorpayOrder>>> =>
    api.post(API_ROUTES.PAYMENTS.CREATE_ORDER, { scan_id: scanId }),

  verifyPayment: (data: {
    razorpay_order_id: string
    razorpay_payment_id: string
    razorpay_signature: string
    scan_id: string
  }): Promise<
    AxiosResponse<ApiResponse<{ success: boolean; scan_id: string }>>
  > => api.post(API_ROUTES.PAYMENTS.VERIFY, data),
}

export const dashboardApi = {
  get: (): Promise<AxiosResponse<ApiResponse<unknown>>> =>
    api.get("/api/v1/dashboard/"),

  scoreHistory: (days = 30): Promise<AxiosResponse<ApiResponse<{ date: string; score: number; grade: string }[]>>> =>
    api.get(`/api/v1/dashboard/score-history?days=${days}`),
}

export const orgApi = {
  getMe: (): Promise<AxiosResponse<ApiResponse<Organization>>> =>
    api.get(API_ROUTES.ORGANIZATIONS.ME),

  getStats: (): Promise<AxiosResponse<ApiResponse<UsageStats>>> =>
    api.get(API_ROUTES.ORGANIZATIONS.STATS),
}

export const subscriptionApi = {
  create: (plan: string): Promise<AxiosResponse<ApiResponse<{
    id: string; plan: string; status: string;
    razorpay_subscription_id: string | null;
    razorpay_key_id: string | null;
    current_period_start: string; current_period_end: string;
    amount_paise: number;
  }>>> => api.post("/api/v1/subscriptions/create", { plan }),

  getCurrent: (): Promise<AxiosResponse<ApiResponse<null | {
    id: string; plan: string; status: string;
    razorpay_subscription_id: string | null;
    current_period_start: string; current_period_end: string;
  }>>> => api.get("/api/v1/subscriptions/current"),

  cancel: (): Promise<AxiosResponse<ApiResponse<{ message: string; access_until: string }>>> =>
    api.post("/api/v1/subscriptions/cancel"),

  verify: (data: {
    razorpay_subscription_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }): Promise<AxiosResponse<ApiResponse<{ success: boolean; plan: string; message: string }>>> =>
    api.post("/api/v1/subscriptions/verify", data),
}

export const userApi = {
  updateProfile: (data: {
    full_name?: string;
    phone?: string;
  }): Promise<AxiosResponse<ApiResponse<{ id: string; full_name: string; email: string }>>> =>
    api.patch("/api/v1/auth/me", data),

  changePassword: (data: {
    current_password: string;
    new_password: string;
  }): Promise<AxiosResponse<ApiResponse<{ message: string }>>> =>
    api.post("/api/v1/auth/change-password", data),

  deleteAccount: (
    confirmation: string,
  ): Promise<AxiosResponse<ApiResponse<{ message: string }>>> =>
    api.delete("/api/v1/auth/me", { data: { confirmation } }),

  getPreferences: (): Promise<AxiosResponse<ApiResponse<Record<string, boolean>>>> =>
    api.get("/api/v1/preferences/"),

  updatePreferences: (
    data: Record<string, boolean>,
  ): Promise<AxiosResponse<ApiResponse<Record<string, boolean>>>> =>
    api.patch("/api/v1/preferences/", data),
}

export default api
