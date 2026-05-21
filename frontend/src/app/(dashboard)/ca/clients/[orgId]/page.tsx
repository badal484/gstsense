"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  CheckCircle,
  Clock,
  DollarSign,
  Loader2,
  Trash2,
} from "lucide-react";
import api from "@/lib/api";
import { API_ROUTES } from "@/lib/constants";
import { formatRupees } from "@/lib/utils";

interface ClientDetail {
  id: string;
  organization_id: string;
  organization_name: string;
  organization_gstin: string;
  status: string;
  referral_commission_rate: string;
  created_at: string;
}

interface Commission {
  id: string;
  commission_amount: string;
  commission_rate: string;
  status: string;
  payout_date: string | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  paid: "bg-green-100 text-green-700",
  cancelled: "bg-gray-100 text-gray-600",
};

export default function ClientDetailPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const router = useRouter();
  const [client, setClient] = useState<ClientDetail | null>(null);
  const [commissions, setCommissions] = useState<Commission[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [clientRes, comRes] = await Promise.all([
          api.get(API_ROUTES.CA_FIRMS.CLIENT(orgId)),
          api.get(`${API_ROUTES.CA_FIRMS.COMMISSIONS}?organization_id=${orgId}`),
        ]);
        setClient(clientRes.data.data);
        setCommissions(comRes.data.data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [orgId]);

  async function handleRemove() {
    if (!confirm("Remove this client from your firm? Commission tracking will stop.")) return;
    setRemoving(true);
    try {
      await api.delete(API_ROUTES.CA_FIRMS.CLIENT(orgId));
      router.push("/ca/clients");
    } catch {
      setRemoving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
      </div>
    );
  }

  if (!client) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center">
        <p className="text-gray-500">Client not found.</p>
      </div>
    );
  }

  const totalCommissions = commissions.reduce(
    (sum, c) => sum + parseFloat(c.commission_amount),
    0
  );
  const pendingCommissions = commissions
    .filter((c) => c.status === "pending")
    .reduce((sum, c) => sum + parseFloat(c.commission_amount), 0);
  const paidCommissions = commissions
    .filter((c) => c.status === "paid")
    .reduce((sum, c) => sum + parseFloat(c.commission_amount), 0);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Clients
      </button>

      {/* Client header */}
      <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-50 rounded-2xl flex items-center justify-center">
              <Building2 className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{client.organization_name}</h1>
              <p className="text-sm text-gray-500 font-mono">{client.organization_gstin}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs bg-green-100 text-green-700 font-semibold px-2.5 py-1 rounded-full">
              {client.status}
            </span>
            <button
              onClick={handleRemove}
              disabled={removing}
              className="flex items-center gap-1.5 text-xs text-red-600 border border-red-200 px-3 py-1.5 rounded-lg hover:bg-red-50 disabled:opacity-60 transition-colors"
            >
              {removing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
              Remove Client
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-gray-400">Commission Rate</p>
            <p className="text-sm font-semibold text-gray-900">
              {(parseFloat(client.referral_commission_rate) * 100).toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Added On</p>
            <p className="text-sm font-semibold text-gray-900">
              {new Date(client.created_at).toLocaleDateString("en-IN")}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Total Commissions</p>
            <p className="text-sm font-semibold text-gray-900">
              {formatRupees(totalCommissions.toString())}
            </p>
          </div>
        </div>
      </div>

      {/* Commission summary */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-amber-600" />
            <span className="text-sm font-semibold text-gray-700">Pending</span>
          </div>
          <p className="text-2xl font-bold text-amber-700">
            {formatRupees(pendingCommissions.toString())}
          </p>
        </div>
        <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <span className="text-sm font-semibold text-gray-700">Paid Out</span>
          </div>
          <p className="text-2xl font-bold text-green-700">
            {formatRupees(paidCommissions.toString())}
          </p>
        </div>
      </div>

      {/* Commission history */}
      <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-50">
          <h2 className="font-bold text-gray-900 text-sm">Commission History</h2>
        </div>
        {commissions.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-gray-400">
            No commissions earned yet. They appear when this client makes a subscription payment.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Date", "Amount", "Rate", "Status", "Paid On"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {commissions.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50/50">
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(c.created_at).toLocaleDateString("en-IN")}
                  </td>
                  <td className="px-4 py-3 text-xs font-semibold text-gray-900">
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
                    {c.payout_date
                      ? new Date(c.payout_date).toLocaleDateString("en-IN")
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
