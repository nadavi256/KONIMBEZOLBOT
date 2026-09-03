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
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("cities").select("*").eq("is_active", true).order("name_he");
  return (data as City[]) ?? [];
}

export async function getCityBySlug(slug: string): Promise<City | null> {
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("cities").select("*").eq("slug", slug).eq("is_active", true).maybeSingle();
  return (data as City) ?? null;
}

export async function getGenres(): Promise<Genre[]> {
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("genres").select("*").order("slug");
  return (data as Genre[]) ?? [];
}

export async function getGenreBySlug(slug: string): Promise<Genre | null> {
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("genres").select("*").eq("slug", slug).maybeSingle();
  return (data as Genre) ?? null;
}

type WindowOpts = { cityId?: string; genreId?: string; limit?: number };

/** Published events inside [from, to), soonest first. */
export async function getEventsInWindow(from: Date, to: Date, opts: WindowOpts = {}): Promise<EventFull[]> {
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
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("venues").select("*").eq("slug", slug).eq("is_active", true).maybeSingle();
  return (data as Venue) ?? null;
}

export async function getVenuesForCity(cityId: string): Promise<Venue[]> {
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("venues").select("*").eq("city_id", cityId).eq("is_active", true).order("name_he");
  return (data as Venue[]) ?? [];
}

export async function getUpcomingEventsForVenue(venueId: string, limit = 30): Promise<EventFull[]> {
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
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("events").select(EVENT_SELECT).eq("slug", slug).maybeSingle();
  return data ? shapeEvent(data) : null;
}

export async function getOrganizerBySlug(slug: string): Promise<Organizer | null> {
  const sb = supabasePublic();
  if (!sb) return null;
  const { data } = await sb.from("organizers").select("*").eq("slug", slug).maybeSingle();
  return (data as Organizer) ?? null;
}

/** For the sitemap: every published event (slug + updated_at + starts_at). */
export async function getAllPublishedEvents(): Promise<
  Pick<EventFull, "slug" | "updated_at" | "starts_at">[]
> {
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
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("venues").select("*").eq("is_active", true);
  return (data as Venue[]) ?? [];
}

export async function getAllOrganizers(): Promise<Organizer[]> {
  const sb = supabasePublic();
  if (!sb) return [];
  const { data } = await sb.from("organizers").select("*");
  return (data as Organizer[]) ?? [];
}
