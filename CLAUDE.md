# NIGHTLIFE — Israeli nightlife events site (SEO + GEO machine)

## What this is
A Hebrew, RTL, mobile-first website that answers questions like
"מה יש הערב בחיפה", "מסיבות טכנו בתל אביב סופ"ש", "אירועים בקריות".
It must be cited by Google AI Overviews and other AI engines, rank in classic
search, and later ship as a mobile app (Capacitor) from the same codebase.

Model to copy: the "זמנים" site — thousands of programmatic pages, each giving
one precise answer at the top, clean schema, fresh data, weekly growth.

Phase 1: events are entered MANUALLY through an admin panel.
Phase 2 (later): scrapers/integrations write into the same tables.
Design every table and page so Phase 2 needs no schema change.

## Stack (do not deviate without asking)
- Next.js 15, App Router, TypeScript, Tailwind. Server components by default.
- Supabase: Postgres + Auth (admin only) + Storage (event images).
- Deploy: Vercel. ISR with `revalidate = 3600` on all public pages,
  `revalidatePath` on every admin save.
- Hebrew UI, `dir="rtl"`, `lang="he"`. Font: Heebo or Assistant.
- Keep all app logic in `/src`. No native code now, but keep routes and
  components Capacitor-friendly (no Node-only APIs in client components).

## Data model (Supabase, SQL migrations in /supabase/migrations)
cities
  id, slug (e.g. haifa), name_he, name_en, region, lat, lng, is_active
venues
  id, slug, name_he, city_id, address, lat, lng, instagram, website,
  description_he, image_url, is_active
organizers
  id, slug, name_he, instagram, website
genres
  id, slug (techno, hiphop, mainstream, latin, mizrahi, rock, indie, drag,
  student, karaoke), name_he
events
  id, slug, title_he, description_he, venue_id, city_id (denormalized),
  organizer_id null, starts_at timestamptz, ends_at null, doors_at null,
  price_min, price_max, currency 'ILS', min_age, ticket_url, ticket_provider
  (eventer|tixwise|zappa|other|free|door), image_url, is_free bool,
  is_sold_out bool, status (draft|published|cancelled),
  source (manual|scraper_x...) DEFAULT 'manual', source_ref null,
  created_at, updated_at
event_genres (event_id, genre_id)

Indexes: events(city_id, starts_at), events(status, starts_at), events(slug).
Slug rule for events: `{venue-slug}-{yyyy-mm-dd}-{short-title}` — stable, unique.

## Admin (/admin, Supabase Auth, single admin user)
- Event form: all fields above, venue picker with "add new venue" inline,
  genre multi-select, image upload to Storage, "duplicate this event" button
  (recurring parties), and date-only quick-add (defaults 23:00 start).
- Duplicate warning: same venue + same date already exists.
- Table view of upcoming events with edit/cancel/publish.
- Every save calls revalidatePath for: home, the city pages, venue page,
  event page, sitemap.

## Public routes (all statically generated + ISR)
/                              — today across all active cities
/[city]                        — hub: tonight / weekend / genres / venues
/[city]/tonight                — "הערב ב{עיר}"
/[city]/tomorrow
/[city]/weekend                — Thu–Sat of the current week
/[city]/[yyyy-mm-dd]           — any date, next 60 days only
/[city]/[genre]                — upcoming in this genre, next 14 days
/venue/[slug]                  — venue page with its upcoming events
/event/[slug]                  — event page
/organizer/[slug]

Indexing rule (critical — avoid thin pages):
- A list page is indexable ONLY if it has ≥ 1 published event in its window.
  Otherwise render it with `robots: noindex,follow` and a useful fallback
  ("אין אירועים הערב, הנה מה שיש בסופ"ש…").
- Past event pages: keep them, add noindex after 30 days, keep internal links.

## Page template (every list page, in this order)
1. H1: exact question phrasing, e.g. "מסיבות בחיפה הערב, יום חמישי 3 בספטמבר"
2. Direct-answer paragraph, ONE sentence, plain facts:
   "הערב בחיפה יש 6 מסיבות, הגדולה ב-{venue} (טכנו, מ-23:00, 60–80 ₪)."
   This sentence is what AI engines lift. Generate it from data, never fluff.
3. "עודכן לפני X שעות" (from max(events.updated_at)).
4. Event cards: time, venue, genre chips, price, age, CTA "לכרטיסים".
5. Short FAQ (3–5 Q/A) generated from data:
   "כמה עולה כניסה?", "מאיזה גיל?", "איפה יש כניסה חופשית?"
6. Internal links block: other days, other genres, nearby cities, venues.
7. Breadcrumbs.

## SEO / GEO requirements (non-negotiable)
- `generateMetadata` on every route: title ≤ 60 chars, description ≤ 155,
  canonical, OG image (dynamic via `next/og`, RTL Hebrew).
- JSON-LD per page type:
  - list pages: ItemList of Event + FAQPage + BreadcrumbList
  - event page: Event (name, startDate, endDate, location as Place with
    address + geo, offers with price/priceCurrency/url/availability,
    organizer, image, eventStatus, eventAttendanceMode)
  - venue page: NightClub / MusicVenue + ItemList
  Validate with Google Rich Results test; zero errors, zero warnings.
- `/sitemap.xml`: dynamic, split by type, `lastmod` from updated_at.
  Only indexable pages go in.
- `/robots.txt`: allow all, explicitly allow GPTBot, ClaudeBot, Claude-Web,
  PerplexityBot, Google-Extended, CCBot, Applebot-Extended. Sitemap line.
- `/llms.txt`: short description of the site + links to city hubs.
- `<link rel="alternate" hreflang="he-IL">`.
- No client-side data fetching for content. HTML must contain everything.
- Core Web Vitals: LCP < 2.5s on 4G mobile, images via next/image, no
  layout shift, no third-party scripts except GA4 (loaded afterInteractive).
- GA4 + Google Search Console verification tag in env vars.

## Content quality rules
- Never generate empty or near-duplicate pages just to have URLs.
- Every H1 / answer sentence must be unique and data-driven.
- Hebrew dates and weekdays everywhere ("יום חמישי, 3 בספטמבר").
- Prices as "60–80 ₪", free as "כניסה חופשית".

## Later (do not build now, just don't block it)
- Scrapers (n8n + Playwright on external VPS) writing events with
  source != 'manual' and source_ref for dedup.
- Capacitor wrapper, push notifications ("מה יש הערב").
- Weekly n8n job pulling Search Console API → Telegram report.
- Affiliate / paid promotion of events.

## Build order (Phase 1, target: 3–4 days)
1. Supabase schema + seed: 4 cities (חיפה, קריות, תל אביב, ירושלים),
   10 genres, 5 venues, 10 fake events. Screenshot the tables.
2. Admin panel with the event form. Enter 3 real events. Screenshot.
3. /[city]/tonight with the full page template + JSON-LD. Validate in
   Rich Results test. Screenshot.
4. All other public routes, sitemap, robots, llms.txt, OG images.
5. Deploy to Vercel, submit sitemap in GSC, connect GA4.
Stop after each step and show the result before continuing.
