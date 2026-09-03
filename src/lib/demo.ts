import { addDays, israelToUtc, todayInIsrael } from "./dates";
import type { City, EventFull, Genre, Organizer, Venue } from "./types";

/**
 * In-memory demo dataset mirroring supabase/seed.sql, for previewing the
 * site without a Supabase project (screenshots, local demos, CI).
 * Enabled ONLY with NEXT_PUBLIC_DEMO_DATA=1 — never in production.
 */
export function demoEnabled(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_DATA === "1";
}

const id = (n: number, kind: string) =>
  `00000000-0000-4000-8000-${kind.charCodeAt(0).toString(16).padStart(4, "0")}${String(n).padStart(8, "0")}`;

export const DEMO_CITIES: City[] = [
  { id: id(1, "c"), slug: "haifa", name_he: "חיפה", name_en: "Haifa", region: "north", lat: 32.794, lng: 34.9896, is_active: true },
  { id: id(2, "c"), slug: "krayot", name_he: "קריות", name_en: "Krayot", region: "north", lat: 32.8398, lng: 35.0771, is_active: true },
  { id: id(3, "c"), slug: "tel-aviv", name_he: "תל אביב", name_en: "Tel Aviv", region: "center", lat: 32.0853, lng: 34.7818, is_active: true },
  { id: id(4, "c"), slug: "jerusalem", name_he: "ירושלים", name_en: "Jerusalem", region: "center", lat: 31.7683, lng: 35.2137, is_active: true },
];

export const DEMO_GENRES: Genre[] = [
  ["techno", "טכנו"], ["hiphop", "היפ הופ"], ["mainstream", "מיינסטרים"], ["latin", "לאטינו"],
  ["mizrahi", "מזרחית"], ["rock", "רוק"], ["indie", "אינדי"], ["drag", "דראג"],
  ["student", "סטודנטים"], ["karaoke", "קריוקי"],
].map(([slug, name_he], i) => ({ id: id(i + 1, "g"), slug, name_he }));

const city = (slug: string) => DEMO_CITIES.find((c) => c.slug === slug)!;
const genre = (slug: string) => DEMO_GENRES.find((g) => g.slug === slug)!;

export const DEMO_VENUES: Venue[] = [
  { id: id(1, "v"), slug: "barbara", name_he: "ברברה", city_id: city("haifa").id, address: "שדרות בן גוריון 6, חיפה", lat: 32.8184, lng: 34.9885, instagram: "https://instagram.com/barbara.haifa", website: null, description_he: "בר מועדון במושבה הגרמנית עם ליינים מתחלפים.", image_url: null, is_active: true },
  { id: id(2, "v"), slug: "sirena", name_he: "הסירנה", city_id: city("haifa").id, address: "רחוב הנמל 32, חיפה", lat: 32.8206, lng: 34.9992, instagram: null, website: null, description_he: "מועדון אנדרגראונד בעיר התחתית.", image_url: null, is_active: true },
  { id: id(3, "v"), slug: "block", name_he: "הבלוק", city_id: city("tel-aviv").id, address: "שדרות הר ציון 157, תל אביב", lat: 32.0532, lng: 34.7794, instagram: "https://instagram.com/theblocktlv", website: "https://block-club.com", description_he: "מועדון הטכנו המרכזי של תל אביב בתחנה המרכזית.", image_url: null, is_active: true },
  { id: id(4, "v"), slug: "kuli-alma", name_he: "קולי עלמא", city_id: city("tel-aviv").id, address: "מקווה ישראל 10, תל אביב", lat: 32.0629, lng: 34.7757, instagram: "https://instagram.com/kulialma", website: "https://kulialma.com", description_he: "גלריה-מועדון עם מוזיקה ואמנות מקומית.", image_url: null, is_active: true },
  { id: id(5, "v"), slug: "yellow", name_he: "ילו סאבמרין", city_id: city("jerusalem").id, address: "הרכבים 13, ירושלים", lat: 31.7515, lng: 35.2093, instagram: null, website: "https://yellowsubmarine.org.il", description_he: "מרכז מוזיקה חי בתלפיות.", image_url: null, is_active: true },
];

export const DEMO_ORGANIZERS: Organizer[] = [
  { id: id(1, "o"), slug: "night-owls", name_he: "ינשופי לילה", instagram: "https://instagram.com/night.owls.il", website: null },
];

const venue = (slug: string) => DEMO_VENUES.find((v) => v.slug === slug)!;

type DemoEventSpec = {
  n: number;
  venue: string;
  dayOffset: number;
  time: string;
  endTime?: string;
  title: string;
  desc: string;
  short: string;
  genres: string[];
  priceMin?: number;
  priceMax?: number;
  minAge?: number;
  free?: boolean;
  ticketUrl?: string;
  provider?: EventFull["ticket_provider"];
  organizer?: string;
};

