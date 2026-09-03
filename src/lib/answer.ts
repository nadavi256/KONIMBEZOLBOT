import { israelTime } from "./dates";
import { priceLabel } from "./format";
import type { EventFull } from "./types";

/**
 * The one-sentence direct answer at the top of every list page — plain facts
 * generated from data, phrased the way a person would answer the question.
 * This is the sentence AI engines lift, so it must be unique and precise.
 */
export function answerSentence(events: EventFull[], scopeHe: string): string {
  if (events.length === 0) {
    return `${scopeHe} לא מתוכננים כרגע אירועים — בדקו את הימים הקרובים למטה.`;
  }
  const biggest = pickHeadliner(events);
  const genre = biggest.genres[0]?.name_he;
  const details = [
    genre,
    `מ-${israelTime(biggest.starts_at)}`,
    priceLabel(biggest) ?? undefined,
  ]
    .filter(Boolean)
    .join(", ");
  if (events.length === 1) {
    return `${scopeHe} יש אירוע אחד: ${biggest.title_he} ב${biggest.venue.name_he} (${details}).`;
  }
  return `${scopeHe} יש ${events.length} אירועים, הבולט ב${biggest.venue.name_he} (${details}).`;
}

/** Headliner = the priciest event, then the earliest-starting. */
function pickHeadliner(events: EventFull[]): EventFull {
  return [...events].sort((a, b) => {
    const pa = Number(a.price_max ?? a.price_min ?? 0);
    const pb = Number(b.price_max ?? b.price_min ?? 0);
    if (pb !== pa) return pb - pa;
    return a.starts_at.localeCompare(b.starts_at);
  })[0];
}

export type Faq = { q: string; a: string };

/** 3–5 data-driven Q&As for a list page. */
export function buildFaq(events: EventFull[], scopeHe: string): Faq[] {
  if (events.length === 0) return [];
  const faqs: Faq[] = [];

  const prices = events
    .flatMap((e) => [e.price_min, e.price_max])
    .filter((p): p is number => p != null)
    .map(Number);
  const freeEvents = events.filter((e) => e.is_free);
  if (prices.length > 0) {
    const min = Math.round(Math.min(...prices));
    const max = Math.round(Math.max(...prices));
    faqs.push({
      q: `כמה עולה כניסה ${scopeHe}?`,
      a:
        min === max
          ? `הכניסה עולה ${min} ₪.`
          : `המחירים נעים בין ${min} ₪ ל-${max} ₪, תלוי באירוע.` +
            (freeEvents.length > 0 ? ` יש גם ${freeEvents.length === 1 ? "אירוע אחד" : `${freeEvents.length} אירועים`} בכניסה חופשית.` : ""),
    });
  }

  const ages = events.map((e) => e.min_age).filter((a): a is number => a != null);
  if (ages.length > 0) {
    const minAge = Math.min(...ages);
    const maxAge = Math.max(...ages);
    faqs.push({
      q: `מאיזה גיל אפשר להיכנס?`,
      a:
        minAge === maxAge
          ? `הכניסה מגיל ${minAge}+.`
          : `תלוי באירוע: הגיל המינימלי נע בין ${minAge}+ ל-${maxAge}+.`,
    });
  }

  if (freeEvents.length > 0) {
    faqs.push({
      q: `איפה יש כניסה חופשית?`,
      a: `כניסה חופשית יש ב${freeEvents.map((e) => e.venue.name_he).join(", ב")}.`,
    });
  }

  const earliest = [...events].sort((a, b) => a.starts_at.localeCompare(b.starts_at))[0];
  faqs.push({
    q: `באיזו שעה מתחילים האירועים?`,
    a: `האירוע הראשון מתחיל ב-${israelTime(earliest.starts_at)} ב${earliest.venue.name_he}.`,
  });

  const ticketed = events.filter((e) => e.ticket_url);
  if (ticketed.length > 0 && faqs.length < 5) {
    faqs.push({
      q: `איך קונים כרטיסים?`,
      a: `ל-${ticketed.length === 1 ? "אירוע אחד" : `${ticketed.length} אירועים`} יש מכירה מוקדמת אונליין — קישור לכרטיסים מופיע בכל כרטיס אירוע.`,
    });
  }

  return faqs.slice(0, 5);
}
