import { updatedAgoHe } from "@/lib/dates";
import type { Faq } from "@/lib/answer";
import type { Crumb } from "@/lib/seo";
import type { EventFull } from "@/lib/types";
import { Breadcrumbs } from "./Breadcrumbs";
import { EventCard, EventGrid } from "./EventCard";
import { FaqSection } from "./FaqSection";
import { InternalLinks, type LinkGroup } from "./InternalLinks";

/**
 * The canonical list-page template (CLAUDE.md §Page template):
 * H1 → direct answer → freshness → cards → FAQ → internal links → breadcrumbs.
 */
export function ListPage({
  h1,
  answer,
  events,
  faqs,
  linkGroups,
  crumbs,
  fallback,
  showDates = false,
}: {
  h1: string;
  answer: string;
  events: EventFull[];
  faqs: Faq[];
  linkGroups: LinkGroup[];
  crumbs: Crumb[];
  /** Rendered when there are no events: useful alternative content. */
  fallback?: React.ReactNode;
  showDates?: boolean;
}) {
  const updated = updatedAgoHe(events.map((e) => e.updated_at));
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="max-w-3xl text-3xl font-black leading-tight sm:text-4xl">{h1}</h1>
      <p className="mt-3 max-w-3xl text-lg text-zinc-300">{answer}</p>
      {updated ? <p className="mt-1 text-sm text-zinc-500">{updated}</p> : null}

      {events.length > 0 ? (
        <div className="mt-7">
          <EventGrid>
            {events.map((e) => (
              <EventCard key={e.id} event={e} showDate={showDates} />
            ))}
          </EventGrid>
        </div>
      ) : (
        <div className="mt-7">{fallback}</div>
      )}

      <FaqSection faqs={faqs} />
      <InternalLinks groups={linkGroups} />
      <div className="mt-8">
        <Breadcrumbs crumbs={crumbs} />
      </div>
    </main>
  );
}
