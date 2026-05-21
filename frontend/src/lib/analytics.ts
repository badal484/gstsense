import posthog from "posthog-js";

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST;

export function initAnalytics(): void {
  if (!POSTHOG_KEY) return;
  if (typeof window === "undefined") return;

  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST || "https://app.posthog.com",
    capture_pageview: false,
    persistence: "localStorage",
  });
}

export function trackEvent(event: string, properties?: Record<string, unknown>): void {
  if (typeof window === "undefined") return;
  posthog.capture(event, properties);
}

export function identifyUser(userId: string, traits?: Record<string, unknown>): void {
  if (typeof window === "undefined") return;
  posthog.identify(userId, traits);
}

export function resetAnalytics(): void {
  if (typeof window === "undefined") return;
  posthog.reset();
}
