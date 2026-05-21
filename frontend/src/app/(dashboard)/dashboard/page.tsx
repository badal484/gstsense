"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Upload,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  ArrowRight,
  FileSpreadsheet,
  IndianRupee,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { orgApi, scanApi } from "@/lib/api";
import { UsageStats, Scan } from "@/types";
import { ROUTES } from "@/lib/constants";
import { formatRupees, formatMonth, formatDate, getRiskLevel, getNextGSTDeadlines } from "@/lib/utils";

function StatCard({
  label,
  value,
  icon,
  sub,
  color = "blue",
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  sub?: string;
  color?: "blue" | "green" | "orange" | "red";
}) {
  const colorMap = {
    blue: "bg-blue-50 text-blue-700",
    green: "bg-green-50 text-green-700",
    orange: "bg-orange-50 text-orange-700",
    red: "bg-red-50 text-red-700",
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-500">{label}</span>
        <div className={`p-2 rounded-xl ${colorMap[color]}`}>{icon}</div>
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

function DeadlineCard({
  label,
  dateStr,
  daysLeft,
}: {
  label: string;
  dateStr: string;
  daysLeft: number;
}) {
  const urgent = daysLeft <= 5;
  const warning = daysLeft <= 10;

  return (
    <div
      className={`rounded-xl border p-4 ${
        urgent
          ? "bg-red-50 border-red-200"
          : warning
          ? "bg-orange-50 border-orange-200"
          : "bg-gray-50 border-gray-100"
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <Clock className={`w-4 h-4 ${urgent ? "text-red-500" : warning ? "text-orange-500" : "text-gray-400"}`} />
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</span>
      </div>
      <div className="font-bold text-gray-900">{dateStr}</div>
      <div
        className={`text-xs font-semibold mt-0.5 ${
          urgent ? "text-red-600" : warning ? "text-orange-600" : "text-gray-500"
        }`}
      >
        {daysLeft === 0 ? "Due today!" : `${daysLeft} days left`}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user, organization } = useAuthStore();
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [recentScans, setRecentScans] = useState<Scan[]>([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const deadlines = getNextGSTDeadlines();

  const gstr1DateStr = deadlines.gstr1.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const gstr3bDateStr = deadlines.gstr3b.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  useEffect(() => {
    async function load() {
      try {
        const [statsRes, scansRes] = await Promise.all([
          orgApi.getStats(),
          scanApi.listScans(1, 5),
        ]);
        setStats(statsRes.data.data ?? null);
        setRecentScans(scansRes.data.data?.scans ?? []);
      } catch {
        // errors handled by interceptor
      } finally {
        setLoadingStats(false);
      }
    }
    load();
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Good day, {user?.full_name.split(" ")[0]}
          </h1>
          {organization && (
            <p className="text-gray-500 text-sm mt-1">
              {organization.business_name} · GSTIN {organization.gstin}
            </p>
          )}
        </div>
        <Link
          href={ROUTES.SCAN}
          className="flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
        >
          <Upload className="w-4 h-4" />
          New Scan
        </Link>
      </div>

      {/* GST Deadlines */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Upcoming GST Deadlines
        </h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <DeadlineCard label="GSTR-1" dateStr={gstr1DateStr} daysLeft={deadlines.daysToGstr1} />
          <DeadlineCard label="GSTR-3B" dateStr={gstr3bDateStr} daysLeft={deadlines.daysToGstr3b} />
        </div>
      </div>

      {/* Stats */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Your Activity
        </h2>
        {loadingStats ? (
          <div className="grid sm:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-white rounded-2xl border border-gray-100 p-6 h-28 animate-pulse" />
            ))}
          </div>
        ) : stats ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Total Scans"
              value={stats.total_scans}
              icon={<FileSpreadsheet className="w-5 h-5" />}
              color="blue"
            />
            <StatCard
              label="Scans This Month"
              value={stats.scans_this_month}
              icon={<TrendingUp className="w-5 h-5" />}
              color="green"
            />
            <StatCard
              label="Total Mismatches Found"
              value={stats.total_mismatches}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="orange"
            />
            <StatCard
              label="Total Rupee Risk"
              value={formatRupees(stats.total_rupee_risk)}
              icon={<IndianRupee className="w-5 h-5" />}
              sub="across all scans"
              color="red"
            />
          </div>
        ) : null}
      </div>

      {/* Recent scans */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Recent Scans</h2>
        </div>

        {recentScans.length === 0 ? (
          <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-12 text-center">
            <FileSpreadsheet className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <h3 className="font-semibold text-gray-700 mb-1">No scans yet</h3>
            <p className="text-sm text-gray-400 mb-4">
              Upload your GSTR-1 and GSTR-3B files to get started.
            </p>
            <Link
              href={ROUTES.SCAN}
              className="inline-flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2 rounded-xl text-sm hover:bg-blue-800 transition-colors"
            >
              <Upload className="w-4 h-4" />
              Start Your First Scan
            </Link>
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm divide-y divide-gray-50">
            {recentScans.map((scan: Scan) => {
              const risk = getRiskLevel(scan.total_rupee_risk ?? "0");
              const isPaid = scan.is_paid;
              const isCompleted = scan.status === "completed";

              return (
                <div
                  key={scan.id}
                  className="flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-2 h-2 rounded-full ${risk.bgColor}`} />
                    <div>
                      <div className="font-semibold text-gray-900 text-sm">
                        {formatMonth(scan.scan_month)}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {formatDate(scan.created_at)} ·{" "}
                        {scan.total_mismatches != null
                          ? `${scan.total_mismatches} mismatch${scan.total_mismatches !== 1 ? "es" : ""}`
                          : "Processing"}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {scan.total_rupee_risk != null && (
                      <span className={`text-sm font-semibold ${risk.color}`}>
                        {formatRupees(scan.total_rupee_risk)}
                      </span>
                    )}

                    {isCompleted && isPaid ? (
                      <Link
                        href={ROUTES.SCAN_REPORT(scan.id)}
                        className="flex items-center gap-1 text-xs font-semibold text-blue-700 hover:underline"
                      >
                        View Report <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    ) : isCompleted && !isPaid ? (
                      <Link
                        href={ROUTES.SCAN_PREVIEW}
                        className="flex items-center gap-1 text-xs font-semibold text-orange-600 hover:underline"
                      >
                        Unlock <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    ) : scan.status === "failed" ? (
                      <span className="text-xs text-red-500 font-medium">Failed</span>
                    ) : (
                      <span className="text-xs text-gray-400 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" /> Processing
                      </span>
                    )}

                    {isCompleted && scan.total_mismatches === 0 && (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
