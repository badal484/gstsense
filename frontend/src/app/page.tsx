"use client";

import Link from "next/link";
import { useState } from "react";
import {
  FileSpreadsheet,
  Zap,
  ShieldCheck,
  TrendingUp,
  CheckCircle,
  ArrowRight,
  Menu,
  X,
  Star,
  AlertTriangle,
  Clock,
  IndianRupee,
} from "lucide-react";
import { ROUTES, ONE_TIME_SCAN_PRICE } from "@/lib/constants";

function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur-md border-b border-gray-100">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between h-16">
        <Link href="/" className="flex items-center gap-2 font-bold text-xl text-blue-700">
          <FileSpreadsheet className="w-6 h-6" />
          GSTSense
        </Link>

        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
          <a href="#how-it-works" className="hover:text-blue-700 transition-colors">How It Works</a>
          <a href="#pricing" className="hover:text-blue-700 transition-colors">Pricing</a>
          <a href="#testimonials" className="hover:text-blue-700 transition-colors">Testimonials</a>
        </div>

        <div className="hidden md:flex items-center gap-3">
          <Link
            href={ROUTES.LOGIN}
            className="text-sm font-medium text-gray-600 hover:text-blue-700 transition-colors px-3 py-2"
          >
            Sign in
          </Link>
          <Link
            href={ROUTES.SIGNUP}
            className="bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-blue-800 transition-colors"
          >
            Get Started Free
          </Link>
        </div>

        <button className="md:hidden p-2" onClick={() => setOpen(!open)}>
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {open && (
        <div className="md:hidden bg-white border-t border-gray-100 px-4 py-4 flex flex-col gap-4">
          <a href="#how-it-works" className="text-sm font-medium text-gray-600" onClick={() => setOpen(false)}>How It Works</a>
          <a href="#pricing" className="text-sm font-medium text-gray-600" onClick={() => setOpen(false)}>Pricing</a>
          <a href="#testimonials" className="text-sm font-medium text-gray-600" onClick={() => setOpen(false)}>Testimonials</a>
          <Link href={ROUTES.LOGIN} className="text-sm font-medium text-gray-600" onClick={() => setOpen(false)}>Sign in</Link>
          <Link
            href={ROUTES.SIGNUP}
            className="bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-lg text-center"
            onClick={() => setOpen(false)}
          >
            Get Started Free
          </Link>
        </div>
      )}
    </nav>
  );
}

