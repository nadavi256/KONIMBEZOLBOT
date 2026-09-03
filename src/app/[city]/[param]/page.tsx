import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CityDayPage, cityDayMetadata } from "@/components/pages/CityDayPage";
import { JsonLd } from "@/components/JsonLd";
import { ListPage } from "@/components/ListPage";
import { answerSentence, buildFaq } from "@/lib/answer";
import { cityLinkGroups } from "@/lib/cityLinks";
import { daysFromToday, isValidDateSlug } from "@/lib/dates";
import { getCityBySlug, getEventsInWindow, getGenreBySlug } from "@/lib/queries";
import { breadcrumbJsonLd, faqJsonLd, itemListJsonLd, type Crumb } from "@/lib/seo";
import { clamp, ogImageUrl, SITE_NAME } from "@/lib/site";

export const revalidate = 3600;
export const dynamicParams = true;

type Props = { params: Promise<{ city: string; param: string }> };

/**
 * /[city]/[param] serves two page types:
 *   - a date page (yyyy-mm-dd, today..+60 days only)
 *   - a genre page (next 14 days in this genre)
 */

function isDateInRange(param: string): boolean {
  if (!isValidDateSlug(param)) return false;
  const diff = daysFromToday(param);
  return diff >= 0 && diff <= 60;
}

async function loadGenreData(citySlug: string, genreSlug: string) {
  const [city, genre] = await Promise.all([getCityBySlug(citySlug), getGenreBySlug(genreSlug)]);
  if (!city || !genre) return null;
  const from = new Date();
  const to = new Date(Date.now() + 14 * 86_400_000);
  const events = await getEventsInWindow(from, to, { cityId: city.id, genreId: genre.id });
  const h1 = `מסיבות ${genre.name_he} ב${city.name_he} בשבועיים הקרובים`;
  const scope = `ב${city.name_he} בז'אנר ${genre.name_he}`;
  return { city, genre, events, h1, scope };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city: citySlug, param } = await params;
  if (isDateInRange(param)) return cityDayMetadata(citySlug, "date", param);
  if (isValidDateSlug(param)) return { robots: { index: false, follow: false } };

  const data = await loadGenreData(citySlug, param);
  if (!data) return {};
  const { city, genre, events, h1, scope } = data;
  const canonical = `/${city.slug}/${genre.slug}`;
  const description = clamp(answerSentence(events, scope), 155);
  return {
    title: { absolute: clamp(`${genre.name_he} ב${city.name_he}: מסיבות קרובות | ${SITE_NAME}`, 60) },
    description,
    alternates: { canonical, languages: { "he-IL": canonical } },
    openGraph: { title: h1, description, images: [ogImageUrl(h1)] },
    robots: events.length > 0 ? { index: true, follow: true } : { index: false, follow: true },
  };
}

export default async function CityParamPage({ params }: Props) {
  const { city: citySlug, param } = await params;

  if (isValidDateSlug(param)) {
    if (!isDateInRange(param)) notFound(); // dates only within the next 60 days
    return <CityDayPage citySlug={citySlug} mode="date" dateParam={param} />;
  }

  const data = await loadGenreData(citySlug, param);
  if (!data) notFound();
  const { city, genre, events, h1, scope } = data;
  const faqs = buildFaq(events, scope);
  const linkGroups = await cityLinkGroups(city, { exclude: `/${city.slug}/${genre.slug}` });
  const crumbs: Crumb[] = [
    { name: "ראשי", href: "/" },
    { name: city.name_he, href: `/${city.slug}` },
    { name: genre.name_he, href: `/${city.slug}/${genre.slug}` },
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
        h1={h1}
        answer={answerSentence(events, scope)}
        events={events}
        faqs={faqs}
        linkGroups={linkGroups}
        crumbs={crumbs}
        showDates
        fallback={
          <p className="surface p-5 text-zinc-300">
            אין אירועי {genre.name_he} מפורסמים ב{city.name_he} בשבועיים הקרובים. אולי{" "}
            <Link href={`/${city.slug}/weekend`} className="text-neon-300 underline">
              בסופ&quot;ש
            </Link>{" "}
            יש משהו אחר?
          </p>
        }
      />
    </>
  );
}
