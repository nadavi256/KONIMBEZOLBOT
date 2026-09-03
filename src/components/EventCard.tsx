import Image from "next/image";
import Link from "next/link";
import { eventNightDate, hebrewDate, israelTime } from "@/lib/dates";
import { ageLabel, priceLabel } from "@/lib/format";
import type { EventFull } from "@/lib/types";

/** Poster-style gradients used when an event has no image (varies per event). */
const POSTER_GRADIENTS = [
  "linear-gradient(135deg, #ff2d84 0%, #7c3aed 100%)",
  "linear-gradient(135deg, #7c3aed 0%, #2563eb 100%)",
  "linear-gradient(135deg, #e11d74 0%, #f59e0b 90%)",
  "linear-gradient(135deg, #06b6d4 0%, #8b5cf6 100%)",
  "linear-gradient(135deg, #a21caf 0%, #ff2d84 100%)",
  "linear-gradient(135deg, #4f46e5 0%, #ec4899 100%)",
];

function posterGradient(slug: string): string {
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
  return POSTER_GRADIENTS[h % POSTER_GRADIENTS.length];
}

export function EventCard({ event, showDate = false }: { event: EventFull; showDate?: boolean }) {
  const price = priceLabel(event);
  const age = ageLabel(event.min_age);
  const dateBadge = showDate ? hebrewDate(eventNightDate(event.starts_at)) : null;

  return (
    <article className="surface group flex flex-col overflow-hidden transition hover:border-neon-500/40 hover:shadow-[0_0_36px_rgba(255,45,132,0.18)]">
      {/* poster */}
      <Link href={`/event/${event.slug}`} className="relative block aspect-[16/9] overflow-hidden">
        {event.image_url ? (
          <Image
            src={event.image_url}
            alt={event.title_he}
            fill
            sizes="(max-width: 640px) 100vw, 480px"
            className="object-cover transition duration-300 group-hover:scale-105"
          />
        ) : (
          <div
            className="flex h-full w-full items-end p-4"
            style={{ backgroundImage: posterGradient(event.slug) }}
          >
            <span className="text-5xl font-black text-white/25">
              {event.genres[0]?.name_he ?? "לילה"}
            </span>
          </div>
        )}
        <div className="absolute inset-x-0 top-0 flex items-start justify-between p-3">
          <span className="rounded-lg bg-black/60 px-2.5 py-1 text-sm font-bold text-white backdrop-blur-sm">
            {israelTime(event.starts_at)}
          </span>
          {dateBadge ? (
            <span className="rounded-lg bg-black/60 px-2.5 py-1 text-xs font-medium text-zinc-200 backdrop-blur-sm">
              {dateBadge}
            </span>
          ) : null}
        </div>
        {event.is_sold_out ? (
          <span className="absolute bottom-3 start-3 rounded-lg bg-red-600 px-2.5 py-1 text-xs font-bold text-white">
            אזלו הכרטיסים
          </span>
        ) : null}
      </Link>

      {/* details */}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="text-lg font-black leading-snug">
          <Link href={`/event/${event.slug}`} className="hover:text-neon-300">
            {event.title_he}
          </Link>
        </h3>
        <p className="text-sm text-zinc-400">
          <Link href={`/venue/${event.venue.slug}`} className="font-medium text-zinc-300 hover:text-neon-300">
            {event.venue.name_he}
          </Link>
          {" · "}
          {event.city.name_he}
        </p>
        <div className="flex flex-wrap items-center gap-1.5">
          {event.genres.map((g) => (
            <span
              key={g.id}
              className="rounded-full border border-glow-500/40 bg-glow-500/10 px-2.5 py-0.5 text-xs font-medium text-glow-300"
            >
              {g.name_he}
            </span>
          ))}
          {age ? <span className="text-xs text-zinc-500">{age}</span> : null}
        </div>
        <div className="mt-auto flex items-center justify-between pt-2">
          <span className={`font-bold ${event.is_free ? "text-emerald-400" : "text-zinc-100"}`}>
            {price ?? ""}
          </span>
          {event.ticket_url && !event.is_sold_out ? (
            <a href={event.ticket_url} rel="nofollow noopener" target="_blank" className="btn-neon">
              לכרטיסים
            </a>
          ) : (
            <Link
              href={`/event/${event.slug}`}
              className="rounded-xl border border-white/15 px-4 py-2 text-sm font-medium text-zinc-300 transition hover:border-neon-500/50 hover:text-white"
            >
              לפרטים
            </Link>
          )}
        </div>
      </div>
    </article>
  );
}

/** Standard responsive grid for event cards. */
export function EventGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>;
}
