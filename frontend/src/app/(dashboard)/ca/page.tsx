"use client";

import { useEffect, useState, FormEvent } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle,
  Clock,
  IndianRupee,
  Download,
  Loader2,
  Users,
} from "lucide-react";
import api from "@/lib/api";
import { API_ROUTES } from "@/lib/constants";
import { formatRupees } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { useSubscriptionPayment } from "@/hooks/useSubscriptionPayment";

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

interface SetupFormData {
  firm_name: string;
  icai_firm_registration_number: string;
  primary_ca_name: string;
  icai_membership_number: string;
  phone: string;
  city: string;
  state: string;
  white_label_subdomain: string;
  primary_color: string;
}

const EMPTY_FORM: SetupFormData = {
  firm_name: "",
  icai_firm_registration_number: "",
  primary_ca_name: "",
  icai_membership_number: "",
  phone: "",
  city: "",
  state: "",
  white_label_subdomain: "",
  primary_color: "#534AB7",
};

const INDIAN_STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
  "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
  "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

export default function CADashboardPage() {
  const { organization, user } = useAuthStore();
  const { initiateSubscription, isLoading: upgrading, error: upgradeError } = useSubscriptionPayment();
  const [upgradeMsg, setUpgradeMsg] = useState("");

  const [firm, setFirm] = useState<CAFirm | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [notRegistered, setNotRegistered] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [reportPolling, setReportPolling] = useState(false);

  // Setup Form State
  const [setupForm, setSetupForm] = useState<SetupFormData>(EMPTY_FORM);
  const [setupErrors, setSetupErrors] = useState<Partial<SetupFormData>>({});
  const [setupSubmitting, setSetupSubmitting] = useState(false);
  const [setupApiError, setSetupApiError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [firmRes, statsRes] = await Promise.all([
        api.get(API_ROUTES.CA_FIRMS.ME),
        api.get(API_ROUTES.CA_FIRMS.DASHBOARD),
      ]);
      const firmData = firmRes.data?.data ?? firmRes.data;
      const statsData = statsRes.data?.data ?? statsRes.data;
      if (!firmData || !statsData) {
        setNotRegistered(true);
      } else {
        setFirm(firmData);
        setStats(statsData);
        setNotRegistered(false);
      }
    } catch {
      setNotRegistered(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (organization?.plan === "ca_firm") {
      load();
    } else {
      setLoading(false);
    }
  }, [organization?.plan]);

  // Setup Form Handlers
  function setSetupField(field: keyof SetupFormData, value: string) {
    setSetupForm((prev) => ({ ...prev, [field]: value }));
    setSetupErrors((prev) => ({ ...prev, [field]: undefined }));
    setSetupApiError("");
  }

  function validateSetup(): boolean {
    const e: Partial<SetupFormData> = {};
    if (!setupForm.firm_name.trim()) e.firm_name = "Firm name is required";
    if (!setupForm.icai_firm_registration_number.trim())
      e.icai_firm_registration_number = "ICAI firm registration number is required";
    if (!setupForm.primary_ca_name.trim()) e.primary_ca_name = "Primary CA name is required";
    if (!setupForm.icai_membership_number.trim())
      e.icai_membership_number = "ICAI membership number is required";
    if (!setupForm.city.trim()) e.city = "City is required";
    if (!setupForm.state) e.state = "State is required";
    if (setupForm.white_label_subdomain && !/^[a-z0-9-]+$/.test(setupForm.white_label_subdomain))
      e.white_label_subdomain = "Only lowercase letters, numbers, and hyphens allowed";
    setSetupErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSetupSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validateSetup()) return;
    setSetupSubmitting(true);
    setSetupApiError("");
    try {
      await api.post(API_ROUTES.CA_FIRMS.REGISTER, {
        firm_name: setupForm.firm_name.trim(),
        icai_firm_registration_number: setupForm.icai_firm_registration_number.trim().toUpperCase(),
        primary_ca_name: setupForm.primary_ca_name.trim(),
        icai_membership_number: setupForm.icai_membership_number.trim().toUpperCase(),
        phone: setupForm.phone.trim() || undefined,
        city: setupForm.city.trim(),
        state: setupForm.state,
        white_label_subdomain: setupForm.white_label_subdomain.trim() || undefined,
        primary_color: setupForm.primary_color,
      });
      // Load dashboard details directly on success
      await load();
    } catch (err) {
      setSetupApiError(err instanceof Error ? err.message : "Registration failed. Please try again.");
    } finally {
      setSetupSubmitting(false);
    }
  }

  async function downloadReport() {
    setDownloadingReport(true);
    try {
      const jobRes = await api.post(API_ROUTES.CA_FIRMS.REPORT);
      const jobId: string = jobRes.data?.data?.job_id;
      if (!jobId) throw new Error("No job_id returned");

      setReportPolling(true);
      const deadline = Date.now() + 60_000;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2500));
        const pollRes = await api.get(`/api/v1/ca-firms/me/report/${jobId}`);
        const result = pollRes.data?.data;
        if (result?.status === "completed" && result.download_url) {
          const a = document.createElement("a");
          a.href = result.download_url;
          a.download = "ca_firm_report.pdf";
          a.click();
          break;
        }
        if (result?.status === "failed") break;
      }
    } catch {
      // ignore
    } finally {
      setDownloadingReport(false);
      setReportPolling(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
      </div>
    );
  }

  // 1. Plan Gating Screen
  if (organization?.plan !== "ca_firm") {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-8 animate-fadeIn">
        <div className="w-16 h-16 bg-blue-100 rounded-3xl flex items-center justify-center mx-auto shadow-inner animate-pulse">
          <Building2 className="w-8 h-8 text-blue-700" />
        </div>
        <div className="space-y-3">
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">CA Firm Portal</h1>
          <p className="text-gray-500 text-lg max-w-lg mx-auto">
            Scale your practice with our white-label solution, client dashboards, and referral commissions.
          </p>
        </div>

        <div className="bg-white border border-gray-100 rounded-3xl p-8 shadow-xl text-left space-y-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-blue-700 text-white text-[10px] uppercase font-bold tracking-widest px-4 py-1.5 rounded-bl-2xl">
            PREMIUM PLAN
          </div>
          
          <h2 className="text-lg font-bold text-gray-800 border-b border-gray-100 pb-3">{"What's included in CA Firm Plan:"}</h2>
          
          <ul className="space-y-4">
            <li className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-green-600" />
              </div>
              <div>
                <strong className="text-gray-800 text-sm block">White-label branding</strong>
                <span className="text-gray-500 text-xs">Host the portal under your own subdomain with custom colors and logo.</span>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-green-600" />
              </div>
              <div>
                <strong className="text-gray-800 text-sm block">15% Referral Commissions</strong>
                <span className="text-gray-500 text-xs">Earn recurring payouts on all subscription fees paid by your clients.</span>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-green-600" />
              </div>
              <div>
                <strong className="text-gray-800 text-sm block">Unlimited Clients</strong>
                <span className="text-gray-500 text-xs">Add all client organizations by GSTIN and track compliance status in real-time.</span>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-green-600" />
              </div>
              <div>
                <strong className="text-gray-800 text-sm block">Bulk PDF Compliance Reports</strong>
                <span className="text-gray-500 text-xs">Generate comprehensive mismatch & ITC reports for all clients in one click.</span>
              </div>
            </li>
          </ul>

          {upgradeError && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl p-3">
              {upgradeError}
            </div>
          )}

          {upgradeMsg && (
            <div className="bg-green-50 border border-green-200 text-green-700 text-xs rounded-xl p-3">
              {upgradeMsg}
            </div>
          )}

          <div className="pt-4 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <span className="text-2xl font-black text-gray-900">₹9,999</span>
              <span className="text-gray-500 text-xs"> / month + GST</span>
            </div>
            <button
              onClick={() => {
                initiateSubscription(
                  "ca_firm",
                  user?.email || "",
                  "CA Firm Plan",
                  () => {
                    setUpgradeMsg("Subscription activated successfully! Refreshing portal...");
                    setTimeout(() => {
                      window.location.reload();
                    }, 1500);
                  },
                  (err) => {
                    console.error("Upgrade error:", err);
                  }
                );
              }}
              disabled={upgrading}
              className="w-full sm:w-auto flex items-center justify-center gap-2 bg-blue-700 text-white font-bold px-6 py-3 rounded-2xl text-sm hover:bg-blue-800 disabled:opacity-60 transition-colors shadow-lg shadow-blue-200"
            >
              {upgrading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Initiating Payment...
                </>
              ) : (
                <>
                  Upgrade to CA Firm Plan
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 2. Embedded Profile Setup Form Screen
  if (notRegistered) {
    return (
      <div className="max-w-2xl mx-auto py-8 animate-fadeIn">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-blue-700" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Register CA Firm</h1>
            <p className="text-sm text-gray-500">Set up your firm profile to start managing clients</p>
          </div>
        </div>

        {setupApiError && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
            {setupApiError}
          </div>
        )}

        <form onSubmit={handleSetupSubmit} className="space-y-6" noValidate>
          {/* Firm Details */}
          <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm space-y-5">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Firm Details
            </h2>

            <Field label="Firm Name" error={setupErrors.firm_name} required>
              <input
                type="text"
                value={setupForm.firm_name}
                onChange={(e) => setSetupField("firm_name", e.target.value)}
                placeholder="ABC & Associates"
                className={inputClass(!!setupErrors.firm_name)}
              />
            </Field>

            <Field
              label="ICAI Firm Registration Number"
              error={setupErrors.icai_firm_registration_number}
              required
              hint="e.g. 123456E"
            >
              <input
                type="text"
                value={setupForm.icai_firm_registration_number}
                onChange={(e) => setSetupField("icai_firm_registration_number", e.target.value)}
                placeholder="123456E"
                className={inputClass(!!setupErrors.icai_firm_registration_number)}
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="City" error={setupErrors.city} required>
                <input
                  type="text"
                  value={setupForm.city}
                  onChange={(e) => setSetupField("city", e.target.value)}
                  placeholder="Mumbai"
                  className={inputClass(!!setupErrors.city)}
                />
              </Field>
              <Field label="State" error={setupErrors.state} required>
                <select
                  value={setupForm.state}
                  onChange={(e) => setSetupField("state", e.target.value)}
                  className={inputClass(!!setupErrors.state)}
                >
                  <option value="">Select state</option>
                  {INDIAN_STATES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </div>

          {/* Primary CA */}
          <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm space-y-5">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Primary CA Details
            </h2>

            <Field label="Primary CA Name" error={setupErrors.primary_ca_name} required>
              <input
                type="text"
                value={setupForm.primary_ca_name}
                onChange={(e) => setSetupField("primary_ca_name", e.target.value)}
                placeholder="CA Ramesh Sharma"
                className={inputClass(!!setupErrors.primary_ca_name)}
              />
            </Field>

            <Field
              label="ICAI Membership Number"
              error={setupErrors.icai_membership_number}
              required
              hint="e.g. 123456"
            >
              <input
                type="text"
                value={setupForm.icai_membership_number}
                onChange={(e) => setSetupField("icai_membership_number", e.target.value)}
                placeholder="123456"
                className={inputClass(!!setupErrors.icai_membership_number)}
              />
            </Field>

            <Field label="Phone" error={setupErrors.phone}>
              <input
                type="tel"
                value={setupForm.phone}
                onChange={(e) => setSetupField("phone", e.target.value)}
                placeholder="+91 98765 43210"
                className={inputClass(!!setupErrors.phone)}
              />
            </Field>
          </div>

          {/* White-label (optional) */}
          <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm space-y-5">
            <div>
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                White-Label Branding
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">Optional — customize your client portal</p>
            </div>

            <Field
              label="Subdomain"
              error={setupErrors.white_label_subdomain}
              hint="Your portal will be at subdomain.gstsense.in"
            >
              <div className="flex rounded-xl border border-gray-200 overflow-hidden focus-within:border-blue-500 transition-colors">
                <input
                  type="text"
                  value={setupForm.white_label_subdomain}
                  onChange={(e) => setSetupField("white_label_subdomain", e.target.value.toLowerCase())}
                  placeholder="myfirm"
                  className="flex-1 px-4 py-3 text-sm outline-none bg-white"
                />
                <span className="bg-gray-50 px-3 flex items-center text-xs text-gray-400 border-l border-gray-200">
                  .gstsense.in
                </span>
              </div>
            </Field>

            <Field label="Brand Color" error={setupErrors.primary_color}>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={setupForm.primary_color}
                  onChange={(e) => setSetupField("primary_color", e.target.value)}
                  className="w-10 h-10 rounded-lg border border-gray-200 cursor-pointer p-0.5"
                />
                <input
                  type="text"
                  value={setupForm.primary_color}
                  onChange={(e) => setSetupField("primary_color", e.target.value)}
                  placeholder="#534AB7"
                  className="w-32 px-3 py-2.5 rounded-xl border border-gray-200 text-sm outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </Field>
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={setupSubmitting}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-blue-400 text-white font-semibold py-3 rounded-xl text-sm transition-colors flex items-center justify-center gap-2"
            >
              {setupSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
              {setupSubmitting ? "Registering…" : "Create Profile"}
            </button>
          </div>
        </form>
      </div>
    );
  }

  if (!firm || !stats) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
      </div>
    );
  }

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
      icon: <IndianRupee className="w-5 h-5 text-purple-600" />,
      bg: "bg-purple-50",
    },
  ];

  const statusColors: Record<string, string> = {
    pending: "bg-amber-100 text-amber-700",
    paid: "bg-green-100 text-green-700",
    cancelled: "bg-gray-100 text-gray-600",
  };

  // 3. CA Firm Dashboard Screen
  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-fadeIn">
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
            {reportPolling ? "Generating…" : downloadingReport ? "Starting…" : "Export Report"}
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

function inputClass(hasError: boolean) {
  return `w-full px-4 py-3 rounded-xl border text-sm outline-none transition-colors ${
    hasError
      ? "border-red-400 focus:border-red-500 bg-red-50"
      : "border-gray-200 focus:border-blue-500 bg-white"
  }`;
}

function Field({
  label,
  error,
  hint,
  required,
  children,
}: {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
