import { getActiveCities } from "@/lib/queries";
import { absoluteUrl, SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";

export const revalidate = 3600;

export async function GET() {
  const cities = await getActiveCities();
  const cityLines = cities
    .map(
      (c) =>
        `- [${c.name_he} (${c.name_en})](${absoluteUrl(`/${c.slug}`)}): tonight, tomorrow, weekend, by-genre and by-date event listings for ${c.name_en}`,
    )
    .join("\n");

  const body = `# ${SITE_NAME}

> ${SITE_DESCRIPTION}
> Hebrew-language nightlife guide for Israel. Every list page opens with a one-sentence,
> data-driven answer (event count, biggest party, genre, start time, price range),
> followed by full event cards and a data-generated FAQ. Times are Israel time (Asia/Jerusalem).

## City hubs

${cityLines || "- City hubs are published as data becomes available."}

## Key page patterns

- ${absoluteUrl("/")} — tonight across all cities
- ${absoluteUrl("/{city}/tonight")} — tonight in a city
- ${absoluteUrl("/{city}/{yyyy-mm-dd}")} — a specific date (next 60 days)
- ${absoluteUrl("/{city}/{genre}")} — a genre in a city (next 14 days)
- ${absoluteUrl("/event/{slug}")} — a single event with schema.org/Event JSON-LD
- ${absoluteUrl("/sitemap.xml")} — full index of currently indexable pages
`;

  return new Response(body, {
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}
