"use client"
import { useState, useCallback } from "react"
import { subscriptionApi } from "@/lib/api"
import { useAuthStore } from "@/store/authStore"
import api from "@/lib/api"

interface RazorpaySubOptions {
  key: string
  subscription_id: string
  name: string
  description: string
  handler: (response: RazorpaySubResponse) => void
  prefill?: { email?: string }
  theme?: { color?: string }
  modal?: { ondismiss?: () => void }
}

interface RazorpaySubInstance {
  open: () => void
}

interface RazorpaySubResponse {
  razorpay_subscription_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window !== "undefined" && window.Razorpay) {
      resolve(true)
      return
    }
    const script = document.createElement("script")
    script.src = "https://checkout.razorpay.com/v1/checkout.js"
    script.onload = () => resolve(true)
    script.onerror = () => resolve(false)
    document.body.appendChild(script)
  })
}

export function useSubscriptionPayment() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { setUserAndOrg } = useAuthStore()

  const initiateSubscription = useCallback(
    async (
      plan: string,
      userEmail: string,
      planLabel: string,
      onSuccess: () => void,
      onFailure: (err: string) => void,
    ): Promise<void> => {
      setIsLoading(true)
      setError(null)

      try {
        const resp = await subscriptionApi.create(plan)
        const data = resp.data.data
        if (!data) throw new Error("Failed to initiate subscription")

        // Dev mode: Razorpay not configured — plan activated immediately by backend
        if (!data.razorpay_subscription_id || !data.razorpay_key_id) {
          const meResp = await api.get("/api/v1/auth/me")
          const { user: freshUser, organization: freshOrg } = meResp.data.data ?? {}
          if (freshUser && freshOrg) setUserAndOrg(freshUser, freshOrg)
          setIsLoading(false)
          onSuccess()
          return
        }

        // Production: open Razorpay subscription checkout
        const loaded = await loadRazorpayScript()
        if (!loaded) {
          throw new Error("Failed to load payment gateway. Check your internet connection.")
        }

        const RazorpayCtor = window.Razorpay as unknown as new (options: RazorpaySubOptions) => RazorpaySubInstance
        const rzp = new RazorpayCtor({
          key: data.razorpay_key_id,
          subscription_id: data.razorpay_subscription_id,
          name: "GSTSense",
          description: `${planLabel} — ₹${(data.amount_paise / 100).toLocaleString("en-IN")}/month`,
          handler: async (response: RazorpaySubResponse) => {
            try {
              await subscriptionApi.verify({
                razorpay_subscription_id: response.razorpay_subscription_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              })
              const meResp = await api.get("/api/v1/auth/me")
              const { user: freshUser, organization: freshOrg } = meResp.data.data ?? {}
              if (freshUser && freshOrg) setUserAndOrg(freshUser, freshOrg)
              setIsLoading(false)
              onSuccess()
            } catch (verifyErr) {
              const msg = verifyErr instanceof Error ? verifyErr.message : "Payment verification failed"
              setError(msg)
              setIsLoading(false)
              onFailure(msg)
            }
          },
          prefill: { email: userEmail },
          theme: { color: "#1d4ed8" },
          modal: {
            ondismiss: () => {
              setIsLoading(false)
            },
          },
        })

        rzp.open()
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Subscription failed"
        setError(msg)
        setIsLoading(false)
        onFailure(msg)
      }
    },
    [setUserAndOrg],
  )

  return { initiateSubscription, isLoading, error }
}
