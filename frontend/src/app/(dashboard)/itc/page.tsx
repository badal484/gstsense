"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  Clock,
  Upload,
  Loader2,
  Copy,
  IndianRupee,
  FileSpreadsheet,
  Lock,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import api from "@/lib/api";
import { useSubscriptionPayment } from "@/hooks/useSubscriptionPayment";
import { ACCEPTED_FILE_TYPES, MAX_FILE_SIZE_BYTES } from "@/lib/constants";
import { formatRupees } from "@/lib/utils";

interface ITCSummary {
  total_unclaimed_itc: string;
  total_excess_claimed: string;
  total_at_risk: string;
  issue_count: number;
  requires_upgrade: boolean;
}

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

function DropZone({
  label,
  hint,
  file,
  onFile,
}: {
  label: string;
  hint?: string;
  file: File | null;
  onFile: (f: File) => void;
}) {
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className={`relative rounded-2xl border-2 border-dashed p-6 text-center transition-colors cursor-pointer ${
        file ? "border-green-400 bg-green-50" : "border-gray-200 hover:border-blue-400 hover:bg-blue-50"
      }`}
      onClick={() => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".xlsx,.xls";
        input.onchange = () => { if (input.files?.[0]) onFile(input.files[0]); };
        input.click();
      }}
    >
      {file ? (
        <div className="flex items-center justify-center gap-3">
          <CheckCircle className="w-6 h-6 text-green-600" />
          <div className="text-left">
            <div className="text-sm font-semibold text-green-800">{label}</div>
            <div className="text-xs text-green-600">{file.name}</div>
          </div>
        </div>
      ) : (
        <>
          <FileSpreadsheet className="w-8 h-8 text-gray-300 mx-auto mb-2" />
          <div className="text-sm font-semibold text-gray-700">{label}</div>
          {hint && <div className="text-xs text-gray-400 mt-1">{hint}</div>}
          <div className="text-xs text-gray-400 mt-2">Drag & drop or click · .xlsx, .xls · max 50MB</div>
        </>
      )}
    </div>
  );
}

function IssueCard({ issue }: { issue: ITCIssue }) {
  const [copied, setCopied] = useState(false);

  function copyGSTIN() {
    navigator.clipboard.writeText(issue.supplier_gstin);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

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
            {issue.invoice_date && (
              <span className="text-xs text-gray-400">{issue.invoice_date}</span>
            )}
          </div>
          <div className="text-xs font-mono text-gray-400">{issue.supplier_gstin}</div>
        </div>
        <div className={`text-xl font-black shrink-0 ${diffColor}`}>
          {formatRupees(issue.difference)}
        </div>
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

      <div className="flex justify-end">
        {issue.issue_type === "supplier_not_filed" ? (
          <button
            onClick={copyGSTIN}
            className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 border border-amber-200 rounded-lg px-3 py-1.5 hover:bg-amber-50 transition-colors"
          >
            <Copy className="w-3.5 h-3.5" />
            {copied ? "Copied!" : "Copy Supplier GSTIN"}
          </button>
        ) : issue.issue_type === "excess_claimed" ? (
          <span className="text-xs text-red-600 font-semibold">Note for Correction in next GSTR-3B</span>
        ) : (
          <span className="text-xs text-green-700 font-semibold">Claim in next GSTR-3B filing</span>
        )}
      </div>
    </div>
  );
}

type FilterTab = "all" | "unclaimed" | "excess_claimed" | "supplier_not_filed";

