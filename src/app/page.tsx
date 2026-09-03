import type { Metadata } from "next";
import Link from "next/link";
import { EventCard } from "@/components/EventCard";
import { JsonLd } from "@/components/JsonLd";
import { answerSentence, buildFaq } from "@/lib/answer";
import { dayWindow, hebrewDate, todayInIsrael, updatedAgoHe } from "@/lib/dates";
import { getActiveCities, getEventsInWindow } from "@/lib/queries";
import { faqJsonLd, itemListJsonLd } from "@/lib/seo";
import { clamp, ogImageUrl, SITE_NAME } from "@/lib/site";

export const revalidate = 3600;

export async function generateMetadata(): Promise<Metadata> {
  const today = todayInIsrael();
  const title = clamp(`מה יש הערב? מסיבות ואירועים בישראל`, 60);
  const description = clamp(
    `כל המסיבות והאירועים של ${hebrewDate(today)} — לפי עיר, שעה, ז'אנר ומחיר. מעודכן יומית.`,
    155,
  );
  return {
    title: { absolute: `${title} | ${SITE_NAME}` },
    description,
    alternates: { canonical: "/", languages: { "he-IL": "/" } },
    openGraph: { title, description, images: [ogImageUrl(title, hebrewDate(today))] },
  };
}

export default async function HomePage() {
  const today = todayInIsrael();
  const { from, to } = dayWindow(today);
  const [cities, events] = await Promise.all([getActiveCities(), getEventsInWindow(from, to)]);
  const updated = updatedAgoHe(events.map((e) => e.updated_at));
  const faqs = buildFaq(events, "הערב בישראל");

  const byCity = cities
    .map((city) => ({ city, events: events.filter((e) => e.city_id === city.id) }))
    .filter((g) => g.events.length > 0);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <JsonLd data={[itemListJsonLd(events), ...(faqs.length ? [faqJsonLd(faqs)] : [])]} />
      <h1 className="text-2xl font-extrabold leading-tight sm:text-3xl">
        מה יש הערב? {hebrewDate(today)}
      </h1>
      <p className="mt-3 text-lg text-zinc-700">{answerSentence(events, "הערב בישראל")}</p>
      {updated ? <p className="mt-1 text-sm text-zinc-400">{updated}</p> : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {cities.map((c) => (
          <Link
            key={c.id}
            href={`/${c.slug}`}
            className="rounded-full border border-violet-300 bg-white px-4 py-1.5 text-sm font-medium text-violet-700 hover:bg-violet-50"
          >
            {c.name_he}
          </Link>
        ))}
      </div>

      {byCity.length > 0 ? (
        byCity.map(({ city, events: cityEvents }) => (
          <section key={city.id} className="mt-8">
            <h2 className="text-xl font-bold">
              <Link href={`/${city.slug}/tonight`} className="hover:underline">
                הערב ב{city.name_he}
              </Link>
            </h2>
            <div className="mt-3 space-y-4">
              {cityEvents.map((e) => (
                <EventCard key={e.id} event={e} />
              ))}
            </div>
          </section>
        ))
      ) : (
        <p className="mt-8 rounded-xl bg-white p-5 text-zinc-600">
          אין אירועים מפורסמים להערב. בחרו עיר למעלה כדי לראות מה קורה בסופ&quot;ש.
        </p>
      )}
    </main>
  );
}
