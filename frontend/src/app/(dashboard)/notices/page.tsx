"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Bell,
  BellOff,
  CheckCircle,
  Clock,
  Download,
  FileText,
  Loader2,
  Upload,
  X,
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
  draft_status: "pending" | "generated" | "reviewed" | "approved";
  icai_membership_number: string | null;
  created_at: string;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: React.ReactNode }
> = {
  pending: {
    label: "Draft Pending",
    color: "bg-gray-100 text-gray-600",
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
  },
  generated: {
    label: "Draft Ready",
    color: "bg-blue-100 text-blue-700",
    icon: <FileText className="w-3 h-3" />,
  },
  reviewed: {
    label: "Under Review",
    color: "bg-amber-100 text-amber-700",
    icon: <Clock className="w-3 h-3" />,
  },
  approved: {
    label: "Approved",
    color: "bg-green-100 text-green-700",
    icon: <CheckCircle className="w-3 h-3" />,
  },
};

const NOTICE_TYPE_LABELS: Record<string, string> = {
  DRC_01: "DRC-01 — Demand Notice",
  DRC_01A: "DRC-01A — Tax Ascertained",
  DRC_01C: "DRC-01C — ITC Mismatch",
  DRC_07: "DRC-07 — Order Summary",
  DRC_10: "DRC-10 — Auction Notice",
  ASMT_10: "ASMT-10 — Scrutiny Notice",
  ASMT_11: "ASMT-11 — Scrutiny Reply",
  REG_03: "REG-03 — Registration Query",
  REG_17: "REG-17 — Cancellation Notice",
  other: "Other Notice",
};

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const parts = dateStr.split(/[\/\-\.]/);
  if (parts.length < 3) return null;
  const due = new Date(`${parts[2]}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`);
  if (isNaN(due.getTime())) return null;
  return Math.ceil((due.getTime() - Date.now()) / 86400000);
}

export default function NoticesPage() {
  const [notices, setNotices] = useState<NoticeDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadNotices() {
    try {
      const r = await api.get(API_ROUTES.NOTICES.LIST);
      setNotices(r.data.data.notices);
      setTotal(r.data.data.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadNotices();
  }, []);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setUploadError("Please select a PDF file.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Only PDF files are accepted.");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setUploadError("File must be under 20 MB.");
      return;
    }
    setUploading(true);
    setUploadError("");
    const form = new FormData();
    form.append("notice_file", file);
    try {
      await api.post(API_ROUTES.NOTICES.UPLOAD, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setShowUploadModal(false);
      if (fileRef.current) fileRef.current.value = "";
      await loadNotices();
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">GST Notice Management</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Upload notices and get AI-drafted replies
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
        >
          <Upload className="w-4 h-4" />
          Upload Notice
        </button>
      </div>

      {/* Legal disclaimer banner */}
      <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex gap-3">
        <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
        <p className="text-xs text-red-800 leading-relaxed">
          <strong>Legal Notice:</strong> All AI-generated drafts require review and approval by a
          qualified Chartered Accountant or Advocate before submission. GSTSense does not practice
          law or provide legal advice. CA credential verification is required before downloading any draft.
        </p>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
        </div>
      )}

      {/* Empty state */}
      {!loading && notices.length === 0 && (
        <div className="bg-white border border-gray-100 rounded-2xl p-14 text-center shadow-sm">
          <BellOff className="w-14 h-14 text-gray-300 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-gray-900 mb-2">No notices yet</h2>
          <p className="text-gray-500 text-sm max-w-sm mx-auto mb-6">
            If you receive a GST notice, upload it here and we will help you draft a proper reply.
          </p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="inline-flex items-center gap-2 bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
          >
            <Upload className="w-4 h-4" />
            Upload Notice
          </button>
        </div>
      )}

      {/* Notices table */}
      {!loading && notices.length > 0 && (
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Notice No", "Type", "Period", "Demand Amount", "Due Date", "Status", "Action"].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {notices.map((n) => {
                const status = STATUS_CONFIG[n.draft_status] ?? STATUS_CONFIG.pending;
                const days = daysUntil(n.response_due_date);
                const urgent = days !== null && days <= 7;
                return (
                  <tr key={n.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-900">
                      {n.notice_number}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {NOTICE_TYPE_LABELS[n.notice_type] ?? n.notice_type}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{n.tax_period ?? "—"}</td>
                    <td className="px-4 py-3 text-xs font-semibold text-gray-900">
                      {n.demand_amount ? formatRupees(n.demand_amount) : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {n.response_due_date ? (
                        <span className={urgent ? "text-red-600 font-semibold" : "text-gray-500"}>
                          {n.response_due_date}
                          {days !== null && (
                            <span className="ml-1 text-xs">
                              ({days <= 0 ? "overdue" : `${days}d`})
                            </span>
                          )}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full ${status.color}`}
                      >
                        {status.icon}
                        {status.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {n.draft_status === "pending" ? (
                        <span className="text-xs text-gray-400 italic">Generating...</span>
                      ) : (
                        <Link
                          href={ROUTES.NOTICE_DETAIL(n.id)}
                          className="text-xs font-semibold text-blue-700 hover:text-blue-800 transition-colors"
                        >
                          {n.draft_status === "approved" ? "View & Download" : "Review Draft"}
                        </Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {total > notices.length && (
            <div className="px-4 py-3 border-t border-gray-100 text-xs text-gray-500 text-right">
              Showing {notices.length} of {total} notices
            </div>
          )}
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">Upload GST Notice</h2>
              <button
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadError("");
                }}
                className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpload} className="space-y-4">
              {/* Drop zone */}
              <label className="flex flex-col items-center justify-center border-2 border-dashed border-gray-200 rounded-xl p-8 cursor-pointer hover:border-blue-400 hover:bg-blue-50/30 transition-colors">
                <FileText className="w-10 h-10 text-gray-300 mb-3" />
                <span className="text-sm font-medium text-gray-700">
                  Drag your GST notice PDF here
                </span>
                <span className="text-xs text-gray-400 mt-1">PDF only · Max 20 MB</span>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  onChange={() => setUploadError("")}
                />
              </label>

              {/* Info box */}
              <div className="bg-blue-50 border border-blue-100 rounded-xl p-3">
                <p className="text-xs text-blue-800 leading-relaxed">
                  Our AI will automatically extract notice details and generate a structured reply
                  draft. A Chartered Accountant must review and approve the draft before submission.
                </p>
              </div>

              {uploadError && (
                <p className="text-xs text-red-600 font-medium">{uploadError}</p>
              )}

              <button
                type="submit"
                disabled={uploading}
                className="w-full flex items-center justify-center gap-2 bg-blue-700 text-white font-semibold py-2.5 rounded-xl text-sm hover:bg-blue-800 disabled:opacity-60 transition-colors"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Upload Notice
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
