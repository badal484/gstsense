"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSearch,
  Loader2,
  RefreshCw,
  Upload,
} from "lucide-react";
import api from "@/lib/api";
import { API_ROUTES, ROUTES } from "@/lib/constants";
import { formatRupees, formatMonth, getRiskLevel } from "@/lib/utils";
import { Scan } from "@/types";

const PAGE_SIZE = 10;

const STATUS_BADGE: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  processing: "bg-blue-100 text-blue-700",
  failed: "bg-red-100 text-red-700",
  uploaded: "bg-gray-100 text-gray-600",
};

function SkeletonRow() {
  return (
    <tr>
      {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-gray-100 rounded animate-pulse" />
        </td>
      ))}
    </tr>
  );
}

export default function ScanHistoryPage() {
  const router = useRouter();
  const [scans, setScans] = useState<Scan[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [paidFilter, setPaidFilter] = useState("");

  async function loadScans(p: number, sf: string) {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page: p, limit: PAGE_SIZE };
      if (sf) params.status_filter = sf;
      const r = await api.get(API_ROUTES.SCANS.LIST, { params });
      const data = r.data.data;
      setScans(data.scans ?? []);
      setTotal(data.total ?? 0);
    } catch {
      setScans([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadScans(page, statusFilter);
  }, [page, statusFilter]);

  async function downloadPdf(scanId: string) {
    setDownloadingId(scanId);
    try {
      const r = await api.get(API_ROUTES.SCANS.DOWNLOAD(scanId));
      const url = r.data?.download_url;
      if (url) {
        const a = document.createElement("a");
        a.href = url;
        a.download = `gstsense_report_${scanId.slice(0, 8)}.pdf`;
        a.click();
      }
    } catch {
      // ignore
    } finally {
      setDownloadingId(null);
    }
  }

  // paidFilter is client-side only (backend has no paid filter param)
  const filtered = scans.filter((s) => {
    if (paidFilter === "paid" && !s.is_paid) return false;
    if (paidFilter === "free" && s.is_paid) return false;
    return true;
  });

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Scan History</h1>
        <p className="text-gray-500 text-sm mt-0.5">All your GST reconciliation scans</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">All Statuses</option>
          <option value="completed">Completed</option>
          <option value="processing">Processing</option>
          <option value="uploaded">Uploaded</option>
          <option value="failed">Failed</option>
        </select>
        <select
          value={paidFilter}
          onChange={(e) => setPaidFilter(e.target.value)}
          className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">All Reports</option>
          <option value="paid">Paid Reports</option>
          <option value="free">Free Previews</option>
        </select>
        {(statusFilter || paidFilter) && (
          <button
            onClick={() => {
              setStatusFilter("");
              setPaidFilter("");
            }}
            className="text-sm text-gray-500 hover:text-gray-700 px-3 py-2 border border-gray-200 rounded-xl"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
        {!loading && filtered.length === 0 && !statusFilter && !paidFilter ? (
          <div className="px-5 py-16 text-center">
            <FileSearch className="w-14 h-14 text-gray-300 mx-auto mb-4" />
            <h2 className="text-lg font-bold text-gray-900 mb-2">No scans yet</h2>
            <p className="text-gray-500 text-sm max-w-sm mx-auto mb-6">
              Upload your GSTR files to run your first compliance scan.
            </p>
            <Link
              href={ROUTES.SCAN}
              className="inline-flex items-center gap-2 bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-xl text-sm hover:bg-blue-800"
            >
              <Upload className="w-4 h-4" />
              Run First Scan
            </Link>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    {["Period", "Invoices", "Mismatches", "Rupee Risk", "Status", "Paid", "Date", "Actions"].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap"
                        >
                          {h}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {loading
                    ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
                    : filtered.map((s) => {
                        const risk = getRiskLevel(s.total_rupee_risk);
                        return (
                          <tr key={s.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">
                              {formatMonth(s.scan_month)}
                            </td>
                            <td className="px-4 py-3 text-gray-600">
                              {s.total_invoices_scanned?.toLocaleString() ?? "—"}
                            </td>
                            <td className="px-4 py-3 text-gray-600">{s.total_mismatches}</td>
                            <td className="px-4 py-3">
                              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${risk.bgColor} ${risk.color}`}>
                                {formatRupees(s.total_rupee_risk)}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_BADGE[s.status] ?? "bg-gray-100 text-gray-600"}`}
                              >
                                {s.status}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              {s.is_paid ? (
                                <span className="text-xs font-semibold bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                                  Full Report
                                </span>
                              ) : (
                                <span className="text-xs font-semibold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                                  Preview
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                              {new Date(s.created_at).toLocaleDateString("en-IN")}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                {s.status === "completed" && s.is_paid && (
                                  <>
                                    <Link
                                      href={ROUTES.SCAN_REPORT(s.id)}
                                      className="text-xs font-semibold text-blue-700 hover:text-blue-800 whitespace-nowrap"
                                    >
                                      View Report
                                    </Link>
                                    <button
                                      onClick={() => downloadPdf(s.id)}
                                      disabled={downloadingId === s.id}
                                      className="p-1 text-gray-400 hover:text-blue-600 disabled:opacity-40"
                                      title="Download PDF"
                                    >
                                      {downloadingId === s.id ? (
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                      ) : (
                                        <Download className="w-3.5 h-3.5" />
                                      )}
                                    </button>
                                  </>
                                )}
                                {s.status === "completed" && !s.is_paid && (
                                  <Link
                                    href={`${ROUTES.SCAN_PREVIEW}?scan_id=${s.id}`}
                                    className="text-xs font-semibold text-purple-700 hover:text-purple-800 whitespace-nowrap"
                                  >
                                    Unlock ₹499
                                  </Link>
                                )}
                                {s.status === "processing" && (
                                  <Link
                                    href={ROUTES.SCAN_PROCESSING}
                                    className="text-xs text-blue-600 whitespace-nowrap"
                                  >
                                    View Progress
                                  </Link>
                                )}
                                {s.status === "failed" && (
                                  <div className="flex items-center gap-1.5">
                                    <Link
                                      href={ROUTES.SCAN}
                                      className="text-xs font-semibold text-red-600 hover:text-red-700 whitespace-nowrap"
                                    >
                                      Retry
                                    </Link>
                                    {s.error_message && (
                                      <span
                                        title={s.error_message}
                                        className="cursor-help"
                                      >
                                        <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                                      </span>
                                    )}
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {total > PAGE_SIZE && (
              <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                <span>
                  Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of{" "}
                  {total} scans
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-1 rounded-lg hover:bg-gray-100 disabled:opacity-40"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="px-2 font-medium">
                    {page} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="p-1 rounded-lg hover:bg-gray-100 disabled:opacity-40"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
