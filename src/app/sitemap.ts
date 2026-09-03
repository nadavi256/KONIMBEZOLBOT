import type { MetadataRoute } from "next";
import { addDays, dayWindow, eventNightDate, todayInIsrael, weekendWindow } from "@/lib/dates";
import { getActiveCities, getEventsInWindow, getGenres } from "@/lib/queries";
import { getAllOrganizers, getAllPublishedEvents, getAllVenues } from "@/lib/queries";
import { siteUrl } from "@/lib/site";

export const revalidate = 3600;

/**
 * Dynamic sitemap. Only pages that pass the indexability rule are listed:
 * a list page needs ≥1 published event in its window; event pages drop out
 * 30 days after they happened.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  const now = new Date();
  const today = todayInIsrael();

  const [cities, genres, allEvents, venues, organizers] = await Promise.all([
    getActiveCities(),
    getGenres(),
    getAllPublishedEvents(),
    getAllVenues(),
    getAllOrganizers(),
  ]);

  // one query for everything in the next 60 days, bucketed in memory
  const horizon = await getEventsInWindow(dayWindow(today).from, dayWindow(addDays(today, 60)).to, {
    limit: 1000,
  });

  const newestUpdate = (predicate: (e: (typeof horizon)[number]) => boolean): Date | null => {
    const times = horizon.filter(predicate).map((e) => new Date(e.updated_at).getTime());
    return times.length ? new Date(Math.max(...times)) : null;
  };

  const entries: MetadataRoute.Sitemap = [
    { url: base, lastModified: newestUpdate(() => true) ?? now, changeFrequency: "hourly", priority: 1 },
  ];

  const tomorrow = addDays(today, 1);
  const weekendWin = weekendWindow();

  for (const city of cities) {
    const cityEvents = horizon.filter((e) => e.city_id === city.id);
    if (cityEvents.length === 0) continue;
    const cityMod = newestUpdate((e) => e.city_id === city.id) ?? now;
    entries.push({ url: `${base}/${city.slug}`, lastModified: cityMod, changeFrequency: "daily", priority: 0.9 });

    const hasOn = (date: string) => cityEvents.some((e) => eventNightDate(e.starts_at) === date);
    if (hasOn(today))
      entries.push({ url: `${base}/${city.slug}/tonight`, lastModified: cityMod, changeFrequency: "hourly", priority: 0.9 });
    if (hasOn(tomorrow))
      entries.push({ url: `${base}/${city.slug}/tomorrow`, lastModified: cityMod, changeFrequency: "daily", priority: 0.8 });
    const hasWeekend = cityEvents.some((e) => {
      const t = new Date(e.starts_at).getTime();
      return t >= weekendWin.from.getTime() && t < weekendWin.to.getTime();
    });
    if (hasWeekend)
      entries.push({ url: `${base}/${city.slug}/weekend`, lastModified: cityMod, changeFrequency: "daily", priority: 0.8 });

    // date pages within 60 days that actually have events
    const dates = [...new Set(cityEvents.map((e) => eventNightDate(e.starts_at)))];
    for (const d of dates) {
      if (d === today || d === tomorrow) continue;
      entries.push({ url: `${base}/${city.slug}/${d}`, lastModified: cityMod, changeFrequency: "daily", priority: 0.6 });
    }

    // genre pages with events in the next 14 days
    const in14 = cityEvents.filter(
      (e) => new Date(e.starts_at).getTime() < Date.now() + 14 * 86_400_000,
    );
    for (const genre of genres) {
      if (in14.some((e) => e.genres.some((g) => g.id === genre.id)))
        entries.push({ url: `${base}/${city.slug}/${genre.slug}`, lastModified: cityMod, changeFrequency: "daily", priority: 0.7 });
    }
  }

  // venue pages with upcoming events
  for (const venue of venues) {
    const venueEvents = horizon.filter((e) => e.venue_id === venue.id);
    if (venueEvents.length === 0) continue;
    entries.push({
      url: `${base}/venue/${venue.slug}`,
      lastModified: newestUpdate((e) => e.venue_id === venue.id) ?? now,
      changeFrequency: "daily",
      priority: 0.7,
    });
  }

  for (const organizer of organizers) {
    const orgEvents = horizon.filter((e) => e.organizer_id === organizer.id);
    if (orgEvents.length === 0) continue;
    entries.push({
      url: `${base}/organizer/${organizer.slug}`,
      lastModified: newestUpdate((e) => e.organizer_id === organizer.id) ?? now,
      changeFrequency: "weekly",
      priority: 0.5,
    });
  }

  // event pages: future + up to 30 days past
  const cutoff = Date.now() - 30 * 86_400_000;
  for (const e of allEvents) {
    if (new Date(e.starts_at).getTime() < cutoff) continue;
    entries.push({
      url: `${base}/event/${e.slug}`,
      lastModified: new Date(e.updated_at),
      changeFrequency: "daily",
      priority: 0.8,
    });
  }

  return entries;
}
