import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/", "/login", "/signup", "/reset-password", "/verify-email", "/forgot-password"];
const AUTH_PATHS = ["/login", "/signup"];

export function middleware(request: NextRequest): NextResponse {
  const { pathname, hostname } = request.nextUrl;
  const token = request.cookies.get("access_token")?.value;

  // CA white-label subdomain routing:
  // *.gstsense.in subdomains (other than www) are CA firm portals.
  // Store the subdomain in a header so pages can read it server-side.
  const hostHeader = request.headers.get("host") ?? hostname;
  const parts = hostHeader.split(".");
  // e.g. "myfirm.gstsense.in" → parts = ["myfirm", "gstsense", "in"]
  const isSubdomain =
    parts.length >= 3 &&
    !["www", "app", ""].includes(parts[0]) &&
    parts[1] === "gstsense";
  const caSlug = isSubdomain ? parts[0] : null;

  const response = NextResponse.next();

  if (caSlug) {
    response.headers.set("x-ca-slug", caSlug);
  }

  const isPublicPath = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith("/api/") || pathname.startsWith("/privacy") || pathname.startsWith("/terms")
  );
  const isAuthPath = AUTH_PATHS.some((p) => pathname === p);
  const isDashboardPath =
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/scan") ||
    pathname.startsWith("/notices") ||
    pathname.startsWith("/settings") ||
    pathname.startsWith("/itc");

  if (isDashboardPath && !token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthPath && token) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
