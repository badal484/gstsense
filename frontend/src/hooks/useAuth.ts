"use client"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuthStore } from "@/store/authStore"
import { ROUTES } from "@/lib/constants"

export function useAuth(requireAuth = false) {
  const {
    user,
    organization,
    isAuthenticated,
    isLoading,
    error,
    login,
    logout,
    initialize,
    clearError,
  } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    const run = async () => {
      await initialize()
      if (requireAuth && !useAuthStore.getState().isAuthenticated) {
        router.replace(ROUTES.LOGIN)
      }
    }
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requireAuth])

  return {
    user,
    organization,
    isAuthenticated,
    isLoading,
    error,
    login,
    logout,
    clearError,
  }
}

export function useRequireAuth() {
  return useAuth(true)
}
