"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Clock,
  FileText,
  IndianRupee,
  Loader2,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
  Upload,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import api from "@/lib/api";
import { API_ROUTES, ROUTES } from "@/lib/constants";
import { formatRupees, formatMonth, getNextGSTDeadlines } from "@/lib/utils";
import { ComplianceScoreWidget } from "@/components/shared/ComplianceScoreWidget";

interface DashboardData {
  compliance_score: number;
  compliance_grade: string;
  compliance_color: string;
  compliance_factors: Array<{
    name: string;
    status: "good" | "warning" | "critical";
    description: string;
    points: string;
  }>;
  recommendations: string[];
  total_scans: number;
  total_mismatches_found: number;
  total_rupee_risk_found: string;
  total_itc_recovered: string;
  scans_this_month: number;
  invoice_limit: number;
  invoices_used_this_month: number;
  invoice_usage_percentage: number;
  next_gstr1_deadline: string;
  next_gstr3b_deadline: string;
  days_to_gstr1: number;
  days_to_gstr3b: number;
  recent_scans: Array<{
    id: string;
    scan_month: string;
    total_mismatches: number;
    total_rupee_risk: string;
    status: string;
    is_paid: boolean;
    created_at: string;
  }>;
  pending_notices: number;
}

function DeadlineChip({
  label,
  date,
  days,
}: {
  label: string;
  date: string;
  days: number;
}) {
  const urgent = days <= 3;
  const warning = days <= 7;
  return (
    <div
      className={`rounded-xl border px-3 py-2 ${
        urgent
          ? "bg-red-50 border-red-200"
          : warning
          ? "bg-amber-50 border-amber-200"
          : "bg-green-50 border-green-200"
      }`}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <Clock
          className={`w-3.5 h-3.5 ${
            urgent ? "text-red-500" : warning ? "text-amber-500" : "text-green-600"
          }`}
        />
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-sm font-bold text-gray-900">{date}</div>
      <div
        className={`text-xs font-semibold ${
          urgent ? "text-red-600" : warning ? "text-amber-600" : "text-green-700"
        }`}
      >
        {days === 0 ? "Due today!" : `${days} days`}
      </div>
    </div>
  );
}

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={`bg-gray-100 rounded-xl animate-pulse ${className ?? ""}`} />;
}

function LoadingSkeleton() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <SkeletonBlock className="h-16 w-80" />
      <div className="grid lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <SkeletonBlock className="h-72" />
        </div>
        <div className="lg:col-span-3 grid grid-cols-2 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonBlock key={i} className="h-28" />
          ))}
        </div>
      </div>
      <SkeletonBlock className="h-10" />
      <SkeletonBlock className="h-48" />
    </div>
  );
}

const STATUS_BADGE: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  processing: "bg-blue-100 text-blue-700",
  failed: "bg-red-100 text-red-700",
  uploaded: "bg-gray-100 text-gray-600",
};

