import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EventCard } from "@/components/EventCard";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { JsonLd } from "@/components/JsonLd";
import { answerSentence, buildFaq } from "@/lib/answer";
import { FaqSection } from "@/components/FaqSection";
import { dayWindow, todayInIsrael, updatedAgoHe, weekendWindow } from "@/lib/dates";
import {
  getCityBySlug,
  getEventsInWindow,
  getGenres,
  getVenuesForCity,
} from "@/lib/queries";
import { breadcrumbJsonLd, faqJsonLd, itemListJsonLd, type Crumb } from "@/lib/seo";
import { clamp, ogImageUrl, SITE_NAME } from "@/lib/site";

export const revalidate = 3600;
export const dynamicParams = true;

type Props = { params: Promise<{ city: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city: citySlug } = await params;
  const city = await getCityBySlug(citySlug);
  if (!city) return {};
  const { from, to } = weekendWindow();
  const events = await getEventsInWindow(from, to, { cityId: city.id });
  const canonical = `/${city.slug}`;
  const description = clamp(
    `מסיבות ואירועים ב${city.name_he}: הערב, מחר ובסופ"ש — שעות, מחירים וכרטיסים. מעודכן יומית.`,
    155,
  );
  return {
    title: { absolute: clamp(`אירועים ומסיבות ב${city.name_he} | ${SITE_NAME}`, 60) },
    description,
    alternates: { canonical, languages: { "he-IL": canonical } },
    openGraph: {
      title: `אירועים ומסיבות ב${city.name_he}`,
      description,
      images: [ogImageUrl(`מסיבות ואירועים ב${city.name_he}`)],
    },
    robots: events.length > 0 ? { index: true, follow: true } : { index: false, follow: true },
  };
}

export default async function CityHubPage({ params }: Props) {
  const { city: citySlug } = await params;
  const city = await getCityBySlug(citySlug);
  if (!city) notFound();

  const today = todayInIsrael();
  const tonightWin = dayWindow(today);
  const weekendWin = weekendWindow();
  const [tonight, weekend, genres, venues] = await Promise.all([
    getEventsInWindow(tonightWin.from, tonightWin.to, { cityId: city.id }),
    getEventsInWindow(weekendWin.from, weekendWin.to, { cityId: city.id }),
    getGenres(),
    getVenuesForCity(city.id),
  ]);

  const scope = `השבוע ב${city.name_he}`;
  const all = [...new Map([...tonight, ...weekend].map((e) => [e.id, e])).values()];
  const faqs = buildFaq(all, scope);
  const updated = updatedAgoHe(all.map((e) => e.updated_at));
  const crumbs: Crumb[] = [
    { name: "ראשי", href: "/" },
    { name: city.name_he, href: `/${city.slug}` },
  ];

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <JsonLd
        data={[
          itemListJsonLd(all),
          ...(faqs.length ? [faqJsonLd(faqs)] : []),
          breadcrumbJsonLd(crumbs),
        ]}
      />
      <h1 className="text-2xl font-extrabold leading-tight sm:text-3xl">
        מסיבות ואירועים ב{city.name_he}
      </h1>
      <p className="mt-3 text-lg text-zinc-700">{answerSentence(all, scope)}</p>
      {updated ? <p className="mt-1 text-sm text-zinc-400">{updated}</p> : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <Link href={`/${city.slug}/tonight`} className="rounded-full bg-violet-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-violet-700">הערב</Link>
        <Link href={`/${city.slug}/tomorrow`} className="rounded-full border border-violet-300 bg-white px-4 py-1.5 text-sm font-medium text-violet-700 hover:bg-violet-50">מחר</Link>
        <Link href={`/${city.slug}/weekend`} className="rounded-full border border-violet-300 bg-white px-4 py-1.5 text-sm font-medium text-violet-700 hover:bg-violet-50">סופ&quot;ש</Link>
      </div>

      <section className="mt-8">
        <h2 className="text-xl font-bold">
          <Link href={`/${city.slug}/tonight`} className="hover:underline">הערב ב{city.name_he}</Link>
        </h2>
        {tonight.length > 0 ? (
          <div className="mt-3 space-y-4">
            {tonight.map((e) => <EventCard key={e.id} event={e} />)}
          </div>
        ) : (
          <p className="mt-3 text-zinc-600">אין אירועים מפורסמים להערב.</p>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-bold">
          <Link href={`/${city.slug}/weekend`} className="hover:underline">בסופ&quot;ש ב{city.name_he}</Link>
        </h2>
        {weekend.length > 0 ? (
          <div className="mt-3 space-y-4">
            {weekend.map((e) => <EventCard key={e.id} event={e} showDate />)}
          </div>
        ) : (
          <p className="mt-3 text-zinc-600">אין עדיין אירועים מפורסמים לסופ&quot;ש.</p>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-bold">לפי ז&apos;אנר</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {genres.map((g) => (
            <Link key={g.id} href={`/${city.slug}/${g.slug}`} className="rounded-full bg-zinc-200 px-3 py-1 text-sm hover:bg-zinc-300">
              {g.name_he}
            </Link>
          ))}
        </div>
      </section>

      {venues.length > 0 ? (
        <section className="mt-8">
          <h2 className="text-xl font-bold">מקומות ב{city.name_he}</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {venues.map((v) => (
              <li key={v.id}>
                <Link href={`/venue/${v.slug}`} className="block rounded-xl border border-zinc-200 bg-white p-3 hover:border-violet-300">
                  <span className="font-semibold">{v.name_he}</span>
                  {v.address ? <span className="block text-sm text-zinc-500">{v.address}</span> : null}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <FaqSection faqs={faqs} />
      <div className="mt-8">
        <Breadcrumbs crumbs={crumbs} />
      </div>
    </main>
  );
}
