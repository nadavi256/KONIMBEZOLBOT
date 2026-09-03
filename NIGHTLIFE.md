# NIGHTLIFE — setup & operations

The Next.js app in this repo (root `package.json`, `/src`, `/supabase`) is the
Hebrew nightlife-events site described in [CLAUDE.md](./CLAUDE.md). The Python
files are the legacy KONIMBEZOL Telegram bot and are unrelated.

## 1. Supabase setup

1. Create a project at [supabase.com](https://supabase.com).
2. Run the migration: SQL editor → paste `supabase/migrations/0001_initial_schema.sql` → run.
   (Or `supabase db push` with the CLI.)
3. Seed demo data: paste `supabase/seed.sql` → run. Event dates are relative to
   "today", so the seed always produces a live-looking site.
4. Create the single admin user: Authentication → Users → **Add user** (email + password,
   auto-confirm). No signup flow exists in the app — this is the only way in.
5. The migration already creates the public `event-images` storage bucket with
   the right policies.

## 2. Environment variables

Copy `.env.example` to `.env.local` and fill in:

| Variable | Where to find it |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Project Settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Project Settings → API |
| `NEXT_PUBLIC_SITE_URL` | Your production URL (used for canonicals, sitemap, OG) |
| `NEXT_PUBLIC_GA4_ID` | GA4 measurement ID (optional; script loads afterInteractive) |
| `NEXT_PUBLIC_GSC_VERIFICATION` | Search Console HTML-tag token (optional) |

Without Supabase env vars the site still builds and renders empty-state
fallbacks (useful for CI); with them, everything goes live.

## 3. Run

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # production build (ISR, revalidate=3600 on public pages)
```

Admin panel: `/admin` (redirects to `/admin/login`). Every save revalidates
home, the affected city's pages, the venue page, the event page, the sitemap
and llms.txt.

## 4. Deploy (Vercel)

1. Import the repo in Vercel (framework preset: Next.js, root directory: repo root).
2. Add the env vars above in Project → Settings → Environment Variables.
3. After the first deploy: submit `https://<domain>/sitemap.xml` in Google
   Search Console and verify the site with the `NEXT_PUBLIC_GSC_VERIFICATION` tag.

## 5. What's where

- `supabase/migrations/` — schema (cities, venues, organizers, genres, events,
  event_genres + RLS + storage bucket). Phase 2 scrapers write the same tables
  with `source != 'manual'` — no schema change needed.
- `src/app/` — public routes (`/`, `/[city]`, `/[city]/tonight|tomorrow|weekend`,
  `/[city]/[yyyy-mm-dd or genre]`, `/venue/[slug]`, `/event/[slug]`,
  `/organizer/[slug]`), plus `sitemap.ts`, `robots.ts`, `llms.txt`, `/og` images,
  and the `/admin` panel.
- `src/lib/` — Israel-timezone date logic (nights run 06:00→06:00), queries,
  JSON-LD builders, the data-driven answer sentence + FAQ generators.
- Indexing rule: list pages with zero events render `noindex,follow` with a
  weekend fallback; event pages go `noindex` 30 days after the event; the
  sitemap only lists indexable pages.
