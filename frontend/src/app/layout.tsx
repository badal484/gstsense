import type { Metadata } from "next"
import "./globals.css"
import { Providers } from "@/components/providers/Providers"
import { CookieBanner } from "@/components/shared/CookieBanner"

export const metadata: Metadata = {
  title: "GSTSense — Find GST Mismatches Before The Government Does",
  description:
    "Upload your GSTR-1 and GSTR-3B files. Detect every mismatch and rupee risk in 60 seconds. Trusted by Indian SMBs and CA firms.",
  keywords: [
    "GST reconciliation",
    "GSTR-1 GSTR-3B mismatch",
    "GST compliance India",
    "Rule 88C notice",
    "ITC mismatch",
    "GST audit software",
  ],
  openGraph: {
    title: "GSTSense — GST Compliance for Indian SMBs",
    description: "Detect GST mismatches in 60 seconds. Prevent Rule 88C notices.",
    url: "https://gstsense.in",
    siteName: "GSTSense",
    type: "website",
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body style={{
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        margin: 0,
        padding: 0,
      }}>
        <Providers>
          {children}
          <CookieBanner />
        </Providers>
      </body>
    </html>
  )
}
