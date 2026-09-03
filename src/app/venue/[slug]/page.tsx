import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { EventCard, EventGrid } from "@/components/EventCard";
import { JsonLd } from "@/components/JsonLd";
import { updatedAgoHe } from "@/lib/dates";
import { getCityBySlug, getUpcomingEventsForVenue, getVenueBySlug } from "@/lib/queries";
import { getActiveCities } from "@/lib/queries";
import { breadcrumbJsonLd, itemListJsonLd, venueJsonLd, type Crumb } from "@/lib/seo";
import { clamp, ogImageUrl, SITE_NAME } from "@/lib/site";

export const revalidate = 3600;
export const dynamicParams = true;

type Props = { params: Promise<{ slug: string }> };

async function loadData(slug: string) {
  const venue = await getVenueBySlug(slug);
  if (!venue) return null;
  const [cities, events] = await Promise.all([getActiveCities(), getUpcomingEventsForVenue(venue.id)]);
  const city = cities.find((c) => c.id === venue.city_id) ?? null;
  return { venue, city, events };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const data = await loadData(slug);
  if (!data) return {};
  const { venue, city, events } = data;
  const canonical = `/venue/${venue.slug}`;
  const cityName = city?.name_he ?? "";
  const description = clamp(
    events.length > 0
      ? `${venue.name_he}${cityName ? ` ב${cityName}` : ""}: ${events.length} אירועים קרובים, שעות, מחירים וכרטיסים.`
      : `${venue.name_he}${cityName ? ` ב${cityName}` : ""} — פרטים, כתובת ואירועים קרובים.`,
    155,
  );
  return {
    title: { absolute: clamp(`${venue.name_he}: אירועים קרובים | ${SITE_NAME}`, 60) },
    description,
    alternates: { canonical, languages: { "he-IL": canonical } },
    openGraph: { title: venue.name_he, description, images: [ogImageUrl(venue.name_he, cityName)] },
    robots: events.length > 0 ? { index: true, follow: true } : { index: false, follow: true },
  };
}

export default async function VenuePage({ params }: Props) {
  const { slug } = await params;
  const data = await loadData(slug);
  if (!data) notFound();
  const { venue, city, events } = data;
  const updated = updatedAgoHe(events.map((e) => e.updated_at));
  const crumbs: Crumb[] = [
    { name: "ראשי", href: "/" },
    ...(city ? [{ name: city.name_he, href: `/${city.slug}` }] : []),
    { name: venue.name_he, href: `/venue/${venue.slug}` },
  ];

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <JsonLd
        data={[
          venueJsonLd(venue, city?.name_he ?? ""),
          itemListJsonLd(events),
          breadcrumbJsonLd(crumbs),
        ]}
      />
      {venue.image_url ? (
        <div className="relative mb-5 h-48 w-full overflow-hidden rounded-2xl sm:h-64">
          <Image src={venue.image_url} alt={venue.name_he} fill sizes="(max-width: 768px) 100vw, 768px" className="object-cover" priority />
        </div>
      ) : null}
      <h1 className="text-3xl font-black leading-tight sm:text-4xl">
        {venue.name_he}
        {city ? ` — ${city.name_he}` : ""}
      </h1>
      {venue.address ? <p className="mt-1 text-zinc-500">{venue.address}</p> : null}
      {venue.description_he ? <p className="mt-3 text-lg text-zinc-300">{venue.description_he}</p> : null}
      <div className="mt-2 flex gap-3 text-sm">
        {venue.instagram ? (
          <a href={venue.instagram} rel="nofollow noopener" target="_blank" className="text-neon-300 underline">אינסטגרם</a>
        ) : null}
        {venue.website ? (
          <a href={venue.website} rel="nofollow noopener" target="_blank" className="text-neon-300 underline">אתר</a>
        ) : null}
      </div>

      <section className="mt-8">
        <h2 className="text-xl font-bold">אירועים קרובים ב{venue.name_he}</h2>
        {updated ? <p className="mt-1 text-sm text-zinc-500">{updated}</p> : null}
        {events.length > 0 ? (
          <EventGrid>
            {events.map((e) => (
              <EventCard key={e.id} event={e} showDate />
            ))}
          </EventGrid>
        ) : (
          <p className="mt-3 surface p-4 text-zinc-500">
            אין כרגע אירועים מפורסמים.{" "}
            {city ? (
              <>
                ראו{" "}
                <Link href={`/${city.slug}`} className="text-neon-300 underline">
                  מה עוד קורה ב{city.name_he}
                </Link>
                .
              </>
            ) : null}
          </p>
        )}
      </section>

      <div className="mt-8">
        <Breadcrumbs crumbs={crumbs} />
      </div>
    </main>
  );
}
