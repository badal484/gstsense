"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Download,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  Loader2,
  ArrowLeft,
  IndianRupee,
} from "lucide-react";
import { scanApi } from "@/lib/api";
import { ScanReport, Mismatch } from "@/types";
import { ROUTES, MISMATCH_TYPE_LABELS, MISMATCH_TYPE_COLORS } from "@/lib/constants";
import { formatRupees, formatMonth, formatDate, getRiskLevel } from "@/lib/utils";

function MismatchCard({ mismatch }: { mismatch: Mismatch }) {
  const [expanded, setExpanded] = useState(false);
  const typeLabel = MISMATCH_TYPE_LABELS[mismatch.mismatch_type] ?? mismatch.mismatch_type;
  const typeColor = MISMATCH_TYPE_COLORS[mismatch.mismatch_type] ?? "bg-gray-100 text-gray-600";
  const risk = getRiskLevel(mismatch.rupee_difference);

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start justify-between gap-4 px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${typeColor}`}>
              {typeLabel}
            </span>
            <span className="text-xs font-mono text-gray-500">{mismatch.invoice_number}</span>
          </div>
          <div className="text-xs text-gray-400 font-mono truncate">{mismatch.supplier_gstin}</div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className={`font-bold ${risk.color}`}>{formatRupees(mismatch.rupee_difference)}</span>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-gray-50 px-5 py-4 space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-xl p-4">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">GSTR-1</div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Taxable Value</span>
                  <span className="font-semibold">{formatRupees(mismatch.gstr1_taxable_value)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Tax Amount</span>
                  <span className="font-semibold">{formatRupees(mismatch.gstr1_tax_amount)}</span>
                </div>
              </div>
            </div>
            <div className="bg-gray-50 rounded-xl p-4">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">GSTR-3B</div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Taxable Value</span>
                  <span className="font-semibold">{formatRupees(mismatch.gstr3b_taxable_value)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Tax Amount</span>
                  <span className="font-semibold">{formatRupees(mismatch.gstr3b_tax_amount)}</span>
                </div>
              </div>
            </div>
          </div>

          {mismatch.ai_explanation && (
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
              <div className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-1.5">AI Analysis</div>
              <p className="text-sm text-blue-900 leading-relaxed">{mismatch.ai_explanation}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

type FilterType = "all" | Mismatch["mismatch_type"];

export default function ReportPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const router = useRouter();
  const [report, setReport] = useState<ScanReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [filter, setFilter] = useState<FilterType>("all");

  useEffect(() => {
    if (!scanId) return;
    scanApi
      .getReport(scanId)
      .then((res) => {
        const data = res.data.data;
        if (data) setReport(data);
      })
      .catch(() => router.push(`${ROUTES.SCAN_PREVIEW}?scan_id=${scanId}`))
      .finally(() => setLoading(false));
  }, [scanId, router]);

  async function handleDownload() {
    if (!scanId) return;
    setDownloading(true);
    try {
      const data = await scanApi.downloadReport(scanId);
      if (data?.download_url?.startsWith("http")) {
        window.open(data.download_url, "_blank");
      } else {
        alert("PDF download requires AWS S3 setup (available after deployment). Your full report is shown on this page.");
      }
    } catch {
      alert("PDF generation is not available in local development mode.");
    } finally {
      setDownloading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
      </div>
    );
  }

  if (!report) return null;

  const risk = getRiskLevel(report.total_rupee_risk);
  const mismatches = report.mismatches ?? [];
  const filtered =
    filter === "all" ? mismatches : mismatches.filter((m) => m.mismatch_type === filter);

  const typeGroups = mismatches.reduce<Record<string, number>>((acc, m) => {
    acc[m.mismatch_type] = (acc[m.mismatch_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              href={ROUTES.DASHBOARD}
              className="text-sm text-gray-500 hover:text-blue-700 transition-colors flex items-center gap-1"
            >
              <ArrowLeft className="w-4 h-4" /> Dashboard
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            Reconciliation Report — {formatMonth(report.scan_month)}
          </h1>
          <p className="text-gray-400 text-xs mt-1">Generated {formatDate(report.created_at)}</p>
        </div>
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors disabled:opacity-70 shrink-0"
        >
          {downloading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          Download PDF
        </button>
      </div>

      {/* Summary */}
      <div className="grid sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-2">
            <FileSpreadsheet className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-500 font-semibold uppercase tracking-wide">Invoices</span>
          </div>
          <div className="text-2xl font-black text-gray-900">
            {report.total_invoices_scanned.toLocaleString("en-IN")}
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-orange-500" />
            <span className="text-xs text-gray-500 font-semibold uppercase tracking-wide">Mismatches</span>
          </div>
          <div className="text-2xl font-black text-orange-600">{report.total_mismatches}</div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-2">
            <IndianRupee className={`w-4 h-4 ${risk.color}`} />
            <span className="text-xs text-gray-500 font-semibold uppercase tracking-wide">Rupee Risk</span>
          </div>
          <div className={`text-2xl font-black ${risk.color}`}>{formatRupees(report.total_rupee_risk)}</div>
          <div className={`text-xs font-semibold mt-0.5 ${risk.color}`}>{risk.label}</div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span className="text-xs text-gray-500 font-semibold uppercase tracking-wide">Suppliers</span>
          </div>
          <div className="text-2xl font-black text-gray-900">{report.total_unique_suppliers}</div>
        </div>
      </div>

      {/* Mismatch breakdown */}
      {Object.keys(typeGroups).length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Mismatch Breakdown</h2>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setFilter("all")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                filter === "all"
                  ? "bg-blue-700 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              All ({mismatches.length})
            </button>
            {Object.entries(typeGroups).map(([type, count]) => {
              const label = MISMATCH_TYPE_LABELS[type as Mismatch["mismatch_type"]] ?? type;
              const active = filter === type;
              return (
                <button
                  key={type}
                  onClick={() => setFilter(type as FilterType)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                    active
                      ? "bg-blue-700 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {label} ({count})
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Mismatch list */}
      {mismatches.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-2xl p-8 text-center">
          <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
          <h2 className="text-xl font-bold text-green-800 mb-2">Perfect Reconciliation</h2>
          <p className="text-green-700 text-sm">
            No mismatches found between your GSTR-1 and GSTR-3B. You&apos;re clear to file.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-700">
              {filtered.length} mismatch{filtered.length !== 1 ? "es" : ""} · sorted by rupee risk
            </h2>
          </div>
          {filtered.map((m, i) => (
            <MismatchCard key={`${m.invoice_number}-${m.mismatch_type}-${i}`} mismatch={m} />
          ))}
        </div>
      )}

      {(report.warnings ?? []).length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-yellow-800 mb-2">Processing Notes</h3>
          <ul className="space-y-1">
            {(report.warnings ?? []).map((w, i) => (
              <li key={i} className="text-xs text-yellow-700 flex items-start gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" /> {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
