import { DEMO_CITIES, DEMO_GENRES, DEMO_ORGANIZERS, DEMO_VENUES, demoEnabled, demoEvents } from "./demo";
import { supabasePublic } from "./supabase/public";
import type { City, EventFull, Genre, Organizer, Venue } from "./types";

/**
 * Read-side data access for public pages. Every function degrades to an
 * empty result when Supabase is unreachable/unconfigured so pages render
 * their noindex fallback instead of erroring.
 */

const EVENT_SELECT =
  "*, venue:venues(*), city:cities(*), organizer:organizers(*), event_genres(genre:genres(*))";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function shapeEvent(row: any): EventFull {
  const { event_genres, ...rest } = row;
  return {
    ...rest,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    genres: (event_genres ?? []).map((eg: any) => eg.genre).filter(Boolean),
  } as EventFull;
}

export async function getActiveCities(): Promise<City[]> {
  if (demoEnabled()) return DEMO_CITIES;
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("cities").select("*").eq("is_active", true).order("name_he");
  return (data as City[]) ?? [];
}

export async function getCityBySlug(slug: string): Promise<City | null> {
  if (demoEnabled()) return DEMO_CITIES.find((c) => c.slug === slug) ?? null;
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("cities").select("*").eq("slug", slug).eq("is_active", true).maybeSingle();
  return (data as City) ?? null;
}

export async function getGenres(): Promise<Genre[]> {
  if (demoEnabled()) return DEMO_GENRES;
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("genres").select("*").order("slug");
  return (data as Genre[]) ?? [];
}

export async function getGenreBySlug(slug: string): Promise<Genre | null> {
  if (demoEnabled()) return DEMO_GENRES.find((g) => g.slug === slug) ?? null;
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("genres").select("*").eq("slug", slug).maybeSingle();
  return (data as Genre) ?? null;
}

type WindowOpts = { cityId?: string; genreId?: string; limit?: number };

/** Published events inside [from, to), soonest first. */
export async function getEventsInWindow(from: Date, to: Date, opts: WindowOpts = {}): Promise<EventFull[]> {
  if (demoEnabled()) {
    return demoEvents()
      .filter((e) => {
        const t = new Date(e.starts_at).getTime();
        if (t < from.getTime() || t >= to.getTime()) return false;
        if (opts.cityId && e.city_id !== opts.cityId) return false;
        if (opts.genreId && !e.genres.some((g) => g.id === opts.genreId)) return false;
        return true;
      })
      .slice(0, opts.limit ?? 100);
  }
  const sb = supabasePublic();
  if (!sb) return [];
  let q = sb
    .from("events")
    .select(EVENT_SELECT)
    .eq("status", "published")
    .gte("starts_at", from.toISOString())
    .lt("starts_at", to.toISOString())
    .order("starts_at", { ascending: true })
    .limit(opts.limit ?? 100);
  if (opts.cityId) q = q.eq("city_id", opts.cityId);
  const { data } = await q;
  let events = (data ?? []).map(shapeEvent);
  if (opts.genreId) events = events.filter((e) => e.genres.some((g) => g.id === opts.genreId));
  return events;
}

export async function getVenueBySlug(slug: string): Promise<Venue | null> {
  if (demoEnabled()) return DEMO_VENUES.find((v) => v.slug === slug) ?? null;
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("venues").select("*").eq("slug", slug).eq("is_active", true).maybeSingle();
  return (data as Venue) ?? null;
}

export async function getVenuesForCity(cityId: string): Promise<Venue[]> {
  if (demoEnabled()) return DEMO_VENUES.filter((v) => v.city_id === cityId);
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("venues").select("*").eq("city_id", cityId).eq("is_active", true).order("name_he");
  return (data as Venue[]) ?? [];
}

export async function getUpcomingEventsForVenue(venueId: string, limit = 30): Promise<EventFull[]> {
  if (demoEnabled())
    return demoEvents().filter((e) => e.venue_id === venueId).slice(0, limit);
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb
    .from("events")
    .select(EVENT_SELECT)
    .eq("status", "published")
    .eq("venue_id", venueId)
    .gte("starts_at", new Date().toISOString())
    .order("starts_at", { ascending: true })
    .limit(limit);
  return (data ?? []).map(shapeEvent);
}

export async function getUpcomingEventsForOrganizer(organizerId: string, limit = 30): Promise<EventFull[]> {
  if (demoEnabled())
    return demoEvents().filter((e) => e.organizer_id === organizerId).slice(0, limit);
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb
    .from("events")
    .select(EVENT_SELECT)
    .eq("status", "published")
    .eq("organizer_id", organizerId)
    .gte("starts_at", new Date().toISOString())
    .order("starts_at", { ascending: true })
    .limit(limit);
  return (data ?? []).map(shapeEvent);
}

export async function getEventBySlug(slug: string): Promise<EventFull | null> {
  if (demoEnabled()) return demoEvents().find((e) => e.slug === slug) ?? null;
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("events").select(EVENT_SELECT).eq("slug", slug).maybeSingle();
  return data ? shapeEvent(data) : null;
}

export async function getOrganizerBySlug(slug: string): Promise<Organizer | null> {
  if (demoEnabled()) return DEMO_ORGANIZERS.find((o) => o.slug === slug) ?? null;
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("organizers").select("*").eq("slug", slug).maybeSingle();
  return (data as Organizer) ?? null;
}

/** For the sitemap: every published event (slug + updated_at + starts_at). */
export async function getAllPublishedEvents(): Promise<
  Pick<EventFull, "slug" | "updated_at" | "starts_at">[]
> {
  if (demoEnabled()) return demoEvents();
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb
    .from("events")
    .select("slug, updated_at, starts_at")
    .eq("status", "published")
    .order("starts_at", { ascending: false })
    .limit(5000);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data as any[]) ?? [];
}

export async function getAllVenues(): Promise<Venue[]> {
  if (demoEnabled()) return DEMO_VENUES;
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("venues").select("*").eq("is_active", true);
  return (data as Venue[]) ?? [];
}

export async function getAllOrganizers(): Promise<Organizer[]> {
  if (demoEnabled()) return DEMO_ORGANIZERS;
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("organizers").select("*");
  return (data as Organizer[]) ?? [];
}
