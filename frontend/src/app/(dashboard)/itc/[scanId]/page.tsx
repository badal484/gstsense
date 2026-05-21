"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle,
  Clock,
  Copy,
  Download,
  IndianRupee,
  Loader2,
  Share2,
} from "lucide-react";
import api from "@/lib/api";
import { ROUTES } from "@/lib/constants";
import { formatRupees, formatMonth } from "@/lib/utils";

interface ITCIssue {
  supplier_gstin: string;
  supplier_name: string | null;
  invoice_number: string;
  invoice_date: string | null;
  issue_type: "unclaimed" | "excess_claimed" | "supplier_not_filed";
  available_itc: string;
  claimed_itc: string;
  difference: string;
  recommendation: string;
}

interface ITCAnalysis {
  scan_id: string;
  total_invoices_checked: number;
  total_unique_suppliers: number;
  total_unclaimed_itc: string;
  total_excess_claimed: string;
  total_at_risk: string;
  issues: ITCIssue[];
  issues_by_type: Record<string, number>;
}

const ISSUE_TYPE_LABELS: Record<string, string> = {
  unclaimed: "Unclaimed ITC",
  excess_claimed: "Excess Claimed",
  supplier_not_filed: "Supplier Not Filed",
};

const ISSUE_TYPE_COLORS: Record<string, string> = {
  unclaimed: "bg-green-100 text-green-800",
  excess_claimed: "bg-red-100 text-red-800",
  supplier_not_filed: "bg-amber-100 text-amber-800",
};

function IssueCard({ issue }: { issue: ITCIssue }) {
  const [copied, setCopied] = useState(false);
  const label = ISSUE_TYPE_LABELS[issue.issue_type] ?? issue.issue_type;
  const color = ISSUE_TYPE_COLORS[issue.issue_type] ?? "bg-gray-100 text-gray-600";
  const diffColor =
    issue.issue_type === "unclaimed"
      ? "text-green-700"
      : issue.issue_type === "excess_claimed"
      ? "text-red-700"
      : "text-amber-700";

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>{label}</span>
            <span className="text-xs font-mono text-gray-500">{issue.invoice_number}</span>
            {issue.invoice_date && <span className="text-xs text-gray-400">{issue.invoice_date}</span>}
          </div>
          <div className="text-xs font-mono text-gray-400">{issue.supplier_gstin}</div>
          {issue.supplier_name && (
            <div className="text-xs text-gray-500 mt-0.5">{issue.supplier_name}</div>
          )}
        </div>
        <div className={`text-xl font-black shrink-0 ${diffColor}`}>{formatRupees(issue.difference)}</div>
      </div>

      <div className="grid sm:grid-cols-2 gap-3 text-xs">
        <div className="bg-gray-50 rounded-xl p-3">
          <div className="font-semibold text-gray-500 mb-1">Available (GSTR-2B)</div>
          <div className="font-bold text-gray-900">{formatRupees(issue.available_itc)}</div>
        </div>
        <div className="bg-gray-50 rounded-xl p-3">
          <div className="font-semibold text-gray-500 mb-1">Claimed (GSTR-3B)</div>
          <div className="font-bold text-gray-900">{formatRupees(issue.claimed_itc)}</div>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-xl p-3">
        <div className="text-xs font-semibold text-blue-700 mb-1">Recommendation</div>
        <p className="text-xs text-blue-900 leading-relaxed">{issue.recommendation}</p>
      </div>

      {issue.issue_type === "supplier_not_filed" && (
        <div className="flex justify-end">
          <button
            onClick={() => {
              navigator.clipboard.writeText(issue.supplier_gstin);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
            className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 border border-amber-200 rounded-lg px-3 py-1.5 hover:bg-amber-50 transition-colors"
          >
            <Copy className="w-3.5 h-3.5" />
            {copied ? "Copied!" : "Copy Supplier GSTIN"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function ITCDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const router = useRouter();
  const [analysis, setAnalysis] = useState<ITCAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [shareCopied, setShareCopied] = useState(false);

  useEffect(() => {
    if (!scanId) return;
    api
      .get(`/api/v1/itc/${scanId}/analysis`)
      .then((r) => setAnalysis(r.data.data))
      .catch(() => router.push(ROUTES.DASHBOARD))
      .finally(() => setLoading(false));
  }, [scanId, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
      </div>
    );
  }

  if (!analysis) return null;

  const filtered =
    filter === "all"
      ? analysis.issues
      : analysis.issues.filter((i) => i.issue_type === filter);

  function handleShare() {
    navigator.clipboard.writeText(window.location.href);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link
            href={ROUTES.DASHBOARD}
            className="text-sm text-gray-500 hover:text-blue-700 flex items-center gap-1 mb-1"
          >
            <ArrowLeft className="w-4 h-4" /> Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">ITC Recovery Report</h1>
          <p className="text-gray-400 text-xs mt-0.5">Scan ID: {scanId}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleShare}
            className="flex items-center gap-2 text-sm font-semibold border border-gray-200 text-gray-700 px-4 py-2.5 rounded-xl hover:bg-gray-50 transition-colors"
          >
            <Share2 className="w-4 h-4" />
            {shareCopied ? "Copied!" : "Share with CA"}
          </button>
          <button
            onClick={() => alert("PDF download requires AWS S3 (available after deployment).")}
            className="flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid sm:grid-cols-3 gap-4">
        <div className="bg-green-50 border border-green-200 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <IndianRupee className="w-4 h-4 text-green-600" />
            <span className="text-xs font-semibold text-green-700 uppercase tracking-wide">Unclaimed ITC</span>
          </div>
          <div className="text-2xl font-black text-green-800">{formatRupees(analysis.total_unclaimed_itc)}</div>
          <div className="text-xs text-green-600 mt-1">Money you can still claim</div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-red-600" />
            <span className="text-xs font-semibold text-red-700 uppercase tracking-wide">Excess Claimed</span>
          </div>
          <div className="text-2xl font-black text-red-800">{formatRupees(analysis.total_excess_claimed)}</div>
          <div className="text-xs text-red-600 mt-1">At risk of Rule 88D notice</div>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-amber-600" />
            <span className="text-xs font-semibold text-amber-700 uppercase tracking-wide">Supplier Not Filed</span>
          </div>
          <div className="text-2xl font-black text-amber-800">{formatRupees(analysis.total_at_risk)}</div>
          <div className="text-xs text-amber-600 mt-1">Blocked until supplier files</div>
        </div>
      </div>

      {/* Stats row */}
      <div className="flex gap-6 text-sm text-gray-500">
        <span><strong className="text-gray-900">{analysis.total_invoices_checked}</strong> invoices checked</span>
        <span><strong className="text-gray-900">{analysis.total_unique_suppliers}</strong> unique suppliers</span>
        <span><strong className="text-gray-900">{analysis.issues.length}</strong> issues found</span>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {(["all", "unclaimed", "excess_claimed", "supplier_not_filed"]).map((tab) => {
          const count =
            tab === "all"
              ? analysis.issues.length
              : (analysis.issues_by_type[tab] ?? 0);
          return (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                filter === tab ? "bg-blue-700 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {tab === "all" ? "All" : ISSUE_TYPE_LABELS[tab]} ({count})
            </button>
          );
        })}
      </div>

      {/* Issues */}
      {filtered.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-2xl p-10 text-center">
          <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-green-800">No issues in this category</h2>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((issue, i) => (
            <IssueCard key={`${issue.invoice_number}-${issue.issue_type}-${i}`} issue={issue} />
          ))}
        </div>
      )}
    </div>
  );
}
