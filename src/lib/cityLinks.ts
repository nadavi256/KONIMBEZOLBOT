import { addDays, hebrewDate, todayInIsrael } from "./dates";
import { getActiveCities, getGenres, getVenuesForCity } from "./queries";
import type { City } from "./types";
import type { LinkGroup } from "@/components/InternalLinks";

/**
 * The internal-links block every city page carries: other days, genres,
 * nearby cities, venues. Fetches are small and cached with the page (ISR).
 */
export async function cityLinkGroups(city: City, opts: { exclude?: string } = {}): Promise<LinkGroup[]> {
  const [genres, venues, cities] = await Promise.all([
    getGenres(),
    getVenuesForCity(city.id),
    getActiveCities(),
  ]);
  const today = todayInIsrael();

  const dayLinks = [
    { name: `הערב ב${city.name_he}`, href: `/${city.slug}/tonight` },
    { name: `מחר ב${city.name_he}`, href: `/${city.slug}/tomorrow` },
    { name: `סופ"ש ב${city.name_he}`, href: `/${city.slug}/weekend` },
    ...[2, 3, 4].map((n) => ({
      name: hebrewDate(addDays(today, n)),
      href: `/${city.slug}/${addDays(today, n)}`,
    })),
  ].filter((l) => l.href !== opts.exclude);

  return [
    { title: "ימים נוספים", links: dayLinks },
    {
      title: "לפי ז'אנר",
      links: genres.map((g) => ({ name: `${g.name_he} ב${city.name_he}`, href: `/${city.slug}/${g.slug}` })),
    },
    {
      title: "ערים בסביבה",
      links: cities
        .filter((c) => c.id !== city.id)
        .map((c) => ({ name: `אירועים ב${c.name_he}`, href: `/${c.slug}` })),
    },
    {
      title: "מקומות בעיר",
      links: venues.map((v) => ({ name: v.name_he, href: `/venue/${v.slug}` })),
    },
  ];
}