export default function ITCPage() {
  const { organization, user } = useAuthStore();
  const { initiateSubscription, isLoading: upgrading, error: upgradeError } = useSubscriptionPayment();

  const [summary, setSummary] = useState<ITCSummary | null>(null);
  const [gstr3bFile, setGstr3bFile] = useState<File | null>(null);
  const [gstr2bFile, setGstr2bFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pollingId, setPollingId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<ITCAnalysis | null>(null);
  const [filter, setFilter] = useState<FilterTab>("all");
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.get("/api/v1/itc/summary/latest")
      .then((r) => setSummary(r.data.data))
      .catch(() => {});
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const pollStatus = useCallback(async (scanId: string) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(async () => {
      try {
        const r = await api.get(`/api/v1/itc/${scanId}/status`);
        const status = r.data.data?.status;
        if (status === "completed") {
          clearInterval(pollIntervalRef.current!);
          pollIntervalRef.current = null;
          setPollingId(null);
          const ar = await api.get(`/api/v1/itc/${scanId}/analysis`);
          setAnalysis(ar.data.data);
        } else if (status === "failed") {
          clearInterval(pollIntervalRef.current!);
          pollIntervalRef.current = null;
          setPollingId(null);
          setUploadError("ITC analysis failed. Please check your files and try again.");
        }
      } catch {
        clearInterval(pollIntervalRef.current!);
        pollIntervalRef.current = null;
        setPollingId(null);
      }
    }, 3000);
  }, []);

  function handleUpgradeToGrowth() {
    initiateSubscription(
      "growth",
      user?.email ?? "",
      "Growth",
      () => {},
      () => {},
    );
  }

  async function handleAnalyze() {
    if (!gstr3bFile || !gstr2bFile) return;
    setUploading(true);
    setUploadError(null);

    const form = new FormData();
    form.append("gstr3b_file", gstr3bFile);
    form.append("gstr2b_file", gstr2bFile);

    try {
      const r = await api.post("/api/v1/itc/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const scanId = r.data.data?.scan_id;
      if (!scanId) throw new Error("No scan ID returned");
      setPollingId(scanId);
      pollStatus(scanId);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  const isRestrictedPlan = organization?.plan === "free" || organization?.plan === "smb";

  // ── UPGRADE PROMPT ────────────────────────────────────────────────────────
  if (isRestrictedPlan) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">ITC Recovery</h1>

        <div className="bg-gradient-to-br from-purple-700 to-indigo-800 rounded-3xl p-8 text-white">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-white/10 rounded-2xl p-3">
              <TrendingUp className="w-7 h-7 text-white" />
            </div>
            <div>
              <div className="text-xs font-semibold text-purple-200 uppercase tracking-wide">Growth Plan Feature</div>
              <h2 className="text-2xl font-bold">Unlock ITC Recovery</h2>
            </div>
          </div>

          {summary && (
            <div className="bg-white/10 rounded-2xl p-4 mb-6">
              <div className="text-sm text-purple-200 mb-1">Estimated unclaimed ITC based on your filing pattern</div>
              <div className="text-4xl font-black">{formatRupees(summary.total_unclaimed_itc)}</div>
              <div className="text-sm text-purple-200 mt-1">in unclaimed input tax credit</div>
            </div>
          )}

          <p className="text-purple-100 text-sm mb-6">
            Businesses like yours typically leave ₹20,000 to ₹2,00,000 in input tax credit
            unclaimed every month. The ITC Recovery engine finds every rupee you are owed.
          </p>

          <div className="grid sm:grid-cols-2 gap-2 mb-6">
            {[
              "Find all unclaimed input tax credits",
              "Detect excess claims before Rule 88D notice",
              "Identify suppliers who have not filed",
              "Monthly ITC health report",
            ].map((f) => (
              <div key={f} className="flex items-center gap-2 text-sm text-purple-100">
                <CheckCircle className="w-4 h-4 text-purple-300 shrink-0" />
                {f}
              </div>
            ))}
          </div>

          {upgradeError && (
            <div className="mb-3 bg-red-500/20 border border-red-400/30 text-red-100 text-sm rounded-xl px-4 py-3">
              {upgradeError}
            </div>
          )}

          <button
            onClick={handleUpgradeToGrowth}
            disabled={upgrading}
            className="w-full flex items-center justify-center gap-2 bg-white text-purple-700 font-bold py-3.5 rounded-2xl hover:bg-purple-50 disabled:opacity-70 transition-colors"
          >
            {upgrading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Lock className="w-5 h-5" />
            )}
            {upgrading ? "Activating…" : "Upgrade to Growth — ₹2,499/month"}
          </button>
        </div>
      </div>
    );
  }

  // ── MAIN PAGE (Growth+ users) ─────────────────────────────────────────────
  const filtered =
    filter === "all"
      ? analysis?.issues ?? []
      : (analysis?.issues ?? []).filter((i) => i.issue_type === filter);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">ITC Recovery Analysis</h1>
        <p className="text-gray-500 text-sm mt-1">
          Upload GSTR-3B and GSTR-2B to find unclaimed input tax credits
        </p>
      </div>

      {/* Upload form */}
      {!analysis && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <DropZone
              label="GSTR-3B (Summary Return)"
              file={gstr3bFile}
              onFile={setGstr3bFile}
            />
            <DropZone
              label="GSTR-2B (Auto-drafted ITC Statement)"
              hint='Download from GST Portal → Returns → View Returns → GSTR-2B'
              file={gstr2bFile}
              onFile={setGstr2bFile}
            />
          </div>

          {uploadError && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
              {uploadError}
            </div>
          )}

          {pollingId ? (
            <div className="flex items-center justify-center gap-3 py-4 text-gray-500">
              <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
              <span className="text-sm">Analysing your ITC data…</span>
            </div>
          ) : (
            <button
              onClick={handleAnalyze}
              disabled={!gstr3bFile || !gstr2bFile || uploading}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-gray-200 disabled:text-gray-400 text-white font-bold py-3.5 rounded-2xl transition-colors flex items-center justify-center gap-2"
            >
              {uploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <TrendingUp className="w-5 h-5" />}
              {uploading ? "Uploading…" : "Analyse ITC"}
            </button>
          )}
        </div>
      )}

      {/* Results */}
      {analysis && (
        <>
          {/* Summary cards */}
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

          {/* Tabs */}
          <div className="flex flex-wrap gap-2">
            {(["all", "unclaimed", "excess_claimed", "supplier_not_filed"] as FilterTab[]).map((tab) => {
              const count =
                tab === "all"
                  ? analysis.issues.length
                  : (analysis.issues_by_type[tab] ?? 0);
              return (
                <button
                  key={tab}
                  onClick={() => setFilter(tab)}
                  className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                    filter === tab
                      ? "bg-blue-700 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {tab === "all" ? "All" : ISSUE_TYPE_LABELS[tab]} ({count})
                </button>
              );
            })}
          </div>

          {/* Issue list */}
          {filtered.length === 0 ? (
            <div className="bg-green-50 border border-green-200 rounded-2xl p-10 text-center">
              <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
              <h2 className="text-lg font-bold text-green-800">No ITC issues found</h2>
              <p className="text-green-700 text-sm mt-1">
                Your ITC claims are perfectly aligned with GSTR-2B.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-500">{filtered.length} issue{filtered.length !== 1 ? "s" : ""} · sorted by rupee risk</p>
              {filtered.map((issue, i) => (
                <IssueCard key={`${issue.invoice_number}-${issue.issue_type}-${i}`} issue={issue} />
              ))}
            </div>
          )}

          <button
            onClick={() => { setAnalysis(null); setGstr3bFile(null); setGstr2bFile(null); }}
            className="text-sm text-blue-700 font-semibold hover:underline"
          >
            ← Run another analysis
          </button>
        </>
      )}
    </div>
  );
}
