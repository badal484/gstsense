import { create } from "zustand"
import type { ScanPreview, ScanReport, Scan } from "@/types"

interface ScanState {
  currentScanId: string | null
  currentStatus: string | null
  preview: ScanPreview | null
  report: ScanReport | null
  scanHistory: Scan[]
  isUploading: boolean
  isPolling: boolean
  uploadError: string | null
}

interface ScanActions {
  setCurrentScanId: (id: string) => void
  setStatus: (status: string) => void
  setPreview: (preview: ScanPreview) => void
  setReport: (report: ScanReport) => void
  setScanHistory: (scans: Scan[]) => void
  setUploading: (loading: boolean) => void
  setPolling: (polling: boolean) => void
  setUploadError: (error: string | null) => void
  reset: () => void
}

export const useScanStore = create<ScanState & ScanActions>((set) => ({
  currentScanId: null,
  currentStatus: null,
  preview: null,
  report: null,
  scanHistory: [],
  isUploading: false,
  isPolling: false,
  uploadError: null,

  setCurrentScanId: (id) => set({ currentScanId: id }),
  setStatus: (status) => set({ currentStatus: status }),
  setPreview: (preview) => set({ preview }),
  setReport: (report) => set({ report }),
  setScanHistory: (scans) => set({ scanHistory: scans }),
  setUploading: (isUploading) => set({ isUploading }),
  setPolling: (isPolling) => set({ isPolling }),
  setUploadError: (uploadError) => set({ uploadError }),
  reset: () =>
    set({
      currentScanId: null,
      currentStatus: null,
      preview: null,
      report: null,
      isUploading: false,
      isPolling: false,
      uploadError: null,
    }),
}))
