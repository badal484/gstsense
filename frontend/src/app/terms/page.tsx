import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service — GSTSense",
  description: "GSTSense terms of service and user agreement",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold text-gray-900">{title}</h2>
      <div className="text-gray-600 text-sm leading-relaxed space-y-2">{children}</div>
    </section>
  );
}

export default function TermsPage() {
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
          <h1 className="text-3xl font-extrabold text-gray-900">Terms of Service</h1>
          <p className="text-sm text-gray-400 mt-1">Last updated: January 2025</p>
        </div>

        <Section title="1. Acceptance of Terms">
          <p>
            By creating an account or using GSTSense, you agree to be bound by these Terms of
            Service and our Privacy Policy. If you do not agree, do not use our services.
          </p>
        </Section>

        <Section title="2. Description of Service">
          <p>
            GSTSense provides GST compliance automation tools, including GSTR-1 vs GSTR-3B
            reconciliation, ITC analysis, and AI-assisted notice response drafting.
          </p>
          <p>
            GSTSense is a <strong>technology company</strong>, not a CA firm or law firm. Our
            services are software tools that assist with GST compliance, not professional advice.
          </p>
          <p>
            Our AI-generated reports and documents are for informational and assistance purposes
            only and do not constitute legal, tax, or accounting advice.
          </p>
        </Section>

        <Section title="3. Important Disclaimer">
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-4">
            <p className="text-red-800 font-semibold leading-relaxed">
              GSTSense is a TECHNOLOGY TOOL. We do not provide legal, tax, or accounting advice.
              AI-generated notice replies must be reviewed by a qualified Chartered Accountant or
              Advocate before submission to any government authority. GSTSense Technologies Private
              Limited accepts no liability for actions taken based on our reports or generated
              documents.
            </p>
          </div>
        </Section>

        <Section title="4. User Responsibilities">
          <p>You are solely responsible for:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>The accuracy and completeness of GST data you upload to GSTSense.</li>
            <li>
              Having all AI-generated notice replies reviewed by a qualified CA or Advocate before
              submitting to any government authority.
            </li>
            <li>Your compliance with all applicable GST laws and regulations.</li>
            <li>Maintaining the confidentiality of your account credentials.</li>
          </ul>
        </Section>

        <Section title="5. Subscription and Payment Terms">
          <ul className="list-disc list-inside space-y-1">
            <li>Monthly subscriptions automatically renew at the end of each billing period.</li>
            <li>
              You may cancel your subscription at any time before the renewal date; access
              continues until the end of the current period.
            </li>
            <li>
              <strong>No refunds</strong> are provided for partial months or unused services.
            </li>
            <li>
              GSTSense reserves the right to change subscription prices with at least 30 days
              written notice to your registered email.
            </li>
          </ul>
        </Section>

        <Section title="6. Intellectual Property">
          <p>
            The GSTSense platform, software, AI models, and all associated intellectual property
            are proprietary to GSTSense Technologies Private Limited.
          </p>
          <p>
            <strong>Your data remains yours.</strong> GST files and business data you upload remain
            your property. We do not claim ownership over your data.
          </p>
        </Section>

        <Section title="7. Limitation of Liability">
          <p>
            To the maximum extent permitted by applicable law, GSTSense Technologies Private
            Limited&apos;s total liability to you for any claim arising from these terms or your use
            of our services is limited to the fees you paid to GSTSense in the three months
            preceding the claim.
          </p>
          <p>
            We are not liable for indirect, incidental, special, consequential, or punitive
            damages, including loss of revenue, loss of data, or penalties imposed by tax
            authorities.
          </p>
        </Section>

        <Section title="8. Governing Law">
          <p>
            These Terms of Service are governed by and construed in accordance with the laws of
            India. Any disputes arising under or in connection with these Terms shall be subject to
            the exclusive jurisdiction of the courts in Mumbai, Maharashtra, India.
          </p>
        </Section>

        <Section title="9. Contact">
          <p>
            For legal inquiries or questions about these Terms, contact us at:{" "}
            <a href="mailto:legal@gstsense.in" className="text-blue-600 hover:underline">
              legal@gstsense.in
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
          <Link href="/terms" className="hover:text-gray-600 text-blue-600">
            Terms of Service
          </Link>
          <Link href="/privacy" className="hover:text-gray-600">
            Privacy Policy
          </Link>
        </div>
      </footer>
    </div>
  );
}
