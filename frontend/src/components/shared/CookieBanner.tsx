"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { initAnalytics } from "@/lib/analytics";

const CONSENT_KEY = "gstsense_cookie_consent";

export function CookieBanner() {
  const [decided, setDecided] = useState<boolean | null>(true); // hide until hydrated

  useEffect(() => {
    const stored = localStorage.getItem(CONSENT_KEY);
    if (stored !== null) {
      setDecided(true);
    } else {
      setDecided(false);
    }
  }, []);

  function accept() {
    localStorage.setItem(CONSENT_KEY, "accepted");
    setDecided(true);
    initAnalytics();
  }

  function reject() {
    localStorage.setItem(CONSENT_KEY, "rejected");
    setDecided(true);
  }

  if (decided !== false) return null;

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 bg-gray-900/95 backdrop-blur-sm text-white px-4 py-4 sm:px-6">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <p className="text-sm text-gray-300 flex-1">
          We use cookies to improve your experience and analyze usage. By using GSTSense you agree
          to our use of cookies in accordance with our{" "}
          <Link href="/privacy" className="underline text-blue-400 hover:text-blue-300">
            Privacy Policy
          </Link>
          .
        </p>
        <div className="flex gap-3 shrink-0">
          <button
            onClick={accept}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-xl transition-colors"
          >
            Accept All
          </button>
          <button
            onClick={reject}
            className="border border-gray-600 hover:border-gray-400 text-gray-300 hover:text-white text-sm font-semibold px-4 py-2 rounded-xl transition-colors"
          >
            Reject Non-Essential
          </button>
        </div>
      </div>
    </div>
  );
}
