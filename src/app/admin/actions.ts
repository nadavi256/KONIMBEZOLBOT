"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { dayWindow, eventNightDate, israelToUtc } from "@/lib/dates";
import { slugify } from "@/lib/format";
import { supabaseServer } from "@/lib/supabase/server";

export type ActionState = {
  error?: string;
  /** Set when an event already exists at the same venue on the same date. */
  duplicateWarning?: string;
  ok?: boolean;
};

/**
 * Every admin save revalidates: home, all pages of the affected city,
 * the venue page, the event page, and the sitemap (CLAUDE.md §Admin).
 */
async function revalidateEvent(citySlug: string | null, venueSlug: string | null, eventSlug: string) {
  revalidatePath("/");
  if (citySlug) revalidatePath(`/${citySlug}`, "layout");
  if (venueSlug) revalidatePath(`/venue/${venueSlug}`);
  revalidatePath(`/event/${eventSlug}`);
  revalidatePath("/sitemap.xml");
  revalidatePath("/llms.txt");
}

async function requireUser() {
  const sb = await supabaseServer();
  const {
    data: { user },
  } = await sb.auth.getUser();
  if (!user) throw new Error("unauthenticated");
  return sb;
}

function num(fd: FormData, name: string): number | null {
  const v = String(fd.get(name) ?? "").trim();
  if (v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function str(fd: FormData, name: string): string | null {
  const v = String(fd.get(name) ?? "").trim();
  return v === "" ? null : v;
}

export async function saveEvent(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const sb = await requireUser();

  const id = str(formData, "id");
  const title = str(formData, "title_he");
  const venueId = str(formData, "venue_id");
  const date = str(formData, "date"); // yyyy-mm-dd, Israel local
  const time = str(formData, "time") ?? "23:00"; // date-only quick add defaults to 23:00
  if (!title || !venueId || !date) {
    return { error: "שם, מקום ותאריך הם שדות חובה" };
  }

  const { data: venue } = await sb
    .from("venues")
    .select("id, slug, city_id, cities(slug)")
    .eq("id", venueId)
    .single();
  if (!venue) return { error: "המקום לא נמצא" };

  const startsAt = israelToUtc(date, time);

  // duplicate warning: another event at the same venue on the same night
  if (formData.get("force") !== "1") {
    const win = dayWindow(date);
    const { data: sameDay } = await sb
      .from("events")
      .select("id, title_he, starts_at")
      .eq("venue_id", venueId)
      .gte("starts_at", win.from.toISOString())
      .lt("starts_at", win.to.toISOString());
    const clash = (sameDay ?? []).find((e) => e.id !== id);
    if (clash) {
      return {
        duplicateWarning: `כבר קיים אירוע במקום הזה בתאריך הזה: "${clash.title_he}". לשמור בכל זאת?`,
      };
    }
  }

  const endsTime = str(formData, "ends_time");
  const doorsTime = str(formData, "doors_time");
  const toSameNight = (t: string): string => {
    const utc = israelToUtc(date, t);
    // a time earlier than the start rolls into the next morning
    return (utc < startsAt ? new Date(utc.getTime() + 86_400_000) : utc).toISOString();
  };

  const isFree = formData.get("is_free") === "on";
  const payload = {
    title_he: title,
    description_he: str(formData, "description_he"),
    venue_id: venue.id,
    city_id: venue.city_id,
    organizer_id: str(formData, "organizer_id"),
    starts_at: startsAt.toISOString(),
    ends_at: endsTime ? toSameNight(endsTime) : null,
    doors_at: doorsTime ? toSameNight(doorsTime) : null,
    price_min: isFree ? null : num(formData, "price_min"),
    price_max: isFree ? null : num(formData, "price_max"),
    min_age: num(formData, "min_age"),
    ticket_url: str(formData, "ticket_url"),
    ticket_provider: str(formData, "ticket_provider"),
    image_url: str(formData, "image_url"),
    is_free: isFree,
    is_sold_out: formData.get("is_sold_out") === "on",
    status: (str(formData, "status") ?? "draft") as "draft" | "published" | "cancelled",
  };

  let eventSlug: string;
  if (id) {
    const { data: existing } = await sb.from("events").select("slug").eq("id", id).single();
    eventSlug = existing?.slug ?? "";
    const { error } = await sb.from("events").update(payload).eq("id", id);
    if (error) return { error: `שגיאה בשמירה: ${error.message}` };
  } else {
    // slug rule: {venue-slug}-{yyyy-mm-dd}-{short-title} — stable & unique
    eventSlug = `${venue.slug}-${date}-${slugify(title, 30)}`;
    const { error } = await sb.from("events").insert({ ...payload, slug: eventSlug });
    if (error) {
      return {
        error: error.code === "23505" ? "כבר קיים אירוע עם אותו כתובת (slug)" : `שגיאה בשמירה: ${error.message}`,
      };
    }
  }

  // sync genres
  const genreIds = formData.getAll("genre_ids").map(String).filter(Boolean);
  const { data: saved } = await sb.from("events").select("id").eq("slug", eventSlug).single();
  if (saved) {
    await sb.from("event_genres").delete().eq("event_id", saved.id);
    if (genreIds.length > 0) {
      await sb
        .from("event_genres")
        .insert(genreIds.map((genre_id) => ({ event_id: saved.id, genre_id })));
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const citySlug = (venue as any).cities?.slug ?? null;
  await revalidateEvent(citySlug, venue.slug, eventSlug);
  redirect("/admin?saved=1");
}

export async function setEventStatus(formData: FormData): Promise<void> {
  const sb = await requireUser();
  const id = String(formData.get("id"));
  const status = String(formData.get("status")) as "draft" | "published" | "cancelled";
  const { data: event } = await sb
    .from("events")
    .select("slug, venues(slug), cities(slug)")
    .eq("id", id)
    .single();
  await sb.from("events").update({ status }).eq("id", id);
  if (event) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const e = event as any;
    await revalidateEvent(e.cities?.slug ?? null, e.venues?.slug ?? null, e.slug);
  }
  revalidatePath("/admin");
}

/** "Duplicate this event" for recurring parties: copies everything as a draft dated +7 days. */
export async function duplicateEvent(formData: FormData): Promise<void> {
  const sb = await requireUser();
  const id = String(formData.get("id"));
  const { data: source } = await sb
    .from("events")
    .select("*, venues(slug), event_genres(genre_id)")
    .eq("id", id)
    .single();
  if (!source) return;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const s = source as any;
  const shift = (iso: string | null) =>
    iso ? new Date(new Date(iso).getTime() + 7 * 86_400_000).toISOString() : null;
  const newStarts = shift(s.starts_at)!;
  const newDate = eventNightDate(newStarts);
  const titlePart = s.slug.split("-").slice(4).join("-") || slugify(s.title_he, 30);
  const newSlug = `${s.venues?.slug ?? "venue"}-${newDate}-${titlePart}`;

  const { data: created, error } = await sb
    .from("events")
    .insert({
      slug: newSlug,
      title_he: s.title_he,
      description_he: s.description_he,
      venue_id: s.venue_id,
      city_id: s.city_id,
      organizer_id: s.organizer_id,
      starts_at: newStarts,
      ends_at: shift(s.ends_at),
      doors_at: shift(s.doors_at),
      price_min: s.price_min,
      price_max: s.price_max,
      currency: s.currency,
      min_age: s.min_age,
      ticket_url: s.ticket_url,
      ticket_provider: s.ticket_provider,
      image_url: s.image_url,
      is_free: s.is_free,
      is_sold_out: false,
      status: "draft",
    })
    .select("id")
    .single();

  if (!error && created && s.event_genres?.length) {
    await sb.from("event_genres").insert(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      s.event_genres.map((eg: any) => ({ event_id: created.id, genre_id: eg.genre_id })),
    );
  }
  revalidatePath("/admin");
  if (created) redirect(`/admin/events/${created.id}`);
}

export type VenueActionState = { error?: string; venueId?: string };

/** Inline "add new venue" from the event form. */
export async function createVenue(_prev: VenueActionState, formData: FormData): Promise<VenueActionState> {
  const sb = await requireUser();
  const name = str(formData, "venue_name_he");
  const cityId = str(formData, "venue_city_id");
  if (!name || !cityId) return { error: "שם עיר ומקום הם חובה" };
  const slug = slugify(str(formData, "venue_slug") ?? name, 40);
  const { data, error } = await sb
    .from("venues")
    .insert({
      slug,
      name_he: name,
      city_id: cityId,
      address: str(formData, "venue_address"),
      instagram: str(formData, "venue_instagram"),
      website: str(formData, "venue_website"),
    })
    .select("id")
    .single();
  if (error) return { error: error.message };
  revalidatePath("/admin");
  return { venueId: data.id };
}

export async function signOut(): Promise<void> {
  const sb = await supabaseServer();
  await sb.auth.signOut();
  redirect("/admin/login");
}
