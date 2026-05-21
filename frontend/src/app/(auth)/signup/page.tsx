"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FileSpreadsheet, Eye, EyeOff, Loader2, CheckCircle, XCircle } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { trackEvent } from "@/lib/analytics";
import { ROUTES } from "@/lib/constants";
import { validateGSTIN } from "@/lib/utils";

interface FieldErrors {
  full_name?: string;
  email?: string;
  gstin?: string;
  password?: string;
}

function PasswordStrength({ password }: { password: string }) {
  const checks = [
    { label: "At least 8 characters", pass: password.length >= 8 },
    { label: "Contains uppercase", pass: /[A-Z]/.test(password) },
    { label: "Contains number", pass: /[0-9]/.test(password) },
  ];

  if (!password) return null;

  return (
    <div className="mt-2 space-y-1">
      {checks.map((c) => (
        <div key={c.label} className="flex items-center gap-1.5">
          {c.pass ? (
            <CheckCircle className="w-3.5 h-3.5 text-green-500" />
          ) : (
            <XCircle className="w-3.5 h-3.5 text-gray-300" />
          )}
          <span className={`text-xs ${c.pass ? "text-green-600" : "text-gray-400"}`}>{c.label}</span>
        </div>
      ))}
    </div>
  );
}

export default function SignupPage() {
  const router = useRouter();
  const { register, isLoading, error } = useAuthStore();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [gstin, setGstin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [gstinValid, setGstinValid] = useState<boolean | null>(null);

  function handleGstinChange(value: string) {
    const upper = value.toUpperCase().trim();
    setGstin(upper);
    setFieldErrors((prev) => ({ ...prev, gstin: undefined }));
    if (upper.length === 15) {
      setGstinValid(validateGSTIN(upper));
    } else {
      setGstinValid(null);
    }
  }

  function validate(): boolean {
    const errors: FieldErrors = {};
    if (!fullName.trim()) errors.full_name = "Full name is required";
    if (!email.trim()) errors.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = "Enter a valid email";
    if (!gstin.trim()) errors.gstin = "GSTIN is required";
    else if (!validateGSTIN(gstin)) errors.gstin = "Enter a valid 15-character GSTIN";
    if (!password) errors.password = "Password is required";
    else if (password.length < 8) errors.password = "Password must be at least 8 characters";
    else if (!/[A-Z]/.test(password)) errors.password = "Password must contain an uppercase letter";
    else if (!/[0-9]/.test(password)) errors.password = "Password must contain a number";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    try {
      await register(fullName.trim(), email.trim(), password, gstin.trim());
      if (useAuthStore.getState().isAuthenticated) {
        trackEvent("signup_completed", { gstin_state: gstin.trim().substring(0, 2) });
        router.push(ROUTES.DASHBOARD);
      }
    } catch {
      // error is already set in the store by register()
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 font-bold text-2xl text-blue-700 mb-6">
            <FileSpreadsheet className="w-7 h-7" />
            GSTSense
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Create your account</h1>
          <p className="text-gray-500 mt-1">Start with a free scan — no credit card needed</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Full name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  setFieldErrors((prev) => ({ ...prev, full_name: undefined }));
                }}
                placeholder="Rajesh Mehta"
                className={`w-full px-4 py-3 rounded-xl border text-sm outline-none transition-colors ${
                  fieldErrors.full_name
                    ? "border-red-400 focus:border-red-500 bg-red-50"
                    : "border-gray-200 focus:border-blue-500 bg-white"
                }`}
                autoComplete="name"
              />
              {fieldErrors.full_name && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.full_name}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Email address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setFieldErrors((prev) => ({ ...prev, email: undefined }));
                }}
                placeholder="you@company.com"
                className={`w-full px-4 py-3 rounded-xl border text-sm outline-none transition-colors ${
                  fieldErrors.email
                    ? "border-red-400 focus:border-red-500 bg-red-50"
                    : "border-gray-200 focus:border-blue-500 bg-white"
                }`}
                autoComplete="email"
              />
              {fieldErrors.email && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.email}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">GSTIN</label>
              <div className="relative">
                <input
                  type="text"
                  value={gstin}
                  onChange={(e) => handleGstinChange(e.target.value)}
                  placeholder="22AAAAA0000A1Z5"
                  maxLength={15}
                  className={`w-full px-4 py-3 pr-10 rounded-xl border text-sm outline-none font-mono tracking-wider transition-colors ${
                    fieldErrors.gstin
                      ? "border-red-400 focus:border-red-500 bg-red-50"
                      : gstinValid === true
                      ? "border-green-400 focus:border-green-500 bg-green-50"
                      : "border-gray-200 focus:border-blue-500 bg-white"
                  }`}
                />
                {gstinValid !== null && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {gstinValid ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500" />
                    )}
                  </div>
                )}
              </div>
              {fieldErrors.gstin && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.gstin}</p>
              )}
              {!fieldErrors.gstin && (
                <p className="mt-1 text-xs text-gray-400">15-character GST Identification Number</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setFieldErrors((prev) => ({ ...prev, password: undefined }));
                  }}
                  placeholder="••••••••"
                  className={`w-full px-4 py-3 pr-11 rounded-xl border text-sm outline-none transition-colors ${
                    fieldErrors.password
                      ? "border-red-400 focus:border-red-500 bg-red-50"
                      : "border-gray-200 focus:border-blue-500 bg-white"
                  }`}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {fieldErrors.password && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.password}</p>
              )}
              <PasswordStrength password={password} />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-blue-400 text-white font-semibold py-3 rounded-xl transition-colors flex items-center justify-center gap-2 mt-2"
            >
              {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
              {isLoading ? "Creating account..." : "Create Account"}
            </button>

            <p className="text-xs text-gray-400 text-center">
              By creating an account you agree to our Terms of Service and Privacy Policy.
            </p>
          </form>
        </div>

        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account?{" "}
          <Link href={ROUTES.LOGIN} className="text-blue-700 font-semibold hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
