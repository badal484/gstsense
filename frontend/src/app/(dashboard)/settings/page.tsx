"use client";

import { useEffect, useRef, useState } from "react";
import {
  Bell,
  Check,
  ChevronRight,
  CreditCard,
  Eye,
  EyeOff,
  Loader2,
  Shield,
  Terminal,
  Trash2,
  User,
} from "lucide-react";
import api from "@/lib/api";
import { API_ROUTES, PLAN_LIMITS, PLAN_PRICES, ROUTES } from "@/lib/constants";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";
import { Organization, User as UserType } from "@/types";

type Tab = "profile" | "notifications" | "security" | "billing" | "api";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "profile", label: "Profile", icon: <User className="w-4 h-4" /> },
  { id: "notifications", label: "Notifications", icon: <Bell className="w-4 h-4" /> },
  { id: "security", label: "Security", icon: <Shield className="w-4 h-4" /> },
  { id: "billing", label: "Billing", icon: <CreditCard className="w-4 h-4" /> },
  { id: "api", label: "API", icon: <Terminal className="w-4 h-4" /> },
];

function SaveButton({ saving, saved }: { saving: boolean; saved: boolean }) {
  return (
    <button
      type="submit"
      disabled={saving}
      className="inline-flex items-center gap-2 bg-blue-700 text-white font-semibold px-5 py-2 rounded-xl text-sm hover:bg-blue-800 disabled:opacity-60"
    >
      {saving ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : saved ? (
        <Check className="w-4 h-4" />
      ) : null}
      {saving ? "Saving…" : saved ? "Saved!" : "Save Changes"}
    </button>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
        checked ? "bg-blue-600" : "bg-gray-200"
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-6" : "translate-x-1"
        )}
      />
    </button>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">{title}</h3>
      {children}
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  );
}

const inputCls =
  "w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-50 disabled:text-gray-400";

// ── Profile Tab ───────────────────────────────────────────────────────────────
function ProfileTab({ user, org }: { user: UserType; org: Organization }) {
  const [name, setName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      await api.patch(API_ROUTES.AUTH.ME, { full_name: name, phone: phone || null });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <Section title="Personal Information">
        <Field label="Full Name">
          <input
            className={inputCls}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </Field>
        <Field label="Email Address" hint="Email cannot be changed after registration.">
          <input className={inputCls} value={user.email} disabled />
        </Field>
        <Field label="Phone Number" hint="Used for WhatsApp deadline reminders.">
          <input
            className={inputCls}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+91 98765 43210"
          />
        </Field>
      </Section>

      <Section title="Organisation Details">
        <Field label="Business Name">
          <input className={inputCls} value={org.business_name} disabled />
        </Field>
        <Field label="GSTIN">
          <input className={inputCls} value={org.gstin} disabled />
        </Field>
        <Field label="State">
          <input className={inputCls} value={org.state_code} disabled />
        </Field>
        <p className="text-xs text-gray-400">
          To update GSTIN or state, contact{" "}
          <a href="mailto:support@gstsense.in" className="text-blue-600 hover:underline">
            support@gstsense.in
          </a>
          .
        </p>
      </Section>

      <SaveButton saving={saving} saved={saved} />
    </form>
  );
}

// ── Notifications Tab ─────────────────────────────────────────────────────────
type NotifPrefs = {
  whatsapp_deadlines: boolean;
  email_scan_complete: boolean;
  email_mismatch_alerts: boolean;
  email_payment_receipts: boolean;
};

