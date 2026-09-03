export const SITE_NAME = "לילה בעיר";
export const SITE_DESCRIPTION =
  "כל המסיבות והאירועים של הלילה בישראל — לפי עיר, תאריך וז'אנר, עם מחירים ושעות מעודכנים.";

export function siteUrl(): string {
  return (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/+$/, "");
}

export function absoluteUrl(path: string): string {
  return `${siteUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Dynamic OG image URL for a page. */
export function ogImageUrl(title: string, subtitle?: string): string {
  const params = new URLSearchParams({ title });
  if (subtitle) params.set("subtitle", subtitle);
  return absoluteUrl(`/og?${params.toString()}`);
}

/** Clamp metadata strings to Google's display limits. */
export function clamp(s: string, max: number): string {
  return s.length <= max ? s : `${s.slice(0, max - 1).trimEnd()}…`;
}
