import { notFound } from "next/navigation";
import { EventForm } from "@/components/admin/EventForm";
import { supabaseServer } from "@/lib/supabase/server";
import type { City, EventRow, Genre, Organizer, Venue } from "@/lib/types";

export const dynamic = "force-dynamic";

const TZ = "Asia/Jerusalem";

function israelDatePart(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date(iso));
}

function israelTimePart(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

export default async function EditEventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const sb = await supabaseServer();
  const [{ data: event }, { data: cities }, { data: venues }, { data: genres }, { data: organizers }, { data: eventGenres }] =
    await Promise.all([
      sb.from("events").select("*").eq("id", id).maybeSingle(),
      sb.from("cities").select("*").eq("is_active", true).order("name_he"),
      sb.from("venues").select("*").eq("is_active", true).order("name_he"),
      sb.from("genres").select("*").order("slug"),
      sb.from("organizers").select("*").order("name_he"),
      sb.from("event_genres").select("genre_id").eq("event_id", id),
    ]);
  if (!event) notFound();
  const row = event as EventRow;

  return (
    <main>
      <h1 className="mb-5 text-2xl font-extrabold">עריכת אירוע: {row.title_he}</h1>
      <EventForm
        cities={(cities ?? []) as City[]}
        venues={(venues ?? []) as Venue[]}
        genres={(genres ?? []) as Genre[]}
        organizers={(organizers ?? []) as Organizer[]}
        event={{ ...row, genre_ids: (eventGenres ?? []).map((g) => g.genre_id) }}
        initialDate={israelDatePart(row.starts_at)}
        initialTime={israelTimePart(row.starts_at)}
        initialEndsTime={row.ends_at ? israelTimePart(row.ends_at) : undefined}
        initialDoorsTime={row.doors_at ? israelTimePart(row.doors_at) : undefined}
      />
    </main>
  );
}
