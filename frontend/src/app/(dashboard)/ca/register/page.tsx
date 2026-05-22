"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Building2, Loader2, ArrowLeft } from "lucide-react";
import Link from "next/link";
import api from "@/lib/api";
import { API_ROUTES } from "@/lib/constants";

const INDIAN_STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
  "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
  "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

interface FormData {
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

const EMPTY: FormData = {
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

export default function CARegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormData>(EMPTY);
  const [errors, setErrors] = useState<Partial<FormData>>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState("");

  function set(field: keyof FormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
    setApiError("");
  }

  function validate(): boolean {
    const e: Partial<FormData> = {};
    if (!form.firm_name.trim()) e.firm_name = "Firm name is required";
    if (!form.icai_firm_registration_number.trim())
      e.icai_firm_registration_number = "ICAI firm registration number is required";
    if (!form.primary_ca_name.trim()) e.primary_ca_name = "Primary CA name is required";
    if (!form.icai_membership_number.trim())
      e.icai_membership_number = "ICAI membership number is required";
    if (!form.city.trim()) e.city = "City is required";
    if (!form.state) e.state = "State is required";
    if (form.white_label_subdomain && !/^[a-z0-9-]+$/.test(form.white_label_subdomain))
      e.white_label_subdomain = "Only lowercase letters, numbers, and hyphens allowed";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    setApiError("");
    try {
      await api.post(API_ROUTES.CA_FIRMS.REGISTER, {
        firm_name: form.firm_name.trim(),
        icai_firm_registration_number: form.icai_firm_registration_number.trim().toUpperCase(),
        primary_ca_name: form.primary_ca_name.trim(),
        icai_membership_number: form.icai_membership_number.trim().toUpperCase(),
        phone: form.phone.trim() || undefined,
        city: form.city.trim(),
        state: form.state,
        white_label_subdomain: form.white_label_subdomain.trim() || undefined,
        primary_color: form.primary_color,
      });
      router.push("/ca");
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Registration failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="mb-6">
        <Link
          href="/ca"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to CA Portal
        </Link>
      </div>

      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
          <Building2 className="w-5 h-5 text-blue-700" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-900">Register CA Firm</h1>
          <p className="text-sm text-gray-500">Set up your firm profile to start managing clients</p>
        </div>
      </div>

      {apiError && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          {apiError}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6" noValidate>
        {/* Firm Details */}
        <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm space-y-5">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Firm Details
          </h2>

          <Field label="Firm Name" error={errors.firm_name} required>
            <input
              type="text"
              value={form.firm_name}
              onChange={(e) => set("firm_name", e.target.value)}
              placeholder="ABC & Associates"
              className={inputClass(!!errors.firm_name)}
            />
          </Field>

          <Field
            label="ICAI Firm Registration Number"
            error={errors.icai_firm_registration_number}
            required
            hint="e.g. 123456E"
          >
            <input
              type="text"
              value={form.icai_firm_registration_number}
              onChange={(e) => set("icai_firm_registration_number", e.target.value)}
              placeholder="123456E"
              className={inputClass(!!errors.icai_firm_registration_number)}
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="City" error={errors.city} required>
              <input
                type="text"
                value={form.city}
                onChange={(e) => set("city", e.target.value)}
                placeholder="Mumbai"
                className={inputClass(!!errors.city)}
              />
            </Field>
            <Field label="State" error={errors.state} required>
              <select
                value={form.state}
                onChange={(e) => set("state", e.target.value)}
                className={inputClass(!!errors.state)}
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

          <Field label="Primary CA Name" error={errors.primary_ca_name} required>
            <input
              type="text"
              value={form.primary_ca_name}
              onChange={(e) => set("primary_ca_name", e.target.value)}
              placeholder="CA Ramesh Sharma"
              className={inputClass(!!errors.primary_ca_name)}
            />
          </Field>

          <Field
            label="ICAI Membership Number"
            error={errors.icai_membership_number}
            required
            hint="e.g. 123456"
          >
            <input
              type="text"
              value={form.icai_membership_number}
              onChange={(e) => set("icai_membership_number", e.target.value)}
              placeholder="123456"
              className={inputClass(!!errors.icai_membership_number)}
            />
          </Field>

          <Field label="Phone" error={errors.phone}>
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => set("phone", e.target.value)}
              placeholder="+91 98765 43210"
              className={inputClass(!!errors.phone)}
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
            error={errors.white_label_subdomain}
            hint="Your portal will be at subdomain.gstsense.in"
          >
            <div className="flex rounded-xl border border-gray-200 overflow-hidden focus-within:border-blue-500 transition-colors">
              <input
                type="text"
                value={form.white_label_subdomain}
                onChange={(e) => set("white_label_subdomain", e.target.value.toLowerCase())}
                placeholder="myfirm"
                className="flex-1 px-4 py-3 text-sm outline-none bg-white"
              />
              <span className="bg-gray-50 px-3 flex items-center text-xs text-gray-400 border-l border-gray-200">
                .gstsense.in
              </span>
            </div>
          </Field>

          <Field label="Brand Color" error={errors.primary_color}>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={form.primary_color}
                onChange={(e) => set("primary_color", e.target.value)}
                className="w-10 h-10 rounded-lg border border-gray-200 cursor-pointer p-0.5"
              />
              <input
                type="text"
                value={form.primary_color}
                onChange={(e) => set("primary_color", e.target.value)}
                placeholder="#534AB7"
                className="w-32 px-3 py-2.5 rounded-xl border border-gray-200 text-sm outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </Field>
        </div>

        <div className="flex gap-3">
          <Link
            href="/ca"
            className="flex-1 text-center border border-gray-200 text-gray-700 font-semibold py-3 rounded-xl text-sm hover:bg-gray-50 transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={submitting}
            className="flex-1 bg-blue-700 hover:bg-blue-800 disabled:bg-blue-400 text-white font-semibold py-3 rounded-xl text-sm transition-colors flex items-center justify-center gap-2"
          >
            {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
            {submitting ? "Registering…" : "Register CA Firm"}
          </button>
        </div>
      </form>
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
