"use client";

import { useEffect } from "react";
import Link from "next/link";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.error(error);
    } else {
      // In production, send to Sentry if configured
      if (typeof window !== "undefined" && (window as unknown as { Sentry?: { captureException: (e: Error) => void } }).Sentry) {
        (window as unknown as { Sentry: { captureException: (e: Error) => void } }).Sentry.captureException(error);
      }
    }
  }, [error]);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4">
      <div className="text-center space-y-4 max-w-md">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-8 h-8 bg-blue-700 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">G</span>
          </div>
          <span className="font-bold text-gray-900 text-lg">GSTSense</span>
        </div>

        <h1 className="text-2xl font-bold text-gray-900">Something went wrong</h1>
        <p className="text-gray-500 text-sm">We have been notified and are fixing it.</p>

        {process.env.NODE_ENV === "development" && (
          <div className="bg-gray-100 rounded-xl px-4 py-3 text-left">
            <p className="text-xs text-gray-500 font-mono break-all">{error.message}</p>
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
          <button
            onClick={reset}
            className="bg-blue-700 text-white font-semibold px-6 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
          >
            Try Again
          </button>
          <Link
            href="/"
            className="border border-gray-200 text-gray-700 font-semibold px-6 py-2.5 rounded-xl text-sm hover:bg-gray-50 transition-colors"
          >
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
}
