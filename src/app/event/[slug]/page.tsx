import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { JsonLd } from "@/components/JsonLd";
import { eventNightDate, hebrewDate, israelTime, updatedAgoHe } from "@/lib/dates";
import { ageLabel, priceLabel } from "@/lib/format";
import { getEventBySlug, getUpcomingEventsForVenue } from "@/lib/queries";
import { EventCard } from "@/components/EventCard";
import { breadcrumbJsonLd, eventJsonLd, type Crumb } from "@/lib/seo";
import { clamp, ogImageUrl, SITE_NAME } from "@/lib/site";

export const revalidate = 3600;
export const dynamicParams = true;

type Props = { params: Promise<{ slug: string }> };

const PAST_NOINDEX_DAYS = 30;

function isNoindexPast(startsAt: string): boolean {
  return Date.now() - new Date(startsAt).getTime() > PAST_NOINDEX_DAYS * 86_400_000;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const event = await getEventBySlug(slug);
  if (!event || event.status === "draft") return {};
  const canonical = `/event/${event.slug}`;
  const dateHe = hebrewDate(eventNightDate(event.starts_at));
  const price = priceLabel(event);
  const description = clamp(
    `${event.title_he} ב${event.venue.name_he}, ${dateHe} מ-${israelTime(event.starts_at)}${price ? `, ${price}` : ""}. כל הפרטים והכרטיסים.`,
    155,
  );
  return {
    title: { absolute: clamp(`${event.title_he} | ${SITE_NAME}`, 60) },
    description,
    alternates: { canonical, languages: { "he-IL": canonical } },
    openGraph: {
      title: event.title_he,
      description,
      images: [event.image_url ?? ogImageUrl(event.title_he, `${event.venue.name_he} · ${dateHe}`)],
    },
    // Past events stay up (with internal links) but drop out of the index after 30 days.
    robots: isNoindexPast(event.starts_at)
      ? { index: false, follow: true }
      : { index: true, follow: true },
  };
}

export default async function EventPage({ params }: Props) {
  const { slug } = await params;
  const event = await getEventBySlug(slug);
  if (!event || event.status === "draft") notFound();

  const nightDate = eventNightDate(event.starts_at);
  const price = priceLabel(event);
  const age = ageLabel(event.min_age);
  const updated = updatedAgoHe([event.updated_at]);
  const moreAtVenue = (await getUpcomingEventsForVenue(event.venue_id, 4)).filter(
    (e) => e.id !== event.id,
  );
  const crumbs: Crumb[] = [
    { name: "ראשי", href: "/" },
    { name: event.city.name_he, href: `/${event.city.slug}` },
    { name: event.venue.name_he, href: `/venue/${event.venue.slug}` },
    { name: event.title_he, href: `/event/${event.slug}` },
  ];

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <JsonLd data={[eventJsonLd(event), breadcrumbJsonLd(crumbs)]} />
      {event.image_url ? (
        <div className="relative mb-5 h-56 w-full overflow-hidden rounded-2xl sm:h-72">
          <Image src={event.image_url} alt={event.title_he} fill sizes="(max-width: 768px) 100vw, 768px" className="object-cover" priority />
        </div>
      ) : null}

      {event.status === "cancelled" ? (
        <p className="mb-4 rounded-xl bg-red-100 p-3 font-semibold text-red-800">האירוע בוטל</p>
      ) : null}

      <h1 className="text-2xl font-extrabold leading-tight sm:text-3xl">{event.title_he}</h1>
      <p className="mt-2 text-lg text-zinc-700">
        {hebrewDate(nightDate)}, מ-{israelTime(event.starts_at)} ב
        <Link href={`/venue/${event.venue.slug}`} className="font-semibold hover:underline">
          {event.venue.name_he}
        </Link>
        , {event.city.name_he}
        {price ? ` · ${price}` : ""}
        {age ? ` · ${age}` : ""}
      </p>
      {updated ? <p className="mt-1 text-sm text-zinc-400">{updated}</p> : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {event.genres.map((g) => (
          <Link key={g.id} href={`/${event.city.slug}/${g.slug}`} className="rounded-full bg-violet-100 px-3 py-1 text-sm text-violet-800 hover:bg-violet-200">
            {g.name_he}
          </Link>
        ))}
        {event.is_sold_out ? (
          <span className="rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700">אזל</span>
        ) : null}
      </div>

      {event.ticket_url && !event.is_sold_out && event.status !== "cancelled" ? (
        <a
          href={event.ticket_url}
          rel="nofollow noopener"
          target="_blank"
          className="mt-5 inline-block rounded-xl bg-violet-600 px-6 py-3 font-semibold text-white hover:bg-violet-700"
        >
          לכרטיסים
        </a>
      ) : null}

      <dl className="mt-6 grid gap-3 rounded-2xl bg-white p-5 sm:grid-cols-2">
        <div>
          <dt className="text-sm text-zinc-500">תאריך</dt>
          <dd className="font-medium">{hebrewDate(nightDate)}</dd>
        </div>
        <div>
          <dt className="text-sm text-zinc-500">שעת התחלה</dt>
          <dd className="font-medium">{israelTime(event.starts_at)}</dd>
        </div>
        {event.doors_at ? (
          <div>
            <dt className="text-sm text-zinc-500">פתיחת דלתות</dt>
            <dd className="font-medium">{israelTime(event.doors_at)}</dd>
          </div>
        ) : null}
        {event.ends_at ? (
          <div>
            <dt className="text-sm text-zinc-500">שעת סיום</dt>
            <dd className="font-medium">{israelTime(event.ends_at)}</dd>
          </div>
        ) : null}
        <div>
          <dt className="text-sm text-zinc-500">מחיר</dt>
          <dd className="font-medium">{price ?? "לא פורסם"}</dd>
        </div>
        {age ? (
          <div>
            <dt className="text-sm text-zinc-500">גיל מינימום</dt>
            <dd className="font-medium">{age}</dd>
          </div>
        ) : null}
        {event.venue.address ? (
          <div className="sm:col-span-2">
            <dt className="text-sm text-zinc-500">כתובת</dt>
            <dd className="font-medium">
              {event.venue.name_he}, {event.venue.address}
            </dd>
          </div>
        ) : null}
        {event.organizer ? (
          <div>
            <dt className="text-sm text-zinc-500">מפיק</dt>
            <dd className="font-medium">
              <Link href={`/organizer/${event.organizer.slug}`} className="hover:underline">
                {event.organizer.name_he}
              </Link>
            </dd>
          </div>
        ) : null}
      </dl>

      {event.description_he ? (
        <section className="mt-6">
          <h2 className="text-xl font-bold">על האירוע</h2>
          <p className="mt-2 whitespace-pre-line text-zinc-700">{event.description_he}</p>
        </section>
      ) : null}

      {moreAtVenue.length > 0 ? (
        <section className="mt-8">
          <h2 className="text-xl font-bold">עוד ב{event.venue.name_he}</h2>
          <div className="mt-3 space-y-4">
            {moreAtVenue.map((e) => (
              <EventCard key={e.id} event={e} showDate />
            ))}
          </div>
        </section>
      ) : null}

      <div className="mt-8">
        <Breadcrumbs crumbs={crumbs} />
      </div>
    </main>
  );
}
