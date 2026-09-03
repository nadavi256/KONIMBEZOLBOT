import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { JsonLd } from "@/components/JsonLd";
import { ListPage } from "@/components/ListPage";
import { answerSentence, buildFaq } from "@/lib/answer";
import { cityLinkGroups } from "@/lib/cityLinks";
import { hebrewDate, weekendDates, weekendWindow } from "@/lib/dates";
import { getCityBySlug, getEventsInWindow } from "@/lib/queries";
import { breadcrumbJsonLd, faqJsonLd, itemListJsonLd, type Crumb } from "@/lib/seo";
import { clamp, ogImageUrl, SITE_NAME } from "@/lib/site";

export const revalidate = 3600;
export const dynamicParams = true;

type Props = { params: Promise<{ city: string }> };

async function loadData(citySlug: string) {
  const city = await getCityBySlug(citySlug);
  if (!city) return null;
  const { from, to } = weekendWindow();
  const events = await getEventsInWindow(from, to, { cityId: city.id });
  const { thursday, saturday } = weekendDates();
  const h1 = `מסיבות בסופ"ש ב${city.name_he}, ${hebrewDate(thursday)} עד ${hebrewDate(saturday)}`;
  const scope = `בסופ"ש ב${city.name_he}`;
  return { city, events, h1, scope };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city: citySlug } = await params;
  const data = await loadData(citySlug);
  if (!data) return {};
  const { city, events, h1, scope } = data;
  const canonical = `/${city.slug}/weekend`;
  const description = clamp(answerSentence(events, scope), 155);
  return {
    title: { absolute: clamp(`סופ"ש ב${city.name_he}: מסיבות ואירועים | ${SITE_NAME}`, 60) },
    description,
    alternates: { canonical, languages: { "he-IL": canonical } },
    openGraph: { title: `סופ"ש ב${city.name_he}`, description, images: [ogImageUrl(h1)] },
    robots: events.length > 0 ? { index: true, follow: true } : { index: false, follow: true },
  };
}

export default async function WeekendPage({ params }: Props) {
  const { city: citySlug } = await params;
  const data = await loadData(citySlug);
  if (!data) notFound();
  const { city, events, h1, scope } = data;
  const faqs = buildFaq(events, scope);
  const linkGroups = await cityLinkGroups(city, { exclude: `/${city.slug}/weekend` });
  const crumbs: Crumb[] = [
    { name: "ראשי", href: "/" },
    { name: city.name_he, href: `/${city.slug}` },
    { name: `סופ"ש ב${city.name_he}`, href: `/${city.slug}/weekend` },
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
          <p className="rounded-2xl bg-white p-5 text-zinc-700">
            אין עדיין אירועים מפורסמים לסופ&quot;ש הזה ב{city.name_he}. בדקו{" "}
            <Link href={`/${city.slug}/tonight`} className="text-violet-700 underline">
              מה קורה הערב
            </Link>{" "}
            או חזרו בהמשך השבוע.
          </p>
        }
      />
    </>
  );
}
