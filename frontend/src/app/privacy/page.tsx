import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy — GSTSense",
  description: "GSTSense privacy policy and data handling practices",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold text-gray-900">{title}</h2>
      <div className="text-gray-600 text-sm leading-relaxed space-y-2">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-gray-100 px-6 py-4">
        <Link href="/" className="inline-flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-700 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">G</span>
          </div>
          <span className="font-bold text-gray-900">GSTSense</span>
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12 space-y-10">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <p className="text-amber-800 text-sm font-medium">⚠️ Legal Review Required</p>
          <p className="text-amber-700 text-sm mt-1">
            These documents are templates and must be reviewed by a qualified Indian lawyer before
            going live. Contact{" "}
            <a href="mailto:legal@gstsense.in" className="underline">legal@gstsense.in</a>{" "}
            for assistance.
          </p>
        </div>

        <div>
          <h1 className="text-3xl font-extrabold text-gray-900">Privacy Policy</h1>
          <p className="text-sm text-gray-400 mt-1">Last updated: January 2025</p>
        </div>

        <Section title="1. Information We Collect">
          <p>We collect information you provide when creating an account and using our services:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>
              <strong>Account information</strong> — your name, email address, and GSTIN.
            </li>
            <li>
              <strong>GST filing data</strong> — GSTR-1, GSTR-3B, and GSTR-2B files you upload for
              reconciliation.
            </li>
            <li>
              <strong>Payment information</strong> — processed securely by Razorpay; we do not
              store card numbers.
            </li>
            <li>
              <strong>Usage data and log files</strong> — pages visited, features used, IP address,
              and browser information.
            </li>
          </ul>
        </Section>

        <Section title="2. How We Use Your Information">
          <ul className="list-disc list-inside space-y-1">
            <li>Providing GST compliance and reconciliation services.</li>
            <li>Generating mismatch reports between GSTR-1 and GSTR-3B.</li>
            <li>Sending GST filing deadline reminders via WhatsApp and email.</li>
            <li>Improving our algorithms, AI models, and platform experience.</li>
          </ul>
        </Section>

        <Section title="3. Data Storage and Security">
          <p>We take the security of your financial data seriously:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>All data stored on AWS servers located in Mumbai, India (ap-south-1 region).</li>
            <li>AES-256 encryption at rest for all stored files and database records.</li>
            <li>TLS 1.3 encryption in transit for all data transmitted to our servers.</li>
            <li>
              Multi-tenant data isolation — your data is never accessible to other organisations.
            </li>
          </ul>
        </Section>

        <Section title="4. Data Sharing">
          <p>
            <strong>We do not sell your data.</strong> We do not share your personal or financial
            information with third parties except:
          </p>
          <ul className="list-disc list-inside space-y-1">
            <li>
              <strong>Razorpay</strong> — for payment processing, subject to their privacy policy.
            </li>
            <li>
              <strong>Amazon Web Services (AWS)</strong> — cloud infrastructure provider.
            </li>
            <li>
              <strong>Anthropic / OpenAI</strong> — for AI-powered analysis. Data sent is
              anonymised and does not include personal identifiers.
            </li>
          </ul>
        </Section>

        <Section title="5. Your Rights Under DPDP Act 2023">
          <p>
            Under the Digital Personal Data Protection Act 2023, you have the following rights:
          </p>
          <ul className="list-disc list-inside space-y-1">
            <li>
              <strong>Right to access</strong> — request a copy of all personal data we hold.
            </li>
            <li>
              <strong>Right to correct</strong> — request correction of inaccurate data.
            </li>
            <li>
              <strong>Right to erase</strong> — request deletion of your account and data.
            </li>
            <li>
              <strong>Right to withdraw consent</strong> — opt out of non-essential data
              processing.
            </li>
          </ul>
          <p>
            To exercise these rights, contact{" "}
            <a href="mailto:privacy@gstsense.in" className="text-blue-600 hover:underline">
              privacy@gstsense.in
            </a>
            . We will respond within 30 days.
          </p>
        </Section>

        <Section title="6. Data Retention">
          <ul className="list-disc list-inside space-y-1">
            <li>
              <strong>Account data</strong> — retained until you request deletion.
            </li>
            <li>
              <strong>GST files (GSTR-1, GSTR-3B)</strong> — automatically deleted 90 days after
              upload.
            </li>
            <li>
              <strong>Payment records</strong> — retained for 7 years as required under Indian tax
              law.
            </li>
            <li>
              <strong>Audit logs</strong> — retained for 12 months for security and compliance
              purposes.
            </li>
          </ul>
        </Section>

        <Section title="7. Contact Us">
          <p>
            For any privacy-related questions or to exercise your rights, please contact our Data
            Protection Officer:
          </p>
          <p>
            Email:{" "}
            <a href="mailto:privacy@gstsense.in" className="text-blue-600 hover:underline">
              privacy@gstsense.in
            </a>
          </p>
          <p>
            <strong>GSTSense Technologies Private Limited</strong>
            <br />
            India
          </p>
        </Section>
      </main>

      <footer className="border-t border-gray-100 px-6 py-6 text-center text-xs text-gray-400">
        <p>
          &copy; {new Date().getFullYear()} GSTSense Technologies Private Limited. All rights
          reserved.
        </p>
        <div className="flex items-center justify-center gap-4 mt-2">
          <Link href="/terms" className="hover:text-gray-600">
            Terms of Service
          </Link>
          <Link href="/privacy" className="hover:text-gray-600 text-blue-600">
            Privacy Policy
          </Link>
        </div>
      </footer>
    </div>
  );
}