export default function DashboardPage() {
  const { user, organization } = useAuthStore();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  async function load() {
    setLoading(true);
    setError(false);
    try {
      const r = await api.get(API_ROUTES.DASHBOARD);
      setData(r.data.data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  if (loading) return <LoadingSkeleton />;

  if (error) {
    return (
      <div className="max-w-6xl mx-auto flex flex-col items-center justify-center py-24 gap-4">
        <AlertTriangle className="w-12 h-12 text-red-400" />
        <p className="text-gray-600">Failed to load dashboard. Please try again.</p>
        <button
          onClick={load}
          className="flex items-center gap-2 bg-blue-700 text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-blue-800"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const usagePct = data.invoice_usage_percentage;
  const usageColor =
    usagePct >= 100 ? "bg-red-500" : usagePct >= 80 ? "bg-amber-500" : "bg-blue-600";

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* ROW 1 — Welcome + Deadlines */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {greeting}, {user?.full_name?.split(" ")[0] ?? "there"}
          </h1>
          <p className="text-gray-500 text-sm mt-0.5">
            {organization?.business_name} —{" "}
            <span className="capitalize">{organization?.plan ?? "Free"}</span> Plan
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <DeadlineChip
              label="GSTR-1"
              date={data.next_gstr1_deadline}
              days={data.days_to_gstr1}
            />
            <DeadlineChip
              label="GSTR-3B"
              date={data.next_gstr3b_deadline}
              days={data.days_to_gstr3b}
            />
          </div>
          <Link
            href={ROUTES.SCAN}
            className="flex items-center justify-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2 rounded-xl text-sm hover:bg-blue-800 transition-colors"
          >
            <Upload className="w-4 h-4" />
            New Scan
          </Link>
        </div>
      </div>

      {/* ROW 2 — Compliance score + stats */}
      <div className="grid lg:grid-cols-5 gap-6">
        {/* Compliance score */}
        <div className="lg:col-span-2 bg-white border border-gray-100 rounded-2xl p-6 shadow-sm">
          <h2 className="text-sm font-bold text-gray-700 mb-4">Compliance Health</h2>
          <ComplianceScoreWidget
            score={data.compliance_score}
            grade={data.compliance_grade}
            color={data.compliance_color}
            factors={data.compliance_factors}
            recommendations={data.recommendations}
            size="lg"
            showDetails={true}
          />
        </div>

        {/* Stat cards */}
        <div className="lg:col-span-3 grid grid-cols-2 gap-4">
          {[
            {
              label: "Total Scans",
              value: data.total_scans,
              icon: <FileText className="w-5 h-5 text-blue-600" />,
              sub: `${data.scans_this_month} this month`,
              bg: "bg-blue-50",
            },
            {
              label: "Mismatches Found",
              value: data.total_mismatches_found,
              icon: <AlertTriangle className="w-5 h-5 text-amber-600" />,
              sub: "across all scans",
              bg: "bg-amber-50",
            },
            {
              label: "Total Rupee Risk",
              value: formatRupees(data.total_rupee_risk_found),
              icon: <IndianRupee className="w-5 h-5 text-red-600" />,
              sub: "identified exposure",
              bg: "bg-red-50",
            },
            {
              label: "ITC Recoverable",
              value: formatRupees(data.total_itc_recovered),
              icon: <ShieldCheck className="w-5 h-5 text-green-600" />,
              sub: "unclaimed credit",
              bg: "bg-green-50",
            },
          ].map((c) => (
            <div key={c.label} className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 ${c.bg}`}>
                {c.icon}
              </div>
              <div className="text-xl font-bold text-gray-900">{c.value}</div>
              <div className="text-xs text-gray-500 mt-0.5">{c.label}</div>
              <div className="text-xs text-gray-400 mt-0.5">{c.sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ROW 3 — Invoice usage */}
      <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-semibold text-gray-800">Invoice Usage This Month</p>
            <p className="text-xs text-gray-400">
              {data.invoices_used_this_month.toLocaleString()} of{" "}
              {data.invoice_limit.toLocaleString()} invoices used
            </p>
          </div>
          <span className="text-sm font-bold text-gray-900">{usagePct.toFixed(0)}%</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2.5">
          <div
            className={`h-2.5 rounded-full transition-all ${usageColor}`}
            style={{ width: `${Math.min(usagePct, 100)}%` }}
          />
        </div>
        {usagePct >= 100 && (
          <div className="mt-3 flex items-center justify-between">
            <p className="text-xs text-red-600 font-semibold">Invoice limit reached</p>
            <Link
              href={ROUTES.SETTINGS}
              className="text-xs text-blue-700 font-semibold hover:text-blue-800"
            >
              Upgrade plan →
            </Link>
          </div>
        )}
        {usagePct >= 80 && usagePct < 100 && (
          <p className="text-xs text-amber-600 font-semibold mt-2">
            Approaching invoice limit — consider upgrading
          </p>
        )}
      </div>

      {/* ROW 4 — Recent scans */}
      <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-50">
          <h2 className="font-bold text-gray-900 text-sm">Recent Scans</h2>
          <Link
            href="/dashboard/history"
            className="text-xs text-blue-700 font-semibold hover:text-blue-800"
          >
            View all
          </Link>
        </div>
        {data.recent_scans.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <FileText className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500 mb-4">No scans yet</p>
            <Link
              href={ROUTES.SCAN}
              className="inline-flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2 rounded-xl text-sm hover:bg-blue-800"
            >
              <Upload className="w-4 h-4" />
              Run Your First Scan
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Period", "Mismatches", "Risk", "Status", "Action"].map((h) => (
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
              {data.recent_scans.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {formatMonth(s.scan_month)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{s.total_mismatches}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {formatRupees(s.total_rupee_risk)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_BADGE[s.status] ?? "bg-gray-100 text-gray-600"}`}
                    >
                      {s.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {s.status === "completed" && s.is_paid ? (
                      <Link
                        href={ROUTES.SCAN_REPORT(s.id)}
                        className="text-xs font-semibold text-blue-700 hover:text-blue-800"
                      >
                        View Report
                      </Link>
                    ) : s.status === "completed" ? (
                      <Link
                        href={ROUTES.SCAN_REPORT(s.id)}
                        className="text-xs font-semibold text-purple-700 hover:text-purple-800"
                      >
                        Unlock ₹499
                      </Link>
                    ) : (
                      <span className="text-xs text-gray-400 italic">{s.status}…</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ROW 5 — CTA */}
      {data.total_scans > 0 && (
        <div className="grid sm:grid-cols-2 gap-4">
          <Link
            href={ROUTES.SCAN}
            className="bg-blue-700 text-white rounded-2xl p-5 flex items-center justify-between hover:bg-blue-800 transition-colors group"
          >
            <div>
              <p className="font-bold text-base">Run a New Scan</p>
              <p className="text-blue-100 text-xs mt-0.5">Check your latest GSTR files</p>
            </div>
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </Link>
          <Link
            href={ROUTES.ITC}
            className="bg-green-700 text-white rounded-2xl p-5 flex items-center justify-between hover:bg-green-800 transition-colors group"
          >
            <div>
              <p className="font-bold text-base">Recover ITC</p>
              <p className="text-green-100 text-xs mt-0.5">Claim unclaimed input tax credits</p>
            </div>
            <ShieldCheck className="w-5 h-5 group-hover:scale-110 transition-transform" />
          </Link>
        </div>
      )}

      {data.pending_notices > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
            <p className="text-sm text-amber-800 font-medium">
              You have {data.pending_notices} pending GST notice(s) requiring attention.
            </p>
          </div>
          <Link
            href={ROUTES.NOTICES}
            className="text-xs font-bold text-amber-800 border border-amber-400 px-3 py-1.5 rounded-lg hover:bg-amber-100 whitespace-nowrap"
          >
            View Notices
          </Link>
        </div>
      )}
    </div>
  );
}
