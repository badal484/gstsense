import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { User, Organization } from "@/types"
import { authApi, tokenStorage } from "@/lib/api"

interface AuthState {
  user: User | null
  organization: Organization | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}

interface AuthActions {
  login: (email: string, password: string) => Promise<void>
  register: (full_name: string, email: string, password: string, gstin: string) => Promise<void>
  logout: () => Promise<void>
  setUserAndOrg: (user: User, org: Organization) => void
  initialize: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set) => ({
      user: null,
      organization: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      register: async (full_name: string, email: string, password: string, gstin: string) => {
        set({ isLoading: true, error: null })
        try {
          const resp = await authApi.register({ full_name, email, password, gstin })
          const data = resp.data.data
          if (!data) throw new Error("No data in register response")

          tokenStorage.setToken(data.tokens.access_token)
          tokenStorage.setRefreshToken(data.tokens.refresh_token)

          set({
            user: data.user.user,
            organization: data.user.organization,
            isAuthenticated: true,
            error: null,
          })
        } catch (err) {
          const message = err instanceof Error ? err.message : "Registration failed"
          set({ error: message })
          throw err
        } finally {
          set({ isLoading: false })
        }
      },

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const resp = await authApi.login(email, password)
          const data = resp.data.data
          if (!data) throw new Error("No data in login response")

          tokenStorage.setToken(data.tokens.access_token)
          tokenStorage.setRefreshToken(data.tokens.refresh_token)

          set({
            user: data.user.user,
            organization: data.user.organization,
            isAuthenticated: true,
            error: null,
          })
        } catch (err) {
          const message = err instanceof Error ? err.message : "Login failed"
          set({ error: message })
          throw err
        } finally {
          set({ isLoading: false })
        }
      },

      logout: async () => {
        try {
          await authApi.logout()
        } catch {
          // fire and forget
        }
        tokenStorage.clearAll()
        set({
          user: null,
          organization: null,
          isAuthenticated: false,
          error: null,
        })
        if (typeof window !== "undefined") {
          window.location.href = "/login"
        }
      },

      setUserAndOrg: (user: User, org: Organization) => {
        set({ user, organization: org, isAuthenticated: true })
      },

      initialize: async () => {
        const token = tokenStorage.getToken()
        if (!token) {
          set({ isAuthenticated: false, isLoading: false })
          return
        }
        set({ isLoading: true })
        try {
          const resp = await authApi.me()
          const data = resp.data.data
          if (!data) throw new Error("No user data")
          set({
            user: data.user,
            organization: data.organization,
            isAuthenticated: true,
          })
        } catch {
          tokenStorage.clearAll()
          set({ user: null, organization: null, isAuthenticated: false })
        } finally {
          set({ isLoading: false })
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: "gstsense-auth",
      partialize: (state) => ({
        user: state.user,
        organization: state.organization,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
)
