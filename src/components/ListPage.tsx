import { updatedAgoHe } from "@/lib/dates";
import type { Faq } from "@/lib/answer";
import type { Crumb } from "@/lib/seo";
import type { EventFull } from "@/lib/types";
import { Breadcrumbs } from "./Breadcrumbs";
import { EventCard } from "./EventCard";
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
    <main className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-extrabold leading-tight sm:text-3xl">{h1}</h1>
      <p className="mt-3 text-lg text-zinc-700">{answer}</p>
      {updated ? <p className="mt-1 text-sm text-zinc-400">{updated}</p> : null}

      {events.length > 0 ? (
        <div className="mt-6 space-y-4">
          {events.map((e) => (
            <EventCard key={e.id} event={e} showDate={showDates} />
          ))}
        </div>
      ) : (
        <div className="mt-6">{fallback}</div>
      )}

      <FaqSection faqs={faqs} />
      <InternalLinks groups={linkGroups} />
      <div className="mt-8">
        <Breadcrumbs crumbs={crumbs} />
      </div>
    </main>
  );
}