function Hero() {
  return (
    <section className="pt-32 pb-20 px-4 sm:px-6 bg-gradient-to-b from-blue-50 to-white">
      <div className="max-w-4xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 bg-orange-100 text-orange-700 text-xs font-semibold px-3 py-1 rounded-full mb-6">
          <AlertTriangle className="w-3.5 h-3.5" />
          GSTR-3B deadline in <span className="font-bold">20 days</span> — don&apos;t file blind
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-gray-900 leading-tight mb-6">
          Catch GST Mismatches{" "}
          <span className="text-blue-700">Before the Notice Arrives</span>
        </h1>

        <p className="text-lg sm:text-xl text-gray-600 max-w-2xl mx-auto mb-10">
          Upload your GSTR-1 and GSTR-3B files. Our AI finds every discrepancy,
          calculates your rupee risk, and explains each mismatch in plain language —
          in under 60 seconds.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
          <Link
            href={ROUTES.SIGNUP}
            className="flex items-center justify-center gap-2 bg-blue-700 text-white font-bold px-8 py-4 rounded-xl text-lg hover:bg-blue-800 transition-colors shadow-lg shadow-blue-200"
          >
            Start Free Scan
            <ArrowRight className="w-5 h-5" />
          </Link>
          <a
            href="#how-it-works"
            className="flex items-center justify-center gap-2 bg-white text-gray-700 font-semibold px-8 py-4 rounded-xl text-lg border border-gray-200 hover:border-blue-300 hover:text-blue-700 transition-colors"
          >
            See How It Works
          </a>
        </div>

        <div className="flex flex-wrap justify-center gap-6 text-sm text-gray-500">
          {["No credit card to start", "Results in 60 seconds", "Bank-grade security"].map((item) => (
            <div key={item} className="flex items-center gap-1.5">
              <CheckCircle className="w-4 h-4 text-green-500" />
              {item}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Pain() {
  const pains = [
    {
      icon: <AlertTriangle className="w-6 h-6 text-red-500" />,
      title: "Notices for differences you didn't notice",
      body: "GSTN flags any mismatch between GSTR-1 and GSTR-3B. Manual checks across hundreds of invoices take hours and still miss things.",
    },
    {
      icon: <Clock className="w-6 h-6 text-orange-500" />,
      title: "Reconciliation takes your whole weekend",
      body: "Accountants spend 3–5 hours every month doing manual VLOOKUP reconciliation. Time that should go to advisory work.",
    },
    {
      icon: <IndianRupee className="w-6 h-6 text-red-600" />,
      title: "₹18% interest + penalties add up fast",
      body: "A ₹5 lakh mismatch becomes ₹5.9 lakh by the time a demand notice arrives. Early detection is cheaper than compliance.",
    },
  ];

  return (
    <section className="py-20 px-4 sm:px-6 bg-gray-50">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            GST compliance is broken for most businesses
          </h2>
          <p className="text-gray-500 max-w-xl mx-auto">
            Filing without reconciling first is like driving without checking your mirrors.
          </p>
        </div>

        <div className="grid sm:grid-cols-3 gap-6">
          {pains.map((p) => (
            <div key={p.title} className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
              <div className="mb-4">{p.icon}</div>
              <h3 className="font-bold text-gray-900 mb-2">{p.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{p.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      num: "01",
      icon: <FileSpreadsheet className="w-8 h-8 text-blue-600" />,
      title: "Upload your files",
      body: "Drag and drop your GSTR-1 and GSTR-3B Excel files. We accept all standard export formats from the GST portal.",
    },
    {
      num: "02",
      icon: <Zap className="w-8 h-8 text-purple-600" />,
      title: "AI reconciles in seconds",
      body: "Our engine matches every invoice by GSTIN and invoice number, flags value mismatches, tax mismatches, and missing entries.",
    },
    {
      num: "03",
      icon: <TrendingUp className="w-8 h-8 text-green-600" />,
      title: "Get an actionable report",
      body: "See every mismatch sorted by rupee risk, with plain-English AI explanations and recommended actions. Download as PDF.",
    },
  ];

  return (
    <section id="how-it-works" className="py-20 px-4 sm:px-6 bg-white">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            Three steps to compliance confidence
          </h2>
          <p className="text-gray-500 max-w-xl mx-auto">
            No Excel skills required. No manual VLOOKUP. Just upload and get answers.
          </p>
        </div>

        <div className="grid sm:grid-cols-3 gap-8">
          {steps.map((step) => (
            <div key={step.num} className="relative">
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl font-black text-blue-100">{step.num}</span>
                <div className="bg-blue-50 rounded-xl p-2">{step.icon}</div>
              </div>
              <h3 className="font-bold text-gray-900 text-lg mb-2">{step.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{step.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  const features = [
    { icon: <ShieldCheck className="w-5 h-5" />, label: "File format validation" },
    { icon: <Zap className="w-5 h-5" />, label: "60-second analysis" },
    { icon: <TrendingUp className="w-5 h-5" />, label: "Rupee risk scoring" },
    { icon: <FileSpreadsheet className="w-5 h-5" />, label: "PDF report export" },
    { icon: <CheckCircle className="w-5 h-5" />, label: "AI mismatch explanations" },
    { icon: <ShieldCheck className="w-5 h-5" />, label: "AES-256 encrypted storage" },
  ];

  return (
    <section className="py-12 px-4 sm:px-6 bg-blue-700">
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-wrap justify-center gap-x-10 gap-y-4">
          {features.map((f) => (
            <div key={f.label} className="flex items-center gap-2 text-blue-100 text-sm font-medium">
              <span className="text-white">{f.icon}</span>
              {f.label}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  const plans = [
    {
      name: "Free",
      price: "₹0",
      period: "",
      desc: "Scan preview and basic checking",
      features: [
        "Upload GSTR-1 & GSTR-3B",
        "See total mismatch count",
        "See total rupee risk",
        "Top 3 mismatches preview",
      ],
      cta: "Get Started Free",
      popular: false,
      dark: false,
    },
    {
      name: "SMB",
      price: "₹999",
      period: "/month",
      desc: "Unlimited scans for standard businesses",
      features: [
        "Everything in Free",
        "Unlimited scans",
        "Up to 1,500 invoices / month",
        "PDF report download",
      ],
      cta: "Upgrade to SMB",
      popular: false,
      dark: false,
    },
    {
      name: "Growth",
      price: "₹2,499",
      period: "/month",
      desc: "For growing businesses needing ITC recovery",
      features: [
        "Everything in SMB",
        "ITC Recovery engine",
        "Up to 5,000 invoices / month",
        "Email & WhatsApp alerts",
      ],
      cta: "Upgrade to Growth",
      popular: true,
      dark: true,
    },
    {
      name: "CA Firm",
      price: "₹9,999",
      period: "/month",
      desc: "For CAs and tax practitioners",
      features: [
        "Everything in Growth",
        "White-label client portal",
        "Custom branding & colors",
        "Up to 50,000 invoices / month",
        "15% referral commission",
      ],
      cta: "Upgrade to CA Firm",
      popular: false,
      dark: false,
    },
  ];

  return (
    <section id="pricing" className="py-20 px-4 sm:px-6 bg-gray-50">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            Simple, transparent pricing
          </h2>
          <p className="text-gray-500 max-w-xl mx-auto">
            Choose the perfect plan for your business compliance and client portfolios.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {plans.map((p) => (
            <div
              key={p.name}
              className={`rounded-2xl p-6 border flex flex-col justify-between shadow-sm relative ${
                p.dark
                  ? "bg-blue-700 border-blue-800 text-white shadow-lg shadow-blue-200"
                  : "bg-white border-gray-200 text-gray-900"
              }`}
            >
              {p.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-orange-400 text-white text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                  Most Popular
                </div>
              )}
              <div>
                <div className="mb-4">
                  <div className={`text-xs font-bold uppercase tracking-wider mb-1 ${p.dark ? "text-blue-200" : "text-gray-400"}`}>
                    {p.name}
                  </div>
                  <div className="flex items-end gap-1">
                    <div className="text-3xl font-black">{p.price}</div>
                    <div className={`text-xs mb-1 ${p.dark ? "text-blue-200" : "text-gray-500"}`}>{p.period}</div>
                  </div>
                  <p className={`text-xs mt-2 leading-relaxed ${p.dark ? "text-blue-100" : "text-gray-500"}`}>{p.desc}</p>
                </div>
                <ul className="space-y-3 mb-8">
                  {p.features.map((item) => (
                    <li key={item} className="flex items-start gap-2 text-xs">
                      <CheckCircle className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${p.dark ? "text-blue-300" : "text-green-500"}`} />
                      <span className={p.dark ? "text-blue-100" : "text-gray-600"}>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <Link
                href={ROUTES.SIGNUP}
                className={`block text-center text-xs font-bold py-3 rounded-xl transition-colors ${
                  p.dark
                    ? "bg-white text-blue-700 hover:bg-blue-50"
                    : "bg-gray-100 text-gray-800 hover:bg-gray-200"
                }`}
              >
                {p.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Testimonials() {
  const testimonials = [
    {
      name: "Priya Sharma",
      role: "CA, Mumbai",
      body: "I used to spend 4 hours every month on reconciliation. GSTSense does it in 45 seconds. My clients love that I catch issues before filing.",
      stars: 5,
    },
    {
      name: "Rajesh Mehta",
      role: "CFO, Mehta Textiles",
      body: "We had a ₹3.2 lakh mismatch we had no idea about. GSTSense flagged it with the exact invoice numbers. Saved us a notice and penalty.",
      stars: 5,
    },
    {
      name: "Anita Krishnan",
      role: "Tax Consultant, Bangalore",
      body: "The AI explanations are the best part. I can share the report directly with clients and they actually understand what's wrong.",
      stars: 5,
    },
  ];

  return (
    <section id="testimonials" className="py-20 px-4 sm:px-6 bg-white">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            Trusted by CAs and finance teams across India
          </h2>
        </div>

        <div className="grid sm:grid-cols-3 gap-6">
          {testimonials.map((t) => (
            <div key={t.name} className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
              <div className="flex gap-0.5 mb-4">
                {Array.from({ length: t.stars }).map((_, i) => (
                  <Star key={i} className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                ))}
              </div>
              <p className="text-gray-700 text-sm leading-relaxed mb-4">&ldquo;{t.body}&rdquo;</p>
              <div>
                <div className="font-semibold text-gray-900 text-sm">{t.name}</div>
                <div className="text-gray-500 text-xs">{t.role}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="py-20 px-4 sm:px-6 bg-blue-700">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
          File with confidence this month
        </h2>
        <p className="text-blue-200 text-lg mb-8">
          Join thousands of CAs and business owners who reconcile before they file.
          Your first preview is completely free.
        </p>
        <Link
          href={ROUTES.SIGNUP}
          className="inline-flex items-center gap-2 bg-white text-blue-700 font-bold px-8 py-4 rounded-xl text-lg hover:bg-blue-50 transition-colors shadow-lg"
        >
          Start Free — No Credit Card Needed
          <ArrowRight className="w-5 h-5" />
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-400 py-12 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto grid sm:grid-cols-4 gap-8 mb-8">
        <div>
          <div className="flex items-center gap-2 text-white font-bold text-lg mb-3">
            <FileSpreadsheet className="w-5 h-5 text-blue-400" />
            GSTSense
          </div>
          <p className="text-sm leading-relaxed">
            AI-powered GST reconciliation for Indian businesses and CAs.
          </p>
        </div>

        <div>
          <div className="text-white font-semibold text-sm mb-3">Product</div>
          <ul className="space-y-2 text-sm">
            <li><a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a></li>
            <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
            <li><Link href={ROUTES.SIGNUP} className="hover:text-white transition-colors">Sign Up</Link></li>
          </ul>
        </div>

        <div>
          <div className="text-white font-semibold text-sm mb-3">Legal</div>
          <ul className="space-y-2 text-sm">
            <li><a href="#" className="hover:text-white transition-colors">Privacy Policy</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Terms of Service</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Refund Policy</a></li>
          </ul>
        </div>

        <div>
          <div className="text-white font-semibold text-sm mb-3">Contact</div>
          <ul className="space-y-2 text-sm">
            <li>support@gstsense.in</li>
            <li>WhatsApp: +91 98765 43210</li>
          </ul>
        </div>
      </div>

      <div className="border-t border-gray-800 pt-6 text-xs text-center">
        © {new Date().getFullYear()} GSTSense. All rights reserved. Not a substitute for professional CA advice.
      </div>
    </footer>
  );
}

export default function LandingPage() {
  return (
    <main>
      <Navbar />
      <Hero />
      <Pain />
      <HowItWorks />
      <Features />
      <Pricing />
      <Testimonials />
      <CTA />
      <Footer />
    </main>
  );
}
