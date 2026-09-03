import { EventForm } from "@/components/admin/EventForm";
import { supabaseServer } from "@/lib/supabase/server";
import type { City, Genre, Organizer, Venue } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function NewEventPage() {
  const sb = await supabaseServer();
  const [{ data: cities }, { data: venues }, { data: genres }, { data: organizers }] =
    await Promise.all([
      sb.from("cities").select("*").eq("is_active", true).order("name_he"),
      sb.from("venues").select("*").eq("is_active", true).order("name_he"),
      sb.from("genres").select("*").order("slug"),
      sb.from("organizers").select("*").order("name_he"),
    ]);

  return (
    <main>
      <h1 className="mb-5 text-2xl font-extrabold">אירוע חדש</h1>
      <EventForm
        cities={(cities ?? []) as City[]}
        venues={(venues ?? []) as Venue[]}
        genres={(genres ?? []) as Genre[]}
        organizers={(organizers ?? []) as Organizer[]}
      />
    </main>
  );
}
