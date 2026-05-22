"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Clock,
  Download,
  Loader2,
  Share2,
  ShieldCheck,
} from "lucide-react";
import api from "@/lib/api";
import { API_ROUTES, ROUTES } from "@/lib/constants";
import { formatRupees } from "@/lib/utils";

interface NoticeDetail {
  id: string;
  notice_number: string;
  notice_type: string;
  demand_amount: string | null;
  tax_period: string | null;
  response_due_date: string | null;
  draft_status: "pending" | "generated" | "reviewed" | "approved" | "failed";
  icai_membership_number: string | null;
  created_at: string;
}

interface NoticeDraft {
  notice_id: string;
  notice_number: string;
  draft_reply_text: string;
  draft_status: string;
  disclaimer_text: string;
  warnings: string[];
}

const NOTICE_TYPE_LABELS: Record<string, string> = {
  DRC_01: "DRC-01 — Show Cause Notice",
  DRC_01A: "DRC-01A — Tax Ascertained",
  DRC_01C: "DRC-01C — ITC Difference Notice",
  DRC_07: "DRC-07 — Order Summary",
  DRC_10: "DRC-10 — Auction Notice",
  ASMT_10: "ASMT-10 — Scrutiny Notice",
  ASMT_11: "ASMT-11 — Scrutiny Reply",
  REG_03: "REG-03 — Registration Notice",
  REG_17: "REG-17 — Cancellation Notice",
  other: "GST Notice",
};

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const parts = dateStr.split(/[\/\-\.]/);
  if (parts.length < 3) return null;
  const due = new Date(
    `${parts[2]}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`
  );
  if (isNaN(due.getTime())) return null;
  return Math.ceil((due.getTime() - Date.now()) / 86400000);
}

