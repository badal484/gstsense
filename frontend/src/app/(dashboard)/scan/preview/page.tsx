"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Lock,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  Loader2,
  FileSpreadsheet,
  ArrowRight,
  IndianRupee,
} from "lucide-react";
import { scanApi } from "@/lib/api";
import { useScanStore } from "@/store/scanStore";
import { usePayment } from "@/hooks/usePayment";
import { useAuthStore } from "@/store/authStore";
import { ScanPreview, Mismatch } from "@/types";
import { ROUTES, MISMATCH_TYPE_LABELS, MISMATCH_TYPE_COLORS, ONE_TIME_SCAN_PRICE } from "@/lib/constants";
import { formatRupees, formatMonth, getRiskLevel } from "@/lib/utils";

function MismatchRow({ mismatch, locked }: { mismatch: Mismatch; locked: boolean }) {
  const typeLabel = MISMATCH_TYPE_LABELS[mismatch.mismatch_type] ?? mismatch.mismatch_type;
  const typeColor = MISMATCH_TYPE_COLORS[mismatch.mismatch_type] ?? "bg-gray-100 text-gray-600";
  const risk = getRiskLevel(mismatch.rupee_difference);

  return (
    <div className={`relative px-6 py-4 ${locked ? "select-none" : ""}`}>
      {locked && (
        <div className="absolute inset-0 backdrop-blur-[3px] bg-white/60 flex items-center justify-center z-10 rounded-xl">
          <Lock className="w-4 h-4 text-gray-400" />
        </div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${typeColor}`}>
              {typeLabel}
            </span>
            <span className="text-xs text-gray-400 font-mono">{mismatch.invoice_number}</span>
          </div>
          <div className="text-xs text-gray-500 font-mono truncate">{mismatch.supplier_gstin}</div>
          {mismatch.ai_explanation && !locked && (
            <p className="text-xs text-gray-600 mt-2 leading-relaxed">{mismatch.ai_explanation}</p>
          )}
        </div>
        <div className={`text-right shrink-0 font-bold ${risk.color}`}>
          {formatRupees(mismatch.rupee_difference)}
        </div>
      </div>
    </div>
  );
}

const LOCKED_PLACEHOLDER: Mismatch = {
  id: "locked",
  invoice_number: "INV-XXXX",
  supplier_gstin: "XXXXXXXXXXXX",
  supplier_name: null,
  mismatch_type: "value_mismatch",
  gstr1_taxable_value: "50000",
  gstr3b_taxable_value: "45000",
  gstr1_tax_amount: "9000",
  gstr3b_tax_amount: "8100",
  rupee_difference: "5000",
  ai_explanation: null,
};

export default function PreviewPage() {
  const router = useRouter();
  const { currentScanId } = useScanStore();
  const { user } = useAuthStore();
  const { initiatePayment, isLoading: paymentLoading } = usePayment();

  const [preview, setPreview] = useState<ScanPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [payError, setPayError] = useState<string | null>(null);

  useEffect(() => {
    if (!currentScanId) {
      router.push(ROUTES.SCAN);
      return;
    }
    scanApi
      .getPreview(currentScanId)
      .then((res) => {
        const data = res.data.data;
        if (data) setPreview(data);
      })
      .catch(() => router.push(ROUTES.SCAN))
      .finally(() => setLoading(false));
  }, [currentScanId, router]);

  async function handleUnlock() {
    if (!currentScanId || !user?.email) return;
    setPayError(null);
    await initiatePayment(
      currentScanId,
      user.email,
      () => router.push(ROUTES.SCAN_REPORT(currentScanId)),
      (err) => setPayError(err),
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
      </div>
    );
  }

  if (!preview) return null;

  const risk = getRiskLevel(preview.total_rupee_risk);
  const lockedCount = Math.max(0, preview.total_mismatches - preview.preview_mismatches.length);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Scan Results</h1>
        <p className="text-gray-500 text-sm mt-1">{formatMonth(preview.scan_month)}</p>
      </div>

      {/* Summary cards */}
      <div className="grid sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-2">
            <FileSpreadsheet className="w-5 h-5 text-gray-400" />
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Invoices Scanned</span>
          </div>
          <div className="text-3xl font-black text-gray-900">
            {preview.total_invoices_scanned.toLocaleString("en-IN")}
          </div>
        </div>

        <div className={`rounded-2xl border shadow-sm p-5 ${preview.total_mismatches === 0 ? "bg-green-50 border-green-200" : "bg-white border-gray-100"}`}>
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className={`w-5 h-5 ${preview.total_mismatches > 0 ? "text-orange-500" : "text-green-500"}`} />
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Mismatches Found</span>
          </div>
          <div className={`text-3xl font-black ${preview.total_mismatches === 0 ? "text-green-700" : "text-orange-600"}`}>
            {preview.total_mismatches}
          </div>
        </div>

        <div className={`rounded-2xl border shadow-sm p-5 ${risk.bgColor} border-transparent`}>
          <div className="flex items-center gap-2 mb-2">
            <IndianRupee className={`w-5 h-5 ${risk.color}`} />
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Rupee Risk</span>
          </div>
          <div className={`text-3xl font-black ${risk.color}`}>
            {formatRupees(preview.total_rupee_risk)}
          </div>
          <div className={`text-xs font-semibold mt-1 ${risk.color}`}>{risk.label} risk</div>
        </div>
      </div>

      {preview.total_mismatches === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-2xl p-8 text-center">
          <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
          <h2 className="text-xl font-bold text-green-800 mb-2">Perfect Match!</h2>
          <p className="text-green-700 text-sm">
            Your GSTR-1 and GSTR-3B are perfectly reconciled. You&apos;re clear to file.
          </p>
          <Link href={ROUTES.DASHBOARD} className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-green-700 hover:underline">
            Back to Dashboard <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <>
          {/* Preview mismatches */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
              <h2 className="font-bold text-gray-900">Mismatches</h2>
              <span className="text-sm text-gray-500">
                Showing {preview.preview_mismatches.length} of {preview.total_mismatches}
              </span>
            </div>

            <div className="divide-y divide-gray-50">
              {preview.preview_mismatches.map((m) => (
                <MismatchRow key={`${m.invoice_number}-${m.mismatch_type}`} mismatch={m} locked={false} />
              ))}

              {/* Locked rows */}
              {lockedCount > 0 &&
                Array.from({ length: Math.min(lockedCount, 3) }).map((_, i) => (
                  <MismatchRow key={`locked-${i}`} mismatch={LOCKED_PLACEHOLDER} locked />
                ))}
            </div>
          </div>

          {/* CTA */}
          <div className="bg-gradient-to-br from-blue-700 to-blue-800 rounded-2xl p-6 sm:p-8 text-white">
            <div className="flex items-start gap-4 mb-5">
              <div className="bg-white/10 rounded-xl p-3 shrink-0">
                <Lock className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold mb-1">
                  {lockedCount > 0
                    ? `${lockedCount} more mismatch${lockedCount !== 1 ? "es" : ""} are locked`
                    : "Unlock the complete report"}
                </h2>
                <p className="text-blue-200 text-sm">
                  Get the full report with all mismatches, AI explanations for every item,
                  and a PDF you can share with your CA.
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-3 mb-5">
              {["All mismatches with details", "AI explanation for each item", "PDF report download", "WhatsApp delivery"].map((f) => (
                <div key={f} className="flex items-center gap-2 text-sm text-blue-100">
                  <CheckCircle className="w-4 h-4 text-blue-300 shrink-0" />
                  {f}
                </div>
              ))}
            </div>

            {payError && (
              <div className="mb-4 bg-red-500/20 border border-red-400/30 text-red-100 text-sm rounded-xl px-4 py-3">
                {payError}
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3 items-center">
              <button
                onClick={handleUnlock}
                disabled={paymentLoading}
                className="flex-1 flex items-center justify-center gap-2 bg-white text-blue-700 font-bold py-3.5 px-6 rounded-xl hover:bg-blue-50 transition-colors disabled:opacity-70"
              >
                {paymentLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <TrendingUp className="w-5 h-5" />
                )}
                {paymentLoading ? "Opening Razorpay..." : `Unlock Full Report — ₹${ONE_TIME_SCAN_PRICE}`}
              </button>
              <span className="text-blue-300 text-xs">Secure payment via Razorpay</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