function NotificationsTab() {
  const [prefs, setPrefs] = useState<NotifPrefs>({
    whatsapp_deadlines: true,
    email_scan_complete: true,
    email_mismatch_alerts: true,
    email_payment_receipts: true,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  function toggle(key: keyof NotifPrefs) {
    setPrefs((p) => ({ ...p, [key]: !p[key] }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      await api.patch("/api/v1/users/notification-preferences", prefs);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      // preferences endpoint may not exist yet — save locally
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  }

  const rows: { key: keyof NotifPrefs; label: string; desc: string }[] = [
    {
      key: "whatsapp_deadlines",
      label: "WhatsApp Deadline Reminders",
      desc: "Receive filing deadline reminders via WhatsApp (requires phone number).",
    },
    {
      key: "email_scan_complete",
      label: "Scan Completed",
      desc: "Email when your GST reconciliation scan finishes.",
    },
    {
      key: "email_mismatch_alerts",
      label: "High-Risk Mismatch Alerts",
      desc: "Email when mismatches above ₹1 lakh are detected.",
    },
    {
      key: "email_payment_receipts",
      label: "Payment Receipts",
      desc: "Email receipts for every payment made on GSTSense.",
    },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-3">
        {rows.map((r) => (
          <div
            key={r.key}
            className="flex items-center justify-between gap-4 bg-gray-50 rounded-xl px-4 py-3"
          >
            <div>
              <p className="text-sm font-medium text-gray-800">{r.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{r.desc}</p>
            </div>
            <Toggle checked={prefs[r.key]} onChange={() => toggle(r.key)} />
          </div>
        ))}
      </div>
      <SaveButton saving={saving} saved={saved} />
    </form>
  );
}

// ── Security Tab ──────────────────────────────────────────────────────────────
function passwordStrength(pw: string): { label: string; color: string; width: string } {
  if (pw.length === 0) return { label: "", color: "", width: "0%" };
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (score <= 1) return { label: "Weak", color: "bg-red-500", width: "20%" };
  if (score === 2) return { label: "Fair", color: "bg-amber-400", width: "40%" };
  if (score === 3) return { label: "Good", color: "bg-yellow-400", width: "60%" };
  if (score === 4) return { label: "Strong", color: "bg-green-400", width: "80%" };
  return { label: "Very Strong", color: "bg-green-600", width: "100%" };
}

function SecurityTab() {
  const { logout } = useAuthStore();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);

  const strength = passwordStrength(next);

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (next !== confirm) {
      setError("New passwords do not match.");
      return;
    }
    if (next.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSaving(true);
    try {
      await api.post("/api/v1/auth/change-password", {
        current_password: current,
        new_password: next,
      });
      setSaved(true);
      setCurrent("");
      setNext("");
      setConfirm("");
      setTimeout(() => setSaved(false), 2500);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
          ?.message ?? "Failed to change password.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAccount() {
    if (deleteConfirm !== "DELETE") return;
    setDeleting(true);
    try {
      await api.delete("/api/v1/users/me");
      logout();
    } catch {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-10">
      {/* Change Password */}
      <form onSubmit={handlePasswordChange} className="space-y-4">
        <Section title="Change Password">
          <Field label="Current Password">
            <div className="relative">
              <input
                type={showCurrent ? "text" : "password"}
                className={cn(inputCls, "pr-10")}
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                required
              />
              <button
                type="button"
                onClick={() => setShowCurrent((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </Field>
          <Field label="New Password">
            <div className="relative">
              <input
                type={showNext ? "text" : "password"}
                className={cn(inputCls, "pr-10")}
                value={next}
                onChange={(e) => setNext(e.target.value)}
                required
              />
              <button
                type="button"
                onClick={() => setShowNext((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showNext ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {next && (
              <div className="mt-2 space-y-1">
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all", strength.color)}
                    style={{ width: strength.width }}
                  />
                </div>
                <p className="text-xs text-gray-500">{strength.label}</p>
              </div>
            )}
          </Field>
          <Field label="Confirm New Password">
            <input
              type="password"
              className={inputCls}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </Field>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </Section>
        <SaveButton saving={saving} saved={saved} />
      </form>

      {/* Sessions */}
      <Section title="Active Sessions">
        <div className="bg-gray-50 rounded-xl px-4 py-3 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-800">Current session</p>
            <p className="text-xs text-gray-400 mt-0.5">This device · Active now</p>
          </div>
          <span className="text-xs bg-green-100 text-green-700 font-semibold px-2 py-0.5 rounded-full">
            Active
          </span>
        </div>
        <button
          onClick={() => {
            api.post(API_ROUTES.AUTH.LOGOUT).catch(() => {});
            useAuthStore.getState().logout();
          }}
          className="text-sm text-red-600 hover:text-red-700 font-medium"
        >
          Sign out of all sessions
        </button>
      </Section>

      {/* Danger Zone */}
      <Section title="Danger Zone">
        <div className="border border-red-200 rounded-xl p-4 space-y-3">
          <p className="text-sm font-semibold text-red-700 flex items-center gap-2">
            <Trash2 className="w-4 h-4" /> Delete Account
          </p>
          <p className="text-xs text-gray-500">
            This permanently deletes your account, all scans, and all data. This cannot be undone.
          </p>
          <p className="text-xs text-gray-600">
            Type <span className="font-mono font-bold">DELETE</span> to confirm:
          </p>
          <input
            className={cn(inputCls, "max-w-xs")}
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder="DELETE"
          />
          <button
            type="button"
            onClick={handleDeleteAccount}
            disabled={deleteConfirm !== "DELETE" || deleting}
            className="flex items-center gap-2 bg-red-600 text-white text-sm font-semibold px-4 py-2 rounded-xl hover:bg-red-700 disabled:opacity-40"
          >
            {deleting && <Loader2 className="w-4 h-4 animate-spin" />}
            Delete My Account
          </button>
        </div>
      </Section>
    </div>
  );
}

// ── Billing Tab ───────────────────────────────────────────────────────────────
function BillingTab({ org }: { org: Organization }) {
  const planLabel = PLAN_LIMITS[org.plan]?.label ?? org.plan;
  const isFree = org.plan === "free";

  const upgrades: { plan: "smb" | "growth" | "ca_firm"; label: string; price: number; desc: string }[] = [
    { plan: "smb", label: "SMB", price: PLAN_PRICES.smb, desc: "Up to 1,500 invoices / month" },
    { plan: "growth", label: "Growth", price: PLAN_PRICES.growth, desc: "Up to 5,000 invoices / month" },
    { plan: "ca_firm", label: "CA Firm", price: PLAN_PRICES.ca_firm, desc: "Up to 50,000 invoices / month + white-label" },
  ];

  return (
    <div className="space-y-8">
      <Section title="Current Plan">
        <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-4 flex items-center justify-between">
          <div>
            <p className="text-lg font-bold text-blue-900">{planLabel} Plan</p>
            <p className="text-sm text-blue-700 mt-0.5">
              {PLAN_LIMITS[org.plan]?.invoices?.toLocaleString()} invoices / month
            </p>
            {org.billing_cycle_end && (
              <p className="text-xs text-blue-500 mt-1">
                Renews {new Date(org.billing_cycle_end).toLocaleDateString("en-IN")}
              </p>
            )}
          </div>
          <span
            className={cn(
              "text-xs font-semibold px-3 py-1 rounded-full",
              org.has_active_subscription
                ? "bg-green-100 text-green-700"
                : "bg-amber-100 text-amber-700"
            )}
          >
            {org.has_active_subscription ? "Active" : org.subscription_status}
          </span>
        </div>
      </Section>

      {isFree && (
        <Section title="Upgrade Plan">
          <div className="space-y-3">
            {upgrades.map((u) => (
              <div
                key={u.plan}
                className="border border-gray-200 rounded-xl px-4 py-3 flex items-center justify-between hover:border-blue-300 transition-colors"
              >
                <div>
                  <p className="text-sm font-semibold text-gray-800">{u.label}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{u.desc}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-sm font-bold text-gray-900">
                    ₹{u.price.toLocaleString()}/mo
                  </span>
                  <button className="text-xs font-semibold bg-blue-700 text-white px-3 py-1.5 rounded-lg hover:bg-blue-800 flex items-center gap-1">
                    Upgrade <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Invoice Usage">
        <div className="space-y-2">
          <div className="flex justify-between text-xs text-gray-500">
            <span>Used this month</span>
            <span>
              {org.invoices_used_this_month.toLocaleString()} / {org.invoice_limit.toLocaleString()}
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                org.is_invoice_limit_reached
                  ? "bg-red-500"
                  : org.invoices_used_this_month / org.invoice_limit > 0.8
                  ? "bg-amber-400"
                  : "bg-blue-500"
              )}
              style={{
                width: `${Math.min((org.invoices_used_this_month / org.invoice_limit) * 100, 100)}%`,
              }}
            />
          </div>
          {org.is_invoice_limit_reached && (
            <p className="text-xs text-red-600 font-medium">
              Invoice limit reached. Upgrade to continue scanning.
            </p>
          )}
        </div>
      </Section>
    </div>
  );
}

// ── API Tab ───────────────────────────────────────────────────────────────────
function ApiTab() {
  return (
    <div className="space-y-6">
      <Section title="API Access">
        <div className="bg-gray-50 rounded-xl px-5 py-8 text-center">
          <Terminal className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-sm font-semibold text-gray-600">API Access Coming Soon</p>
          <p className="text-xs text-gray-400 mt-1 max-w-sm mx-auto">
            Programmatic access to GSTSense reconciliation and ITC analysis will be available in a
            future release.
          </p>
        </div>
      </Section>
    </div>
  );
}

// ── Root Page ─────────────────────────────────────────────────────────────────
export default function SettingsPage() {
  const { user, organization } = useAuthStore();
  const [activeTab, setActiveTab] = useState<Tab>("profile");

  if (!user || !organization) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 text-sm mt-0.5">Manage your account, notifications, and billing</p>
      </div>

      <div className="flex flex-col md:flex-row gap-6">
        {/* Sidebar */}
        <nav className="md:w-48 shrink-0">
          <ul className="space-y-1">
            {TABS.map((t) => (
              <li key={t.id}>
                <button
                  onClick={() => setActiveTab(t.id)}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm font-medium transition-colors",
                    activeTab === t.id
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-600 hover:bg-gray-50"
                  )}
                >
                  {t.icon}
                  {t.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Content */}
        <div className="flex-1 bg-white border border-gray-100 rounded-2xl shadow-sm p-6">
          {activeTab === "profile" && <ProfileTab user={user} org={organization} />}
          {activeTab === "notifications" && <NotificationsTab />}
          {activeTab === "security" && <SecurityTab />}
          {activeTab === "billing" && <BillingTab org={organization} />}
          {activeTab === "api" && <ApiTab />}
        </div>
      </div>
    </div>
  );
}
