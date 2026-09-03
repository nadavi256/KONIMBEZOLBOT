import type { Metadata } from "next";
import Link from "next/link";
import { EventCard, EventGrid } from "@/components/EventCard";
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
    <main className="mx-auto max-w-5xl px-4 py-10">
      <JsonLd data={[itemListJsonLd(events), ...(faqs.length ? [faqJsonLd(faqs)] : [])]} />

      {/* hero */}
      <section className="relative">
        <h1 className="text-4xl font-black leading-tight sm:text-5xl">
          מה יש <span className="text-neon-gradient">הערב</span>?
          <span className="mt-1 block text-2xl font-bold text-zinc-400 sm:text-3xl">
            {hebrewDate(today)}
          </span>
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-300">{answerSentence(events, "הערב בישראל")}</p>
        {updated ? <p className="mt-1 text-sm text-zinc-500">{updated}</p> : null}

        <div className="mt-6 flex flex-wrap gap-2">
          {cities.map((c) => (
            <Link
              key={c.id}
              href={`/${c.slug}`}
              className="rounded-full border border-white/15 bg-night-800/80 px-5 py-2 text-sm font-bold text-zinc-200 transition hover:border-neon-500/60 hover:text-white hover:shadow-[0_0_20px_rgba(255,45,132,0.25)]"
            >
              {c.name_he}
            </Link>
          ))}
        </div>
      </section>

      {byCity.length > 0 ? (
        byCity.map(({ city, events: cityEvents }) => (
          <section key={city.id} className="mt-12">
            <div className="mb-4 flex items-baseline justify-between">
              <h2 className="text-2xl font-black">
                הערב ב<span className="text-neon-gradient">{city.name_he}</span>
              </h2>
              <Link href={`/${city.slug}/tonight`} className="text-sm font-medium text-glow-300 hover:text-neon-300">
                לכל האירועים ←
              </Link>
            </div>
            <EventGrid>
              {cityEvents.map((e) => (
                <EventCard key={e.id} event={e} />
              ))}
            </EventGrid>
          </section>
        ))
      ) : (
        <p className="surface mt-10 p-6 text-zinc-400">
          אין אירועים מפורסמים להערב. בחרו עיר למעלה כדי לראות מה קורה בסופ&quot;ש.
        </p>
      )}
    </main>
  );
}
