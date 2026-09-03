import Image from "next/image";
import Link from "next/link";
import { eventNightDate, hebrewDate, israelTime } from "@/lib/dates";
import { ageLabel, priceLabel } from "@/lib/format";
import type { EventFull } from "@/lib/types";

export function EventCard({ event, showDate = false }: { event: EventFull; showDate?: boolean }) {
  const price = priceLabel(event);
  const age = ageLabel(event.min_age);
  return (
    <article className="flex gap-4 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      {event.image_url ? (
        <div className="relative hidden h-28 w-28 shrink-0 overflow-hidden rounded-xl sm:block">
          <Image src={event.image_url} alt={event.title_he} fill sizes="112px" className="object-cover" />
        </div>
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 text-sm text-zinc-500">
          <time dateTime={event.starts_at} className="font-semibold text-zinc-900">
            {israelTime(event.starts_at)}
          </time>
          {showDate ? <span>{hebrewDate(eventNightDate(event.starts_at))}</span> : null}
          <Link href={`/venue/${event.venue.slug}`} className="hover:underline">
            {event.venue.name_he}
          </Link>
        </div>
        <h3 className="mt-1 text-lg font-bold leading-snug">
          <Link href={`/event/${event.slug}`} className="hover:underline">
            {event.title_he}
          </Link>
        </h3>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          {event.genres.map((g) => (
            <span key={g.id} className="rounded-full bg-violet-100 px-2.5 py-0.5 text-violet-800">
              {g.name_he}
            </span>
          ))}
          {price ? <span className="font-medium text-zinc-700">{price}</span> : null}
          {age ? <span className="text-zinc-500">{age}</span> : null}
          {event.is_sold_out ? (
            <span className="rounded-full bg-red-100 px-2.5 py-0.5 font-medium text-red-700">אזל</span>
          ) : null}
        </div>
      </div>
      {event.ticket_url && !event.is_sold_out ? (
        <div className="flex items-center">
          <a
            href={event.ticket_url}
            rel="nofollow noopener"
            target="_blank"
            className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700"
          >
            לכרטיסים
          </a>
        </div>
      ) : null}
    </article>
  );
}
