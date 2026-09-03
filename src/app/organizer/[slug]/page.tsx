import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { EventCard } from "@/components/EventCard";
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
    <main className="mx-auto max-w-3xl px-4 py-8">
      <JsonLd data={[itemListJsonLd(events), breadcrumbJsonLd(crumbs)]} />
      <h1 className="text-2xl font-extrabold leading-tight sm:text-3xl">
        האירועים של {organizer.name_he}
      </h1>
      <div className="mt-2 flex gap-3 text-sm">
        {organizer.instagram ? (
          <a href={organizer.instagram} rel="nofollow noopener" target="_blank" className="text-violet-700 underline">אינסטגרם</a>
        ) : null}
        {organizer.website ? (
          <a href={organizer.website} rel="nofollow noopener" target="_blank" className="text-violet-700 underline">אתר</a>
        ) : null}
      </div>
      {updated ? <p className="mt-1 text-sm text-zinc-400">{updated}</p> : null}

      {events.length > 0 ? (
        <div className="mt-6 space-y-4">
          {events.map((e) => (
            <EventCard key={e.id} event={e} showDate />
          ))}
        </div>
      ) : (
        <p className="mt-6 rounded-xl bg-white p-4 text-zinc-600">אין כרגע אירועים מפורסמים.</p>
      )}

      <div className="mt-8">
        <Breadcrumbs crumbs={crumbs} />
      </div>
    </main>
  );
}
