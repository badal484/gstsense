"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle,
  Clock,
  DollarSign,
  Download,
  Loader2,
  Users,
} from "lucide-react";
import api from "@/lib/api";
import { API_ROUTES } from "@/lib/constants";
import { formatRupees } from "@/lib/utils";

interface CAFirm {
  id: string;
  firm_name: string;
  primary_ca_name: string;
  icai_membership_number: string;
  city: string;
  state: string;
  white_label_subdomain: string | null;
  primary_color: string;
  total_clients: number;
  total_referral_earnings: string;
}

interface DashboardStats {
  total_clients: number;
  active_clients: number;
  total_commissions_pending: string;
  total_commissions_paid: string;
  total_commissions_all_time: string;
  commissions_this_month: string;
  recent_clients: RecentClient[];
  recent_commissions: RecentCommission[];
}

interface RecentClient {
  id: string;
  organization_id: string;
  organization_name: string;
  organization_gstin: string;
  referral_commission_rate: string;
  created_at: string;
}

interface RecentCommission {
  id: string;
  organization_name: string;
  commission_amount: string;
  status: string;
  created_at: string;
}

export default function CADashboardPage() {
  const [firm, setFirm] = useState<CAFirm | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [notRegistered, setNotRegistered] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [firmRes, statsRes] = await Promise.all([
          api.get(API_ROUTES.CA_FIRMS.ME),
          api.get(API_ROUTES.CA_FIRMS.DASHBOARD),
        ]);
        setFirm(firmRes.data.data);
        setStats(statsRes.data.data);
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 403 || status === 404) setNotRegistered(true);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function downloadReport() {
    setDownloadingReport(true);
    try {
      const r = await api.get(API_ROUTES.CA_FIRMS.REPORT, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = "ca_firm_report.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    } finally {
      setDownloadingReport(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
      </div>
    );
  }

  if (notRegistered) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-6">
        <Building2 className="w-16 h-16 text-gray-300 mx-auto" />
        <h1 className="text-2xl font-bold text-gray-900">CA Firm Portal</h1>
        <p className="text-gray-500">
          Register your CA firm to manage client portfolios and earn referral commissions on client
          subscriptions.
        </p>
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-left">
          <p className="text-xs text-amber-800">
            <strong>Requirements:</strong> CA Firm plan required. You will need your ICAI firm
            registration number and membership number.
          </p>
        </div>
        <Link
          href="/ca/register"
          className="inline-flex items-center gap-2 bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
        >
          Register Your CA Firm
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    );
  }

  if (!firm || !stats) return null;

  const statCards = [
    {
      label: "Active Clients",
      value: stats.active_clients,
      icon: <Users className="w-5 h-5 text-blue-600" />,
      bg: "bg-blue-50",
    },
    {
      label: "Pending Commission",
      value: formatRupees(stats.total_commissions_pending),
      icon: <Clock className="w-5 h-5 text-amber-600" />,
      bg: "bg-amber-50",
    },
    {
      label: "Paid Commission",
      value: formatRupees(stats.total_commissions_paid),
      icon: <CheckCircle className="w-5 h-5 text-green-600" />,
      bg: "bg-green-50",
    },
    {
      label: "This Month",
      value: formatRupees(stats.commissions_this_month),
      icon: <DollarSign className="w-5 h-5 text-purple-600" />,
      bg: "bg-purple-50",
    },
  ];

  const statusColors: Record<string, string> = {
    pending: "bg-amber-100 text-amber-700",
    paid: "bg-green-100 text-green-700",
    cancelled: "bg-gray-100 text-gray-600",
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{firm.firm_name}</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            {firm.primary_ca_name} · ICAI {firm.icai_membership_number} · {firm.city},{" "}
            {firm.state}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={downloadReport}
            disabled={downloadingReport}
            className="flex items-center gap-2 border border-gray-200 text-gray-700 font-semibold px-4 py-2.5 rounded-xl text-sm hover:bg-gray-50 disabled:opacity-60 transition-colors"
          >
            {downloadingReport ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Export Report
          </button>
          <Link
            href="/ca/clients"
            className="flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
          >
            <Users className="w-4 h-4" />
            Manage Clients
          </Link>
        </div>
      </div>

      {/* Subdomain banner */}
      {firm.white_label_subdomain && (
        <div className="bg-blue-50 border border-blue-100 rounded-2xl px-4 py-3 flex items-center gap-3">
          <Building2 className="w-4 h-4 text-blue-600 shrink-0" />
          <p className="text-xs text-blue-800">
            White-label portal active at{" "}
            <strong>{firm.white_label_subdomain}.gstsense.in</strong>
          </p>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((c) => (
          <div key={c.label} className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 ${c.bg}`}>
              {c.icon}
            </div>
            <div className="text-xl font-bold text-gray-900">{c.value}</div>
            <div className="text-xs text-gray-500 mt-0.5">{c.label}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Recent clients */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-50">
            <h2 className="font-bold text-gray-900 text-sm">Recent Clients</h2>
            <Link
              href="/ca/clients"
              className="text-xs text-blue-700 font-semibold hover:text-blue-800"
            >
              View all
            </Link>
          </div>
          {stats.recent_clients.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-gray-400">No clients yet</div>
          ) : (
            <div className="divide-y divide-gray-50">
              {stats.recent_clients.map((c) => (
                <div key={c.id} className="flex items-center justify-between px-5 py-3">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{c.organization_name}</div>
                    <div className="text-xs text-gray-400 font-mono">{c.organization_gstin}</div>
                  </div>
                  <span className="text-xs text-gray-500">
                    {(parseFloat(c.referral_commission_rate) * 100).toFixed(1)}% commission
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent commissions */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-50">
            <h2 className="font-bold text-gray-900 text-sm">Recent Commissions</h2>
            <Link
              href="/ca/commissions"
              className="text-xs text-blue-700 font-semibold hover:text-blue-800"
            >
              View all
            </Link>
          </div>
          {stats.recent_commissions.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-gray-400">
              No commissions yet
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {stats.recent_commissions.map((c) => (
                <div key={c.id} className="flex items-center justify-between px-5 py-3">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{c.organization_name}</div>
                    <div className="text-xs text-gray-400">
                      {new Date(c.created_at).toLocaleDateString("en-IN")}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900">
                      {formatRupees(c.commission_amount)}
                    </span>
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColors[c.status] ?? "bg-gray-100 text-gray-600"}`}
                    >
                      {c.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
