"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle,
  Clock,
  DollarSign,
  Loader2,
} from "lucide-react";
import api from "@/lib/api";
import { API_ROUTES } from "@/lib/constants";
import { formatRupees } from "@/lib/utils";

interface Commission {
  id: string;
  organization_id: string;
  organization_name: string;
  payment_id: string;
  commission_amount: string;
  commission_rate: string;
  status: string;
  payout_date: string | null;
  created_at: string;
}

interface Summary {
  total_pending: string;
  total_paid: string;
  total_cancelled: string;
  count_pending: number;
  count_paid: number;
}

const STATUS_FILTER_OPTIONS = [
  { value: "", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "paid", label: "Paid" },
  { value: "cancelled", label: "Cancelled" },
];

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  paid: "bg-green-100 text-green-700",
  cancelled: "bg-gray-100 text-gray-600",
};

export default function CommissionsPage() {
  const [commissions, setCommissions] = useState<Commission[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [markingId, setMarkingId] = useState<string | null>(null);

  async function loadData() {
    try {
      const url = filter
        ? `${API_ROUTES.CA_FIRMS.COMMISSIONS}?commission_status=${filter}`
        : API_ROUTES.CA_FIRMS.COMMISSIONS;
      const [comRes, sumRes] = await Promise.all([
        api.get(url),
        api.get(API_ROUTES.CA_FIRMS.COMMISSION_SUMMARY),
      ]);
      setCommissions(comRes.data.data);
      setSummary(sumRes.data.data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function markPaid(commissionId: string) {
    setMarkingId(commissionId);
    try {
      await api.post(API_ROUTES.CA_FIRMS.MARK_PAID(commissionId));
      await loadData();
    } catch {
      // ignore
    } finally {
      setMarkingId(null);
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Referral Commissions</h1>
        <p className="text-gray-500 text-sm mt-0.5">
          Track earnings from client subscription payments
        </p>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-amber-600" />
              <span className="text-sm font-semibold text-gray-700">Pending</span>
            </div>
            <p className="text-2xl font-bold text-amber-700">
              {formatRupees(summary.total_pending)}
            </p>
            <p className="text-xs text-gray-400 mt-1">{summary.count_pending} commission(s)</p>
          </div>
          <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="text-sm font-semibold text-gray-700">Paid Out</span>
            </div>
            <p className="text-2xl font-bold text-green-700">
              {formatRupees(summary.total_paid)}
            </p>
            <p className="text-xs text-gray-400 mt-1">{summary.count_paid} commission(s)</p>
          </div>
          <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm col-span-2 lg:col-span-1">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-semibold text-gray-700">All Time</span>
            </div>
            <p className="text-2xl font-bold text-blue-700">
              {formatRupees(
                (parseFloat(summary.total_paid) + parseFloat(summary.total_pending)).toString()
              )}
            </p>
            <p className="text-xs text-gray-400 mt-1">Total earned</p>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2">
        {STATUS_FILTER_OPTIONS.map((o) => (
          <button
            key={o.value}
            onClick={() => setFilter(o.value)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              filter === o.value
                ? "bg-blue-700 text-white"
                : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
        </div>
      )}

      {!loading && commissions.length === 0 && (
        <div className="bg-white border border-gray-100 rounded-2xl p-14 text-center shadow-sm">
          <DollarSign className="w-14 h-14 text-gray-300 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-gray-900 mb-2">No commissions yet</h2>
          <p className="text-gray-500 text-sm max-w-sm mx-auto">
            Commissions appear automatically when your clients make subscription payments.
          </p>
        </div>
      )}

      {!loading && commissions.length > 0 && (
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Client", "Amount", "Rate", "Status", "Date", "Payout Date", "Action"].map(
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
              {commissions.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {c.organization_name}
                  </td>
                  <td className="px-4 py-3 text-sm font-semibold text-gray-900">
                    {formatRupees(c.commission_amount)}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {(parseFloat(c.commission_rate) * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-600"}`}
                    >
                      {c.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(c.created_at).toLocaleDateString("en-IN")}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {c.payout_date
                      ? new Date(c.payout_date).toLocaleDateString("en-IN")
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {c.status === "pending" ? (
                      <button
                        onClick={() => markPaid(c.id)}
                        disabled={markingId === c.id}
                        className="text-xs font-semibold text-green-700 hover:text-green-800 disabled:opacity-60 flex items-center gap-1"
                      >
                        {markingId === c.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <CheckCircle className="w-3 h-3" />
                        )}
                        Mark Paid
                      </button>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
