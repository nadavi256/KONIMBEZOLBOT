import Link from "next/link";
import { hebrewDate, eventNightDate, israelTime } from "@/lib/dates";
import { supabaseServer } from "@/lib/supabase/server";
import { duplicateEvent, setEventStatus, signOut } from "./actions";

export const dynamic = "force-dynamic";

const STATUS_HE: Record<string, string> = {
  draft: "טיוטה",
  published: "מפורסם",
  cancelled: "בוטל",
};

export default async function AdminHome() {
  const sb = await supabaseServer();
  const { data: events } = await sb
    .from("events")
    .select("id, slug, title_he, starts_at, status, venues(name_he), cities(name_he)")
    .gte("starts_at", new Date(Date.now() - 86_400_000).toISOString())
    .order("starts_at", { ascending: true })
    .limit(200);

  return (
    <main>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">אירועים קרובים</h1>
        <div className="flex items-center gap-3">
          <Link
            href="/admin/events/new"
            className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700"
          >
            + אירוע חדש
          </Link>
          <form action={signOut}>
            <button className="text-sm text-zinc-500 hover:text-red-600">התנתקות</button>
          </form>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-right text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">אירוע</th>
              <th className="px-4 py-3 font-medium">תאריך</th>
              <th className="px-4 py-3 font-medium">מקום</th>
              <th className="px-4 py-3 font-medium">סטטוס</th>
              <th className="px-4 py-3 font-medium">פעולות</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {(events ?? []).map((e) => {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const row = e as any;
              return (
                <tr key={row.id}>
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/admin/events/${row.id}`} className="text-violet-700 hover:underline">
                      {row.title_he}
                    </Link>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {hebrewDate(eventNightDate(row.starts_at))} · {israelTime(row.starts_at)}
                  </td>
                  <td className="px-4 py-3">
                    {row.venues?.name_he} ({row.cities?.name_he})
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        row.status === "published"
                          ? "rounded-full bg-green-100 px-2 py-0.5 text-green-700"
                          : row.status === "cancelled"
                            ? "rounded-full bg-red-100 px-2 py-0.5 text-red-700"
                            : "rounded-full bg-zinc-100 px-2 py-0.5 text-zinc-600"
                      }
                    >
                      {STATUS_HE[row.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <Link href={`/admin/events/${row.id}`} className="text-violet-700 hover:underline">
                        עריכה
                      </Link>
                      {row.status !== "published" ? (
                        <form action={setEventStatus}>
                          <input type="hidden" name="id" value={row.id} />
                          <input type="hidden" name="status" value="published" />
                          <button className="text-green-700 hover:underline">פרסום</button>
                        </form>
                      ) : (
                        <form action={setEventStatus}>
                          <input type="hidden" name="id" value={row.id} />
                          <input type="hidden" name="status" value="cancelled" />
                          <button className="text-red-700 hover:underline">ביטול</button>
                        </form>
                      )}
                      <form action={duplicateEvent}>
                        <input type="hidden" name="id" value={row.id} />
                        <button className="text-zinc-600 hover:underline">שכפול</button>
                      </form>
                    </div>
                  </td>
                </tr>
              );
            })}
            {(events ?? []).length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-zinc-500">
                  אין אירועים קרובים. <Link href="/admin/events/new" className="text-violet-700 underline">הוסיפו את הראשון</Link>.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
