"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle,
  Download,
  FileText,
  Loader2,
  Shield,
  XCircle,
} from "lucide-react";
import axios from "axios";
import { API_BASE_URL } from "@/lib/constants";

interface ReviewData {
  notice_id: string;
  notice_type: string;
  gstin: string;
  business_name: string;
  tax_period: string | null;
  demand_amount: string | null;
  draft_response: string;
  draft_status: string;
  issued_at: string | null;
  due_date: string | null;
  is_expired: boolean;
}

type ReviewStatus = "idle" | "loading" | "loaded" | "not_found" | "expired" | "error";

export default function NoticeReviewPage() {
  const params = useParams();
  const token = params?.token as string;

  const [status, setStatus] = useState<ReviewStatus>("loading");
  const [data, setData] = useState<ReviewData | null>(null);
  const [approving, setApproving] = useState(false);
  const [approved, setApproved] = useState(false);
  const [approveError, setApproveError] = useState("");
  const [icaiNumber, setIcaiNumber] = useState("");
  const [comment, setComment] = useState("");

  useEffect(() => {
    if (!token) return;
    axios
      .get(`${API_BASE_URL}/api/v1/notices/review/${token}`)
      .then((r) => {
        const d: ReviewData = r.data.data;
        if (d.is_expired) {
          setStatus("expired");
        } else {
          setData(d);
          setStatus("loaded");
        }
      })
      .catch(() => {
        setStatus("not_found");
      });
  }, [token]);

  async function handleApprove() {
    if (!token) return;
    if (!icaiNumber.trim()) {
      setApproveError("ICAI membership number is required to approve.");
      return;
    }
    setApproving(true);
    setApproveError("");
    try {
      await axios.post(`${API_BASE_URL}/api/v1/notices/review/${token}/approve`, {
        icai_number: icaiNumber.trim(),
        comment: comment.trim() || "",
      });
      setApproved(true);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
          ?.message ?? "Failed to approve. Please try again.";
      setApproveError(msg);
    } finally {
      setApproving(false);
    }
  }

  // ── Loading ──────────────────────────────────────────────────────────────────
  if (status === "loading") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-gray-500">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          <p className="text-sm">Loading notice…</p>
        </div>
      </div>
    );
  }

  // ── Not Found ────────────────────────────────────────────────────────────────
  if (status === "not_found") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md text-center space-y-3">
          <XCircle className="w-14 h-14 text-red-400 mx-auto" />
          <h1 className="text-xl font-bold text-gray-900">Link Not Found</h1>
          <p className="text-gray-500 text-sm">
            This review link is invalid or has already been used.
          </p>
        </div>
      </div>
    );
  }

  // ── Expired ──────────────────────────────────────────────────────────────────
  if (status === "expired") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md text-center space-y-3">
          <AlertTriangle className="w-14 h-14 text-amber-400 mx-auto" />
          <h1 className="text-xl font-bold text-gray-900">Link Expired</h1>
          <p className="text-gray-500 text-sm">
            This review link has expired. Please ask your CA to generate a new one.
          </p>
        </div>
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────────
  if (status === "error" || !data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md text-center space-y-3">
          <XCircle className="w-14 h-14 text-red-400 mx-auto" />
          <h1 className="text-xl font-bold text-gray-900">Something went wrong</h1>
          <p className="text-gray-500 text-sm">Please refresh or try again later.</p>
        </div>
      </div>
    );
  }

  // ── Approved ─────────────────────────────────────────────────────────────────
  if (approved) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md text-center space-y-4">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto" />
          <h1 className="text-2xl font-bold text-gray-900">Response Approved</h1>
          <p className="text-gray-500 text-sm">
            Thank you. Your CA has been notified and the response is now marked as approved.
          </p>
          <div className="bg-green-50 border border-green-100 rounded-xl px-4 py-3 text-sm text-green-800">
            You can now close this tab.
          </div>
        </div>
      </div>
    );
  }

  // ── Main Review Page ─────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Shield className="w-5 h-5 text-blue-600" />
              <span className="text-xs font-semibold text-blue-600 uppercase tracking-wide">
                GSTSense — Secure Review Link
              </span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Notice Response Review</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Please review the AI-drafted GST notice response prepared for your organisation.
            </p>
          </div>
        </div>

        {/* Notice Meta */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Notice Details
          </h2>
          <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-3 text-sm">
            <div>
              <dt className="text-xs text-gray-400 font-medium">Business</dt>
              <dd className="text-gray-800 font-semibold mt-0.5">{data.business_name}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400 font-medium">GSTIN</dt>
              <dd className="text-gray-800 font-mono mt-0.5">{data.gstin}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400 font-medium">Notice Type</dt>
              <dd className="text-gray-800 capitalize mt-0.5">
                {data.notice_type.replace(/_/g, " ")}
              </dd>
            </div>
            {data.tax_period && (
              <div>
                <dt className="text-xs text-gray-400 font-medium">Tax Period</dt>
                <dd className="text-gray-800 mt-0.5">{data.tax_period}</dd>
              </div>
            )}
            {data.demand_amount && (
              <div>
                <dt className="text-xs text-gray-400 font-medium">Demand Amount</dt>
                <dd className="text-gray-800 font-semibold mt-0.5">₹{data.demand_amount}</dd>
              </div>
            )}
            {data.due_date && (
              <div>
                <dt className="text-xs text-gray-400 font-medium">Due Date</dt>
                <dd className="text-red-600 font-semibold mt-0.5">
                  {new Date(data.due_date).toLocaleDateString("en-IN")}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Draft Response */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide flex items-center gap-2">
              <FileText className="w-4 h-4 text-blue-600" />
              AI-Drafted Response
            </h2>
            <span className="text-xs bg-blue-50 text-blue-700 font-semibold px-2 py-0.5 rounded-full">
              Draft · Pending Your Approval
            </span>
          </div>
          <div className="bg-gray-50 rounded-xl p-4">
            <pre className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed font-sans">
              {data.draft_response}
            </pre>
          </div>

          {/* Legal disclaimer */}
          <div className="flex gap-2 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 leading-relaxed">
              <strong>Important:</strong> This response was generated by AI and reviewed by your CA.
              Please read it carefully before approving. Your approval indicates you have reviewed
              and are satisfied with the response content.
            </p>
          </div>
        </div>

        {/* Approval */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Your Decision
          </h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              ICAI Membership Number <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={icaiNumber}
              onChange={(e) => { setIcaiNumber(e.target.value.toUpperCase()); setApproveError(""); }}
              placeholder="e.g. MRN123456 or FRN100001W"
              className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Required for legal compliance. Your membership number will be recorded on the approval.
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Comment (optional)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              placeholder="Add any notes or feedback for your CA…"
              className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
          {approveError && (
            <p className="text-sm text-red-600">{approveError}</p>
          )}
          <div className="flex gap-3">
            <button
              onClick={handleApprove}
              disabled={approving}
              className="flex items-center gap-2 bg-green-600 text-white font-semibold px-6 py-2.5 rounded-xl text-sm hover:bg-green-700 disabled:opacity-60"
            >
              {approving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4" />
              )}
              Approve Response
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-gray-400">
          Powered by{" "}
          <span className="font-semibold text-gray-500">GSTSense</span> — AI-powered GST
          compliance
        </p>
      </div>
    </div>
  );
}
