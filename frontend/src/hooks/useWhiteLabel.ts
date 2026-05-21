"use client";

import { useEffect, useState } from "react";

export interface WhiteLabelConfig {
  caSlug: string | null;
  isWhiteLabel: boolean;
  brandName: string;
  brandColor: string;
}

const DEFAULT_CONFIG: WhiteLabelConfig = {
  caSlug: null,
  isWhiteLabel: false,
  brandName: "GSTSense",
  brandColor: "#1d4ed8",
};

/**
 * Returns white-label branding for CA firm subdomains.
 * Falls back to GSTSense defaults on the main domain.
 *
 * The CA slug is injected by the Next.js middleware into a meta tag
 * rendered in the root layout, so this hook reads it client-side.
 */
export function useWhiteLabel(): WhiteLabelConfig {
  const [config, setConfig] = useState<WhiteLabelConfig>(DEFAULT_CONFIG);

  useEffect(() => {
    // Read the slug injected by middleware via a <meta name="x-ca-slug"> tag.
    const meta = document.querySelector<HTMLMetaElement>('meta[name="x-ca-slug"]');
    const slug = meta?.content ?? null;

    if (!slug) {
      setConfig(DEFAULT_CONFIG);
      return;
    }

    // Derive a display name from the slug (e.g. "myfirm" → "Myfirm")
    const brandName = slug.charAt(0).toUpperCase() + slug.slice(1) + " GST Portal";

    setConfig({
      caSlug: slug,
      isWhiteLabel: true,
      brandName,
      brandColor: "#1d4ed8",
    });
  }, []);

  return config;
}