function DraftText({ text }: { text: string }) {
  return (
    <div className="font-mono text-xs text-gray-800 leading-relaxed whitespace-pre-wrap">
      {text.split(/(\[PLACEHOLDER[^\]]*\])/gi).map((part, i) =>
        /^\[PLACEHOLDER/i.test(part) ? (
          <span key={i} className="bg-amber-100 text-amber-800 font-semibold px-0.5 rounded">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </div>
  );
}

export default function NoticeDetailPage() {
  const { noticeId } = useParams<{ noticeId: string }>();
  const router = useRouter();

  const [notice, setNotice] = useState<NoticeDetail | null>(null);
  const [draft, setDraft] = useState<NoticeDraft | null>(null);
  const [loadingNotice, setLoadingNotice] = useState(true);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [icaiInput, setIcaiInput] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const [approving, setApproving] = useState(false);

  const loadNotice = useCallback(async () => {
    try {
      const r = await api.get(API_ROUTES.NOTICES.DETAIL(noticeId));
      setNotice(r.data.data);
      return r.data.data as NoticeDetail;
    } catch {
      router.push(ROUTES.NOTICES);
      return null;
    }
  }, [noticeId, router]);

  const loadDraft = useCallback(async () => {
    setLoadingDraft(true);
    try {
      const r = await api.get(API_ROUTES.NOTICES.DRAFT(noticeId));
      setDraft(r.data.data);
    } catch {
      // draft not ready yet
    } finally {
      setLoadingDraft(false);
    }
  }, [noticeId]);

  useEffect(() => {
    if (!noticeId) return;
    loadNotice().then((n) => {
      setLoadingNotice(false);
      if (n && n.draft_status !== "pending") {
        loadDraft();
      }
    });
  }, [noticeId, loadNotice, loadDraft]);

  // Poll for draft when status is pending
  useEffect(() => {
    if (!notice || notice.draft_status !== "pending") return;
    const interval = setInterval(async () => {
      const updated = await loadNotice();
      if (updated && updated.draft_status !== "pending") {
        clearInterval(interval);
        if (updated.draft_status !== "failed") loadDraft();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [notice, loadNotice, loadDraft]);

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    if (!icaiInput.trim()) {
      setVerifyError("Please enter your ICAI membership number.");
      return;
    }
    setVerifying(true);
    setVerifyError("");
    try {
      await api.post(
        `${API_ROUTES.NOTICES.VERIFY(noticeId)}?icai_number=${encodeURIComponent(icaiInput.trim())}`
      );
      await loadNotice();
      await loadDraft();
    } catch (err: unknown) {
      setVerifyError(err instanceof Error ? err.message : "Verification failed. Check the number and retry.");
    } finally {
      setVerifying(false);
    }
  }

  async function handleDownload() {
    setDownloading(true);
    try {
      const r = await api.get(API_ROUTES.NOTICES.DOWNLOAD(noticeId), {
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `GSTSense_Notice_Reply_${notice?.notice_number ?? noticeId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  }

  async function handleShare() {
    try {
      const r = await api.post(API_ROUTES.NOTICES.SHARE(noticeId));
      const url = r.data.data.share_url;
      await navigator.clipboard.writeText(url);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2500);
    } catch {
      await navigator.clipboard.writeText(window.location.href);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2500);
    }
  }

  async function handleApprove() {
    setApproving(true);
    try {
      await api.post(API_ROUTES.NOTICES.APPROVE(noticeId), { notes: null });
      await loadNotice();
    } finally {
      setApproving(false);
    }
  }

  if (loadingNotice) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
      </div>
    );
  }

  if (!notice) return null;

  const days = daysUntil(notice.response_due_date);
  const urgent = days !== null && days <= 7;
  const credentialsVerified = !!notice.icai_membership_number;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link
            href={ROUTES.NOTICES}
            className="text-sm text-gray-500 hover:text-blue-700 flex items-center gap-1 mb-1"
          >
            <ArrowLeft className="w-4 h-4" /> Notices
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Notice Reply Draft</h1>
          <p className="text-gray-400 text-xs mt-0.5">
            {NOTICE_TYPE_LABELS[notice.notice_type] ?? notice.notice_type} ·{" "}
            {notice.notice_number}
          </p>
        </div>
        {credentialsVerified && (
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleShare}
              className="flex items-center gap-2 text-sm font-semibold border border-gray-200 text-gray-700 px-3 py-2 rounded-xl hover:bg-gray-50 transition-colors"
            >
              <Share2 className="w-4 h-4" />
              {shareCopied ? "Copied!" : "Share with CA"}
            </button>
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2 rounded-xl text-sm hover:bg-blue-800 disabled:opacity-60 transition-colors"
            >
              {downloading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              Download Reply PDF
            </button>
          </div>
        )}
      </div>

      {/* Notice Details Card */}
      <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Notice Details</h2>
        <div className="grid sm:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs text-gray-400 mb-1">Notice Number</div>
            <div className="font-mono font-semibold text-gray-900">{notice.notice_number}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-1">Demand Amount</div>
            <div className="font-bold text-gray-900">
              {notice.demand_amount ? formatRupees(notice.demand_amount) : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-1">Tax Period</div>
            <div className="text-gray-700">{notice.tax_period ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-1">Response Due</div>
            {notice.response_due_date ? (
              <div
                className={`font-semibold ${urgent ? "text-red-600" : "text-gray-700"}`}
              >
                {notice.response_due_date}
                {days !== null && (
                  <span className="ml-2 text-xs font-normal">
                    {urgent ? (
                      <span className="text-red-600">
                        ⚠ {days <= 0 ? "Overdue!" : `${days} days left`}
                      </span>
                    ) : (
                      <span className="text-gray-400">{days} days left</span>
                    )}
                  </span>
                )}
              </div>
            ) : (
              <div className="text-gray-500">—</div>
            )}
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-1">Draft Status</div>
            <div className="text-gray-700 capitalize">{notice.draft_status.replace("_", " ")}</div>
          </div>
        </div>
      </div>

      {/* Draft status: pending */}
      {notice.draft_status === "pending" && (
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-10 text-center">
          <Loader2 className="w-10 h-10 text-blue-600 animate-spin mx-auto mb-3" />
          <h2 className="text-lg font-bold text-blue-900">Generating your reply draft...</h2>
          <p className="text-blue-700 text-sm mt-1">
            Our AI is analysing the notice and preparing a structured reply. This usually takes
            30–60 seconds.
          </p>
        </div>
      )}

      {/* Draft status: failed */}
      {notice.draft_status === "failed" && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-10 text-center">
          <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-red-900">Draft generation failed</h2>
          <p className="text-red-700 text-sm mt-1">
            We could not generate a draft for this notice. Please contact support or try uploading
            the notice again.
          </p>
        </div>
      )}

      {/* Draft content */}
      {notice.draft_status !== "pending" && notice.draft_status !== "failed" && (
        <>
          {/* Disclaimer */}
          <div className="bg-red-50 border-2 border-red-300 rounded-2xl p-4 flex gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-bold text-red-800 mb-1">
                ⚠ IMPORTANT — AI-Generated Draft
              </p>
              <p className="text-xs text-red-700 leading-relaxed">
                This is an AI-generated draft. It must be reviewed and approved by a qualified
                Chartered Accountant or Advocate before submission to any government authority.
                GSTSense does not practice law or provide legal advice. You assume sole
                professional liability for its accuracy before use.
              </p>
            </div>
          </div>

          {/* Warnings */}
          {draft?.warnings && draft.warnings.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 space-y-2">
              <p className="text-sm font-bold text-amber-800">⚠ AI Verification Warnings</p>
              <ul className="space-y-1">
                {draft.warnings.map((w, i) => (
                  <li key={i} className="text-xs text-amber-700 flex gap-2">
                    <span className="shrink-0">•</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Draft text */}
          {loadingDraft ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
            </div>
          ) : draft ? (
            <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-6 max-h-[60vh] overflow-y-auto">
              <DraftText text={draft.draft_reply_text} />
            </div>
          ) : null}

          {/* CA Credential Verification */}
          {!credentialsVerified ? (
            <div className="bg-white border-2 border-amber-300 rounded-2xl p-5 shadow-sm">
              <div className="flex items-start gap-3 mb-4">
                <ShieldCheck className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-gray-900">
                    CA Credential Verification Required
                  </h3>
                  <p className="text-xs text-gray-500 mt-1">
                    To download this draft, enter your ICAI Membership Number. This is legally
                    required to ensure compliance with the Advocates Act, 1961.
                  </p>
                </div>
              </div>
              <form onSubmit={handleVerify} className="flex gap-3 items-end">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    ICAI Membership Number
                  </label>
                  <input
                    value={icaiInput}
                    onChange={(e) => {
                      setIcaiInput(e.target.value);
                      setVerifyError("");
                    }}
                    placeholder="e.g. MRN123456 or FRN100001W"
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-amber-400"
                  />
                  {verifyError && (
                    <p className="text-xs text-red-600 mt-1">{verifyError}</p>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={verifying}
                  className="flex items-center gap-2 bg-amber-600 text-white font-semibold px-4 py-2 rounded-xl text-sm hover:bg-amber-700 disabled:opacity-60 transition-colors"
                >
                  {verifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  Verify
                </button>
              </form>
            </div>
          ) : (
            <div className="bg-green-50 border border-green-200 rounded-2xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="text-sm font-semibold text-green-800">
                  Verified: CA {notice.icai_membership_number}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {notice.draft_status !== "approved" && (
                  <button
                    onClick={handleApprove}
                    disabled={approving}
                    className="flex items-center gap-1.5 text-xs font-semibold bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-60 transition-colors"
                  >
                    {approving ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <CheckCircle className="w-3.5 h-3.5" />
                    )}
                    Approve Draft
                  </button>
                )}
                {notice.draft_status === "approved" && (
                  <span className="text-xs font-semibold text-green-700 bg-green-100 px-2 py-1 rounded-full">
                    ✓ Approved
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Submission instructions after approval */}
          {notice.draft_status === "approved" && (
            <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
              <p className="text-xs font-semibold text-blue-800 mb-1">
                How to submit to GST Portal:
              </p>
              <ol className="text-xs text-blue-700 space-y-1 list-decimal list-inside">
                <li>Download the Reply PDF using the button above</li>
                <li>Login to the GST portal at gstin.gov.in</li>
                <li>Go to Services → Notices → View Notices</li>
                <li>Find your notice and click &quot;Reply&quot;</li>
                <li>Upload the downloaded PDF as your reply</li>
                <li>Submit before the due date</li>
              </ol>
            </div>
          )}
        </>
      )}
    </div>
  );
}