const SPECS: DemoEventSpec[] = [
  { n: 1, venue: "barbara", dayOffset: 0, time: "23:00", endTime: "05:00", title: "לילה של טכנו בברברה", desc: "ליין טכנו שבועי עם דיג׳יים מקומיים.", short: "techno-night", genres: ["techno"], priceMin: 60, priceMax: 80, minAge: 21, ticketUrl: "https://example.com/tickets/1", provider: "eventer", organizer: "night-owls" },
  { n: 2, venue: "sirena", dayOffset: 0, time: "23:30", title: "מסיבת היפ הופ בהסירנה", desc: "כל הבנגרים של הסצנה, סט פתיחה מקומי.", short: "hiphop-party", genres: ["hiphop"], priceMin: 50, priceMax: 70, minAge: 18, ticketUrl: "https://example.com/tickets/2", provider: "tixwise" },
  { n: 3, venue: "block", dayOffset: 0, time: "23:00", endTime: "07:00", title: "מרתון טכנו בהבלוק", desc: "שמונה שעות של טכנו עם אורח בינלאומי.", short: "techno-marathon", genres: ["techno"], priceMin: 90, priceMax: 120, minAge: 21, ticketUrl: "https://example.com/tickets/3", provider: "eventer", organizer: "night-owls" },
  { n: 4, venue: "kuli-alma", dayOffset: 0, time: "22:00", title: "ערב כניסה חופשית בקולי עלמא", desc: "דיג׳יי סטים, אמנות מקומית וכניסה חופשית.", short: "free-entry", genres: ["indie", "mainstream"], minAge: 24, free: true, provider: "free" },
  { n: 5, venue: "yellow", dayOffset: 0, time: "21:00", title: "הופעת אינדי חיה בילו סאבמרין", desc: "שלוש להקות אינדי מקומיות על במה אחת.", short: "indie-live", genres: ["indie", "rock"], priceMin: 70, priceMax: 70, ticketUrl: "https://example.com/tickets/5", provider: "other" },
  { n: 6, venue: "barbara", dayOffset: 1, time: "21:00", title: "קריוקי בברברה", desc: "ערב קריוקי פתוח, שירה על הבר.", short: "karaoke", genres: ["karaoke"], minAge: 18, free: true, provider: "free" },
  { n: 7, venue: "block", dayOffset: 1, time: "23:00", title: "מסיבת מיינסטרים בהבלוק", desc: "להיטים של עכשיו כל הלילה.", short: "mainstream", genres: ["mainstream"], priceMin: 80, priceMax: 100, minAge: 18, ticketUrl: "https://example.com/tickets/7", provider: "tixwise" },
  { n: 8, venue: "sirena", dayOffset: 2, time: "22:00", title: "לילה לאטיני בהסירנה", desc: "סלסה, באצ׳אטה ורגטון עד הבוקר.", short: "latin-night", genres: ["latin"], priceMin: 40, priceMax: 60, minAge: 18, ticketUrl: "https://example.com/tickets/8", provider: "eventer" },
  { n: 9, venue: "kuli-alma", dayOffset: 3, time: "22:00", title: "מופע דראג בקולי עלמא", desc: "מופע דראג מלא נצנצים ואחריו מסיבה.", short: "drag-show", genres: ["drag", "mainstream"], priceMin: 65, priceMax: 85, minAge: 21, ticketUrl: "https://example.com/tickets/9", provider: "eventer", organizer: "night-owls" },
  { n: 10, venue: "yellow", dayOffset: 5, time: "23:00", title: "מסיבת סטודנטים בילו סאבמרין", desc: "מסיבת פתיחת סמסטר עם הנחה לסטודנטים.", short: "student-party", genres: ["student", "mainstream"], priceMin: 30, priceMax: 50, minAge: 18, ticketUrl: "https://example.com/tickets/10", provider: "tixwise" },
];

function buildEvents(): EventFull[] {
  const today = todayInIsrael();
  const nowIso = new Date(Date.now() - 3 * 3600_000).toISOString(); // "updated 3 hours ago"
  return SPECS.map((s) => {
    const v = venue(s.venue);
    const c = DEMO_CITIES.find((x) => x.id === v.city_id)!;
    const date = addDays(today, s.dayOffset);
    const starts = israelToUtc(date, s.time);
    const ends = s.endTime
      ? (() => {
          const e = israelToUtc(date, s.endTime!);
          return (e < starts ? new Date(e.getTime() + 86_400_000) : e).toISOString();
        })()
      : null;
    const org = s.organizer ? DEMO_ORGANIZERS.find((o) => o.slug === s.organizer)! : null;
    return {
      id: id(s.n, "e"),
      slug: `${v.slug}-${date}-${s.short}`,
      title_he: s.title,
      description_he: s.desc,
      venue_id: v.id,
      city_id: c.id,
      organizer_id: org?.id ?? null,
      starts_at: starts.toISOString(),
      ends_at: ends,
      doors_at: null,
      price_min: s.free ? null : (s.priceMin ?? null),
      price_max: s.free ? null : (s.priceMax ?? null),
      currency: "ILS",
      min_age: s.minAge ?? null,
      ticket_url: s.ticketUrl ?? null,
      ticket_provider: s.provider ?? null,
      image_url: null,
      is_free: s.free ?? false,
      is_sold_out: false,
      status: "published" as const,
      source: "manual",
      source_ref: null,
      created_at: nowIso,
      updated_at: nowIso,
      venue: v,
      city: c,
      organizer: org,
      genres: s.genres.map(genre),
    };
  });
}

let cachedEvents: EventFull[] | null = null;
export function demoEvents(): EventFull[] {
  cachedEvents ??= buildEvents();
  return cachedEvents;
}
