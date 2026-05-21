import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { GST_DEADLINES } from "./constants"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatRupees(
  amount: string | number,
  showSymbol = true,
): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount
  if (isNaN(num)) return showSymbol ? "₹0" : "0"

  const absNum = Math.abs(num)
  const intPart = Math.floor(absNum).toString()
  const decPart = (absNum % 1).toFixed(2).slice(1) // ".XX"

  let formatted: string
  if (intPart.length <= 3) {
    formatted = intPart
  } else {
    // Indian grouping: last 3, then groups of 2
    let result = intPart.slice(-3)
    let remaining = intPart.slice(0, -3)
    while (remaining.length > 0) {
      result = remaining.slice(-2) + "," + result
      remaining = remaining.slice(0, -2)
    }
    formatted = result
  }

  const sign = num < 0 ? "-" : ""
  const withDecimal = `${sign}${formatted}${decPart}`
  return showSymbol ? `₹${withDecimal}` : withDecimal
}

export function formatMonth(scanMonth: string): string {
  try {
    const [year, month] = scanMonth.split("-")
    const date = new Date(parseInt(year), parseInt(month) - 1, 1)
    return date.toLocaleDateString("en-IN", { month: "long", year: "numeric" })
  } catch {
    return scanMonth
  }
}

export function formatDate(isoString: string): string {
  try {
    return new Date(isoString).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "long",
      year: "numeric",
    })
  } catch {
    return isoString
  }
}

export function formatDateTime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleString("en-IN", {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    })
  } catch {
    return isoString
  }
}

export function getRiskLevel(
  totalRupeeRisk: string | number,
): { label: string; color: string; bgColor: string } {
  const amount =
    typeof totalRupeeRisk === "string"
      ? parseFloat(totalRupeeRisk)
      : totalRupeeRisk

  if (amount < 10000) {
    return { label: "LOW", color: "text-green-700", bgColor: "bg-green-100" }
  }
  if (amount < 100000) {
    return {
      label: "MEDIUM",
      color: "text-amber-700",
      bgColor: "bg-amber-100",
    }
  }
  if (amount < 500000) {
    return { label: "HIGH", color: "text-red-700", bgColor: "bg-red-100" }
  }
  return { label: "CRITICAL", color: "text-red-900", bgColor: "bg-red-200" }
}

export function getNextGSTDeadlines(): {
  gstr1: Date
  gstr3b: Date
  daysToGstr1: number
  daysToGstr3b: number
} {
  const now = new Date()
  const today = now.getDate()
  const currentYear = now.getFullYear()
  const currentMonth = now.getMonth() // 0-indexed

  function nextDeadline(dayOfMonth: number): Date {
    if (today < dayOfMonth) {
      return new Date(currentYear, currentMonth, dayOfMonth)
    }
    // Past this month's deadline — next month
    const next = new Date(currentYear, currentMonth + 1, dayOfMonth)
    return next
  }

  function daysUntil(date: Date): number {
    const ms = date.getTime() - new Date().setHours(0, 0, 0, 0)
    return Math.ceil(ms / (1000 * 60 * 60 * 24))
  }

  const gstr1 = nextDeadline(GST_DEADLINES.GSTR1)
  const gstr3b = nextDeadline(GST_DEADLINES.GSTR3B)

  return {
    gstr1,
    gstr3b,
    daysToGstr1: daysUntil(gstr1),
    daysToGstr3b: daysUntil(gstr3b),
  }
}

export function truncateGSTIN(gstin: string): string {
  if (gstin.length !== 15) return gstin
  return `${gstin.slice(0, 7)}****${gstin.slice(11)}`
}

export function validateGSTIN(gstin: string): boolean {
  const pattern = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/
  return pattern.test(gstin.trim().toUpperCase())
}
