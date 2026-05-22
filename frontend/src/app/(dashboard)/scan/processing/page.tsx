"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FileSpreadsheet, Loader2, AlertCircle } from "lucide-react";
import { useScanPolling } from "@/hooks/useScan";
import { useScanStore } from "@/store/scanStore";
import { ROUTES } from "@/lib/constants";

const STATUS_MESSAGES = [
  "Validating file format and GSTIN patterns...",
  "Parsing GSTR-1 invoices...",
  "Parsing GSTR-3B entries...",
  "Building invoice lookup tables...",
  "Matching invoices by GSTIN and invoice number...",
  "Detecting missing entries in GSTR-3B...",
  "Detecting missing entries in GSTR-1...",
  "Computing value mismatches...",
  "Computing tax mismatches...",
  "Calculating total rupee risk...",
  "Generating AI explanations...",
  "Preparing your report...",
];

export default function ProcessingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentScanId } = useScanStore();

  // Prefer URL param over store so page survives refresh
  const scanId = searchParams.get("scan_id") ?? currentScanId;

  const [messageIndex, setMessageIndex] = useState(0);
  const [failed, setFailed] = useState(false);
  const [failReason, setFailReason] = useState<string | null>(null);
  const { startPolling, stopPolling } = useScanPolling();
  const pollingStarted = useRef(false);

  useEffect(() => {
    if (!scanId) {
      router.push(ROUTES.SCAN + "?expired=1");
      return;
    }
    if (pollingStarted.current) return;
    pollingStarted.current = true;

    startPolling(
      scanId,
      () => router.push(`${ROUTES.SCAN_PREVIEW}?scan_id=${scanId}`),
      (err) => {
        setFailed(true);
        setFailReason(err);
      },
    );

    return () => {
    pollingStarted.current = false; // reset so StrictMode remount can restart polling
    stopPolling();
  };
  }, [scanId, router, startPolling, stopPolling]);

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((i) => (i + 1) % STATUS_MESSAGES.length);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="max-w-lg mx-auto flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-12 w-full">
        {failed ? (
          <>
            <div className="w-16 h-16 bg-red-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <AlertCircle className="w-9 h-9 text-red-500" />
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Processing Failed</h2>
            <p className="text-gray-500 text-sm mb-6">
              {failReason ?? "Something went wrong while processing your files. Please try again."}
            </p>
            <button
              onClick={() => router.push(ROUTES.SCAN)}
              className="bg-blue-700 text-white font-semibold px-6 py-3 rounded-xl hover:bg-blue-800 transition-colors"
            >
              Try Again
            </button>
          </>
        ) : (
          <>
            <div className="relative w-16 h-16 mx-auto mb-6">
              <div className="absolute inset-0 bg-blue-100 rounded-2xl" />
              <div className="absolute inset-0 flex items-center justify-center">
                <FileSpreadsheet className="w-8 h-8 text-blue-700" />
              </div>
              <div className="absolute -inset-1 rounded-2xl border-4 border-blue-200 border-t-blue-700 animate-spin" />
            </div>

            <h2 className="text-xl font-bold text-gray-900 mb-2">Analysing Your Returns</h2>
            <p className="text-gray-500 text-sm mb-6">
              Our AI is comparing your GSTR-1 and GSTR-3B line by line.
              This takes about 30–60 seconds.
            </p>

            <div className="bg-gray-50 rounded-xl border border-gray-100 px-5 py-3 min-h-[48px] flex items-center justify-center">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Loader2 className="w-4 h-4 animate-spin text-blue-600 shrink-0" />
                <span>{STATUS_MESSAGES[messageIndex]}</span>
              </div>
            </div>

            <div className="mt-6 w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-blue-700 h-full rounded-full transition-all duration-[3500ms] ease-linear"
                style={{ width: `${((messageIndex + 1) / STATUS_MESSAGES.length) * 100}%` }}
              />
            </div>
          </>
        )}
      </div>

      <p className="text-xs text-gray-400 mt-4">
        Please keep this page open while we process your files.
      </p>
    </div>
  );
}
