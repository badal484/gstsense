"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { FileSpreadsheet, CheckCircle, XCircle, Loader2 } from "lucide-react";
import api from "@/lib/api";

type State = "loading" | "success" | "error";

export default function VerifyEmailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    api
      .get<{ data: { message: string } }>(`/api/v1/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then((res) => {
        setMessage(res.data?.data?.message ?? "Email verified successfully.");
        setState("success");
      })
      .catch((err: unknown) => {
        setMessage(
          err instanceof Error
            ? err.message
            : "Invalid or expired verification link.",
        );
        setState("error");
      });
  }, [token, router]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white flex items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        <Link href="/" className="inline-flex items-center gap-2 font-bold text-2xl text-blue-700 mb-8">
          <FileSpreadsheet className="w-7 h-7" />
          GSTSense
        </Link>

        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8">
          {state === "loading" && (
            <>
              <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
              <p className="text-gray-600">Verifying your email…</p>
            </>
          )}

          {state === "success" && (
            <>
              <CheckCircle className="w-14 h-14 text-green-500 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-gray-900 mb-2">Email verified!</h2>
              <p className="text-gray-500 text-sm mb-6">{message}</p>
              <Link
                href="/login"
                className="bg-blue-700 text-white font-semibold px-6 py-3 rounded-xl hover:bg-blue-800 transition-colors inline-block"
              >
                Log in
              </Link>
            </>
          )}

          {state === "error" && (
            <>
              <XCircle className="w-14 h-14 text-red-500 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-gray-900 mb-2">Verification failed</h2>
              <p className="text-gray-500 text-sm mb-6">{message}</p>
              <Link
                href="/login"
                className="text-blue-700 font-semibold hover:underline text-sm"
              >
                Back to login
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
