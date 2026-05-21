import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Providers } from "@/components/providers/Providers";
import { CookieBanner } from "@/components/shared/CookieBanner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: {
    default: "GSTSense — GST Reconciliation for Indian Businesses",
    template: "%s | GSTSense",
  },
  description:
    "Catch GST mismatches between GSTR-1 and GSTR-3B before tax notices arrive. AI-powered reconciliation with instant reports.",
  keywords: ["GST reconciliation", "GSTR-1", "GSTR-3B", "GST compliance", "India tax"],
  authors: [{ name: "GSTSense" }],
  creator: "GSTSense",
  metadataBase: new URL("https://gstsense.in"),
  openGraph: {
    type: "website",
    locale: "en_IN",
    url: "https://gstsense.in",
    title: "GSTSense — Catch GST Mismatches Before They Cost You",
    description:
      "AI-powered GSTR-1 vs GSTR-3B reconciliation. Upload, scan, get a report in under 60 seconds.",
    siteName: "GSTSense",
  },
  twitter: {
    card: "summary_large_image",
    title: "GSTSense — GST Reconciliation Made Simple",
    description:
      "Upload your GSTR-1 and GSTR-3B files. Get AI-powered mismatch analysis in seconds.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-inter antialiased bg-white text-gray-900">
        <Providers>
          {children}
          <CookieBanner />
        </Providers>
      </body>
    </html>
  );
}
