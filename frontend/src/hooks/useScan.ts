"use client"
import { useState, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"
import { scanApi } from "@/lib/api"
import { useScanStore } from "@/store/scanStore"
import { ROUTES, POLL_INTERVAL_MS } from "@/lib/constants"

export function useScanUpload() {
  const router = useRouter()
  const { setCurrentScanId, setStatus, setUploading, setUploadError } =
    useScanStore()

  const upload = useCallback(
    async (gstr1File: File, gstr3bFile: File): Promise<string> => {
      setUploading(true)
      setUploadError(null)
      try {
        const resp = await scanApi.upload(gstr1File, gstr3bFile)
        const scanId = resp.data.data?.scan_id
        if (!scanId) throw new Error("No scan ID returned")
        setCurrentScanId(scanId)
        setStatus("uploaded")
        router.push(`${ROUTES.SCAN_PROCESSING}?scan_id=${scanId}`)
        return scanId
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Upload failed. Please try again."
        setUploadError(message)
        throw err
      } finally {
        setUploading(false)
      }
    },
    [router, setCurrentScanId, setStatus, setUploading, setUploadError],
  )

  return { upload }
}

const MAX_POLLS = 200 // 200 × 3s = 10 minutes

export function useScanPolling() {
  const [isPolling, setIsPolling] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollCountRef = useRef(0)
  const { setStatus } = useScanStore()

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
    pollCountRef.current = 0
  }, [])

  const startPolling = useCallback(
    (
      scanId: string,
      onComplete: (status: string) => void,
      onError: (error: string) => void,
    ) => {
      setIsPolling(true)
      pollCountRef.current = 0

      const poll = async () => {
        pollCountRef.current += 1

        if (pollCountRef.current >= MAX_POLLS) {
          stopPolling()
          onError("Scan timed out. Please contact support.")
          return
        }

        try {
          const resp = await scanApi.getStatus(scanId)
          const status = resp.data.data?.status ?? ""
          setStatus(status)

          if (status === "completed") {
            stopPolling()
            onComplete("completed")
          } else if (status === "failed") {
            stopPolling()
            onError("Scan processing failed. Please check your files and try again.")
          }
        } catch {
          // transient network error — keep polling
        }
      }

      // Check immediately on mount so a completed scan redirects without waiting
      poll()
      intervalRef.current = setInterval(poll, POLL_INTERVAL_MS)
    },
    [setStatus, stopPolling],
  )

  return { startPolling, stopPolling, isPolling }
}
