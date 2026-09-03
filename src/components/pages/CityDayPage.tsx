import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EventCard } from "@/components/EventCard";
import { JsonLd } from "@/components/JsonLd";
import { ListPage } from "@/components/ListPage";
import { answerSentence, buildFaq } from "@/lib/answer";
import { cityLinkGroups } from "@/lib/cityLinks";
import { addDays, dayWindow, hebrewDate, todayInIsrael, weekendWindow } from "@/lib/dates";
import { getCityBySlug, getEventsInWindow } from "@/lib/queries";
import { breadcrumbJsonLd, faqJsonLd, itemListJsonLd, type Crumb } from "@/lib/seo";
import { clamp, ogImageUrl, SITE_NAME } from "@/lib/site";

export type DayMode = "tonight" | "tomorrow" | "date";

function phrasing(mode: DayMode, cityName: string, dateStr: string) {
  const dateHe = hebrewDate(dateStr);
  switch (mode) {
    case "tonight":
      return {
        h1: `מסיבות ב${cityName} הערב, ${dateHe}`,
        scope: `הערב ב${cityName}`,
        title: `הערב ב${cityName}: מסיבות ואירועים`,
        path: `/tonight`,
      };
    case "tomorrow":
      return {
        h1: `מסיבות ב${cityName} מחר, ${dateHe}`,
        scope: `מחר ב${cityName}`,
        title: `מחר ב${cityName}: מסיבות ואירועים`,
        path: `/tomorrow`,
      };
    default:
      return {
        h1: `מסיבות ואירועים ב${cityName} — ${dateHe}`,
        scope: `ב${dateHe} ב${cityName}`,
        title: `${cityName} ${dateStr}: מסיבות ואירועים`,
        path: `/${dateStr}`,
      };
  }
}

function resolveDate(mode: DayMode, dateStr?: string): string {
  if (mode === "tonight") return todayInIsrael();
  if (mode === "tomorrow") return addDays(todayInIsrael(), 1);
  return dateStr!;
}

export async function cityDayMetadata(
  citySlug: string,
  mode: DayMode,
  dateParam?: string,
): Promise<Metadata> {
  const city = await getCityBySlug(citySlug);
  if (!city) return {};
  const dateStr = resolveDate(mode, dateParam);
  const { from, to } = dayWindow(dateStr);
  const events = await getEventsInWindow(from, to, { cityId: city.id });
  const p = phrasing(mode, city.name_he, dateStr);
  const canonical = `/${city.slug}${p.path}`;
  const description = clamp(answerSentence(events, p.scope), 155);
  return {
    title: { absolute: clamp(`${p.title} | ${SITE_NAME}`, 60) },
    description,
    alternates: { canonical, languages: { "he-IL": canonical } },
    openGraph: { title: p.title, description, images: [ogImageUrl(p.h1)] },
    // Indexing rule: a list page is indexable only with ≥1 published event.
    robots: events.length > 0 ? { index: true, follow: true } : { index: false, follow: true },
  };
}

export async function CityDayPage({
  citySlug,
  mode,
  dateParam,
}: {
  citySlug: string;
  mode: DayMode;
  dateParam?: string;
}) {
  const city = await getCityBySlug(citySlug);
  if (!city) notFound();
  const dateStr = resolveDate(mode, dateParam);
  const { from, to } = dayWindow(dateStr);
  const events = await getEventsInWindow(from, to, { cityId: city.id });
  const p = phrasing(mode, city.name_he, dateStr);

  const weekendFallback =
    events.length === 0
      ? await getEventsInWindow(weekendWindow().from, weekendWindow().to, {
          cityId: city.id,
          limit: 6,
        })
      : [];

  const faqs = buildFaq(events, p.scope);
  const linkGroups = await cityLinkGroups(city, { exclude: `/${city.slug}${p.path}` });
  const crumbs: Crumb[] = [
    { name: "ראשי", href: "/" },
    { name: city.name_he, href: `/${city.slug}` },
    { name: p.h1, href: `/${city.slug}${p.path}` },
  ];

  return (
    <>
      <JsonLd
        data={[
          itemListJsonLd(events),
          ...(faqs.length ? [faqJsonLd(faqs)] : []),
          breadcrumbJsonLd(crumbs),
        ]}
      />
      <ListPage
        h1={p.h1}
        answer={answerSentence(events, p.scope)}
        events={events}
        faqs={faqs}
        linkGroups={linkGroups}
        crumbs={crumbs}
        fallback={
          <div className="rounded-2xl bg-white p-5">
            <p className="text-zinc-700">
              אין אירועים מפורסמים {p.scope}.{" "}
              {weekendFallback.length > 0 ? "הנה מה שיש בסופ״ש:" : (
                <>
                  בדקו את{" "}
                  <Link href={`/${city.slug}/weekend`} className="text-violet-700 underline">
                    עמוד הסופ״ש של {city.name_he}
                  </Link>
                  .
                </>
              )}
            </p>
            {weekendFallback.length > 0 ? (
              <div className="mt-4 space-y-4">
                {weekendFallback.map((e) => (
                  <EventCard key={e.id} event={e} showDate />
                ))}
              </div>
            ) : null}
          </div>
        }
      />
    </>
  );
}
