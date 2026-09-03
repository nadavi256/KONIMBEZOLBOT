import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { EventCard, EventGrid } from "@/components/EventCard";
import { JsonLd } from "@/components/JsonLd";
import { updatedAgoHe } from "@/lib/dates";
import { getOrganizerBySlug, getUpcomingEventsForOrganizer } from "@/lib/queries";
import { breadcrumbJsonLd, itemListJsonLd, type Crumb } from "@/lib/seo";
import { clamp, ogImageUrl, SITE_NAME } from "@/lib/site";

export const revalidate = 3600;
export const dynamicParams = true;

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const organizer = await getOrganizerBySlug(slug);
  if (!organizer) return {};
  const events = await getUpcomingEventsForOrganizer(organizer.id);
  const canonical = `/organizer/${organizer.slug}`;
  const description = clamp(
    `כל האירועים הקרובים של ${organizer.name_he}: תאריכים, מקומות, מחירים וכרטיסים.`,
    155,
  );
  return {
    title: { absolute: clamp(`${organizer.name_he}: אירועים קרובים | ${SITE_NAME}`, 60) },
    description,
    alternates: { canonical, languages: { "he-IL": canonical } },
    openGraph: { title: organizer.name_he, description, images: [ogImageUrl(organizer.name_he)] },
    robots: events.length > 0 ? { index: true, follow: true } : { index: false, follow: true },
  };
}

export default async function OrganizerPage({ params }: Props) {
  const { slug } = await params;
  const organizer = await getOrganizerBySlug(slug);
  if (!organizer) notFound();
  const events = await getUpcomingEventsForOrganizer(organizer.id);
  const updated = updatedAgoHe(events.map((e) => e.updated_at));
  const crumbs: Crumb[] = [
    { name: "ראשי", href: "/" },
    { name: organizer.name_he, href: `/organizer/${organizer.slug}` },
  ];

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <JsonLd data={[itemListJsonLd(events), breadcrumbJsonLd(crumbs)]} />
      <h1 className="text-3xl font-black leading-tight sm:text-4xl">
        האירועים של {organizer.name_he}
      </h1>
      <div className="mt-2 flex gap-3 text-sm">
        {organizer.instagram ? (
          <a href={organizer.instagram} rel="nofollow noopener" target="_blank" className="text-neon-300 underline">אינסטגרם</a>
        ) : null}
        {organizer.website ? (
          <a href={organizer.website} rel="nofollow noopener" target="_blank" className="text-neon-300 underline">אתר</a>
        ) : null}
      </div>
      {updated ? <p className="mt-1 text-sm text-zinc-500">{updated}</p> : null}

      {events.length > 0 ? (
        <EventGrid>
          {events.map((e) => (
            <EventCard key={e.id} event={e} showDate />
          ))}
        </EventGrid>
      ) : (
        <p className="mt-6 surface p-4 text-zinc-500">אין כרגע אירועים מפורסמים.</p>
      )}

      <div className="mt-8">
        <Breadcrumbs crumbs={crumbs} />
      </div>
    </main>
  );
}
