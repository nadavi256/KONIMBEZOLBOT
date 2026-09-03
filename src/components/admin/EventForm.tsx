"use client";

import { useActionState, useState } from "react";
import { createVenue, saveEvent, type ActionState } from "@/app/admin/actions";
import { supabaseBrowser } from "@/lib/supabase/client";
import type { City, EventRow, Genre, Organizer, Venue } from "@/lib/types";

type Props = {
  cities: City[];
  venues: Venue[];
  genres: Genre[];
  organizers: Organizer[];
  event?: EventRow & { genre_ids: string[] };
  /** Israel-local prefills for edit mode. */
  initialDate?: string;
  initialTime?: string;
  initialEndsTime?: string;
  initialDoorsTime?: string;
};

const input =
  "w-full rounded-xl border border-zinc-300 px-3 py-2 focus:border-violet-500 focus:outline-none";
const label = "block text-sm font-medium text-zinc-600 mb-1";

export function EventForm({
  cities,
  venues: initialVenues,
  genres,
  organizers,
  event,
  initialDate,
  initialTime,
  initialEndsTime,
  initialDoorsTime,
}: Props) {
  const [state, formAction, pending] = useActionState<ActionState, FormData>(saveEvent, {});
  const [venues, setVenues] = useState(initialVenues);
  const [venueId, setVenueId] = useState(event?.venue_id ?? "");
  const [showNewVenue, setShowNewVenue] = useState(false);
  const [venueError, setVenueError] = useState<string | null>(null);
  const [venueBusy, setVenueBusy] = useState(false);
  const [imageUrl, setImageUrl] = useState(event?.image_url ?? "");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isFree, setIsFree] = useState(event?.is_free ?? false);

  // inline "add new venue" (called imperatively — forms can't nest)
  const [nv, setNv] = useState({ name: "", cityId: "", address: "", instagram: "", website: "" });

  async function addVenue() {
    setVenueBusy(true);
    setVenueError(null);
    const fd = new FormData();
    fd.set("venue_name_he", nv.name);
    fd.set("venue_city_id", nv.cityId);
    fd.set("venue_address", nv.address);
    fd.set("venue_instagram", nv.instagram);
    fd.set("venue_website", nv.website);
    const result = await createVenue({}, fd);
    setVenueBusy(false);
    if (result.error || !result.venueId) {
      setVenueError(result.error ?? "שגיאה ביצירת מקום");
      return;
    }
    setVenues((prev) => [
      ...prev,
      {
        id: result.venueId!,
        slug: "",
        name_he: nv.name,
        city_id: nv.cityId,
        address: nv.address || null,
        lat: null,
        lng: null,
        instagram: nv.instagram || null,
        website: nv.website || null,
        description_he: null,
        image_url: null,
        is_active: true,
      },
    ]);
    setVenueId(result.venueId);
    setShowNewVenue(false);
  }

  async function onImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    const sb = supabaseBrowser();
    const path = `${Date.now()}-${file.name.replace(/[^a-zA-Z0-9.\-_]/g, "")}`;
    const { error } = await sb.storage.from("event-images").upload(path, file, { upsert: false });
    setUploading(false);
    if (error) {
      setUploadError(`שגיאה בהעלאה: ${error.message}`);
      return;
    }
    setImageUrl(sb.storage.from("event-images").getPublicUrl(path).data.publicUrl);
  }

  return (
    <form action={formAction} className="space-y-5">
      {event ? <input type="hidden" name="id" value={event.id} /> : null}
      <input type="hidden" name="image_url" value={imageUrl} />

      <div>
        <label className={label}>שם האירוע *</label>
        <input name="title_he" required defaultValue={event?.title_he} className={input} />
      </div>

      <div>
        <label className={label}>תיאור</label>
        <textarea name="description_he" rows={3} defaultValue={event?.description_he ?? ""} className={input} />
      </div>

      <div>
        <label className={label}>מקום *</label>
        <div className="flex gap-2">
          <select
            name="venue_id"
            required
            value={venueId}
            onChange={(e) => setVenueId(e.target.value)}
            className={input}
          >
            <option value="">בחרו מקום…</option>
            {venues.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name_he} ({cities.find((c) => c.id === v.city_id)?.name_he ?? ""})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setShowNewVenue((s) => !s)}
            className="shrink-0 rounded-xl border border-violet-300 px-3 py-2 text-sm text-violet-700 hover:bg-violet-50"
          >
            {showNewVenue ? "סגירה" : "+ מקום חדש"}
          </button>
        </div>

        {showNewVenue ? (
          <div className="mt-3 space-y-3 rounded-xl border border-violet-200 bg-violet-50 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <input placeholder="שם המקום *" value={nv.name} onChange={(e) => setNv({ ...nv, name: e.target.value })} className={input} />
              <select value={nv.cityId} onChange={(e) => setNv({ ...nv, cityId: e.target.value })} className={input}>
                <option value="">עיר *</option>
                {cities.map((c) => (
                  <option key={c.id} value={c.id}>{c.name_he}</option>
                ))}
              </select>
              <input placeholder="כתובת" value={nv.address} onChange={(e) => setNv({ ...nv, address: e.target.value })} className={input} />
              <input placeholder="אינסטגרם" dir="ltr" value={nv.instagram} onChange={(e) => setNv({ ...nv, instagram: e.target.value })} className={input} />
            </div>
            {venueError ? <p className="text-sm text-red-600">{venueError}</p> : null}
            <button
              type="button"
              onClick={addVenue}
              disabled={venueBusy || !nv.name || !nv.cityId}
              className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {venueBusy ? "יוצר…" : "יצירת מקום"}
            </button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label className={label}>תאריך *</label>
          <input type="date" name="date" required defaultValue={initialDate} className={input} />
        </div>
        <div>
          <label className={label}>שעת התחלה</label>
          <input type="time" name="time" defaultValue={initialTime ?? "23:00"} className={input} />
        </div>
        <div>
          <label className={label}>פתיחת דלתות</label>
          <input type="time" name="doors_time" defaultValue={initialDoorsTime} className={input} />
        </div>
        <div>
          <label className={label}>שעת סיום</label>
          <input type="time" name="ends_time" defaultValue={initialEndsTime} className={input} />
        </div>
        <div>
          <label className={label}>גיל מינימום</label>
          <input type="number" name="min_age" min={0} max={99} defaultValue={event?.min_age ?? ""} className={input} />
        </div>
        <div>
          <label className={label}>מפיק</label>
          <select name="organizer_id" defaultValue={event?.organizer_id ?? ""} className={input}>
            <option value="">—</option>
            {organizers.map((o) => (
              <option key={o.id} value={o.id}>{o.name_he}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className={label}>ז&apos;אנרים</label>
        <div className="flex flex-wrap gap-2">
          {genres.map((g) => (
            <label key={g.id} className="flex cursor-pointer items-center gap-1.5 rounded-full border border-zinc-300 bg-white px-3 py-1.5 text-sm has-checked:border-violet-500 has-checked:bg-violet-100">
              <input
                type="checkbox"
                name="genre_ids"
                value={g.id}
                defaultChecked={event?.genre_ids.includes(g.id)}
                className="accent-violet-600"
              />
              {g.name_he}
            </label>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex items-center gap-2">
          <input type="checkbox" name="is_free" checked={isFree} onChange={(e) => setIsFree(e.target.checked)} className="accent-violet-600" />
          כניסה חופשית
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" name="is_sold_out" defaultChecked={event?.is_sold_out} className="accent-violet-600" />
          אזלו הכרטיסים
        </label>
        {!isFree ? (
          <>
            <div>
              <label className={label}>מחיר מינימלי (₪)</label>
              <input type="number" name="price_min" min={0} defaultValue={event?.price_min ?? ""} className={input} />
            </div>
            <div>
              <label className={label}>מחיר מקסימלי (₪)</label>
              <input type="number" name="price_max" min={0} defaultValue={event?.price_max ?? ""} className={input} />
            </div>
          </>
        ) : null}
        <div>
          <label className={label}>קישור לכרטיסים</label>
          <input type="url" name="ticket_url" dir="ltr" defaultValue={event?.ticket_url ?? ""} className={input} />
        </div>
        <div>
          <label className={label}>ספק כרטיסים</label>
          <select name="ticket_provider" defaultValue={event?.ticket_provider ?? ""} className={input}>
            <option value="">—</option>
            <option value="eventer">Eventer</option>
            <option value="tixwise">Tixwise</option>
            <option value="zappa">Zappa</option>
            <option value="door">בכניסה</option>
            <option value="free">חינם</option>
            <option value="other">אחר</option>
          </select>
        </div>
      </div>

      <div>
        <label className={label}>תמונה</label>
        <input type="file" accept="image/*" onChange={onImageChange} className="text-sm" />
        {uploading ? <p className="mt-1 text-sm text-zinc-500">מעלה…</p> : null}
        {uploadError ? <p className="mt-1 text-sm text-red-600">{uploadError}</p> : null}
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt="" className="mt-2 h-32 rounded-xl object-cover" />
        ) : null}
      </div>

      <div>
        <label className={label}>סטטוס</label>
        <select name="status" defaultValue={event?.status ?? "draft"} className={input}>
          <option value="draft">טיוטה</option>
          <option value="published">מפורסם</option>
          <option value="cancelled">בוטל</option>
        </select>
      </div>

      {state.duplicateWarning ? (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
          <p className="font-medium text-amber-800">{state.duplicateWarning}</p>
          <label className="mt-2 flex items-center gap-2 text-sm text-amber-800">
            <input type="checkbox" name="force" value="1" className="accent-amber-600" />
            כן, לשמור בכל זאת
          </label>
        </div>
      ) : null}
      {state.error ? <p className="text-red-600">{state.error}</p> : null}

      <button
        type="submit"
        disabled={pending || uploading}
        className="rounded-xl bg-violet-600 px-6 py-2.5 font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
      >
        {pending ? "שומר…" : "שמירה"}
      </button>
    </form>
  );
}
