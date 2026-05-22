"use client"
import { useState, useCallback } from "react"
import { paymentApi } from "@/lib/api"

declare global {
  interface Window {
    Razorpay: new (options: RazorpayOptions) => RazorpayInstance
  }
}

interface RazorpayOptions {
  key: string
  amount: number
  currency: string
  name: string
  description: string
  order_id: string
  handler: (response: RazorpayPaymentResponse) => void
  prefill?: { email?: string; contact?: string }
  theme?: { color?: string }
  modal?: { ondismiss?: () => void }
}

interface RazorpayInstance {
  open: () => void
}

interface RazorpayPaymentResponse {
  razorpay_order_id: string
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

export function usePayment() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const initiatePayment = useCallback(
    async (
      scanId: string,
      userEmail: string,
      onSuccess: (scanId: string) => void,
      onFailure: (error: string) => void,
    ): Promise<void> => {
      setIsLoading(true)
      setError(null)

      try {
        const loaded = await loadRazorpayScript()
        if (!loaded) {
          const msg = "Failed to load payment gateway. Check your internet connection."
          setError(msg)
          onFailure(msg)
          return
        }

        const resp = await paymentApi.createOrder(scanId)
        const order = resp.data.data
        if (!order) throw new Error("Failed to create payment order")
        const envKey = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID
        const key = envKey || order.key_id
        if (!key) {
          const msg = "Razorpay key missing. Set NEXT_PUBLIC_RAZORPAY_KEY_ID in .env.local."
          setError(msg)
          onFailure(msg)
          setIsLoading(false)
          return
        }

        const rzp = new window.Razorpay({
          key,
          amount: order.amount,
          currency: "INR",
          name: "GSTSense",
          description: "GST Mismatch Report",
          order_id: order.order_id,
          handler: async (response: RazorpayPaymentResponse) => {
            try {
              const verifyResp = await paymentApi.verifyPayment({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
                scan_id: scanId,
              })
              if (verifyResp.data.data?.success) {
                setIsLoading(false)
                onSuccess(scanId)
              } else {
                const msg = "Payment verification failed. Contact support."
                setError(msg)
                onFailure(msg)
              }
            } catch (verifyErr) {
              const msg =
                verifyErr instanceof Error
                  ? verifyErr.message
                  : "Payment verification failed"
              setError(msg)
              setIsLoading(false)
              onFailure(msg)
            }
          },
          prefill: { email: userEmail },
          theme: { color: "#534AB7" },
          modal: {
            ondismiss: () => {
              setIsLoading(false)
            },
          },
        })

        rzp.open()
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Payment failed"
        setError(msg)
        setIsLoading(false)
        onFailure(msg)
      }
    },
    [],
  )

  return { initiatePayment, isLoading, error }
}
