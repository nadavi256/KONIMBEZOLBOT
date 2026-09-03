import type { EventFull } from "./types";

/** "60–80 ₪" / "60 ₪" / "כניסה חופשית" / null when unknown. */
export function priceLabel(e: Pick<EventFull, "is_free" | "price_min" | "price_max">): string | null {
  if (e.is_free) return "כניסה חופשית";
  const min = e.price_min != null ? Math.round(Number(e.price_min)) : null;
  const max = e.price_max != null ? Math.round(Number(e.price_max)) : null;
  // U+2066/U+2069 isolate the range so RTL text doesn't flip it to "80–60"
  if (min != null && max != null && min !== max) return `⁦${min}–${max}⁩ ₪`;
  if (min != null) return `${min} ₪`;
  if (max != null) return `${max} ₪`;
  return null;
}

export function ageLabel(minAge: number | null): string | null {
  return minAge ? `${minAge}+` : null;
}

/** Trim + normalize a Hebrew/Latin string into a URL slug segment. */
export function slugify(input: string, maxLen = 40): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/['"״׳`]/g, "")
    .replace(/[^a-z0-9֐-׿]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, maxLen)
    .replace(/-+$/g, "");
}
