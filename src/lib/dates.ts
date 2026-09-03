/**
 * All public-facing time logic runs in Asia/Jerusalem, regardless of server TZ.
 * A "night" belongs to the calendar day it starts on: the window for date D is
 * [D 06:00, D+1 06:00) Israel time, so a party that starts at 23:00 and a
 * 00:30 after-party both count as "tonight".
 */
const TZ = "Asia/Jerusalem";

function tzOffsetMs(instant: Date): number {
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  const p = Object.fromEntries(dtf.formatToParts(instant).map((x) => [x.type, x.value]));
  const asUtc = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute, +p.second);
  return asUtc - instant.getTime();
}

/** Interpret a local Israel date+time and return the UTC instant. */
export function israelToUtc(dateStr: string, timeStr = "00:00"): Date {
  const naive = new Date(`${dateStr}T${timeStr}:00Z`);
  const guess = new Date(naive.getTime() - tzOffsetMs(naive));
  return new Date(naive.getTime() - tzOffsetMs(guess));
}

/** yyyy-mm-dd of "now" in Israel. */
export function todayInIsrael(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
}

export function addDays(dateStr: string, n: number): string {
  const d = new Date(`${dateStr}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function isValidDateSlug(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T12:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

/** Days from today (Israel) to the given date; 0 = today, negative = past. */
export function daysFromToday(dateStr: string): number {
  const today = new Date(`${todayInIsrael()}T12:00:00Z`).getTime();
  const target = new Date(`${dateStr}T12:00:00Z`).getTime();
  return Math.round((target - today) / 86_400_000);
}

/** The night-window (UTC instants) for an Israel calendar date. */
export function dayWindow(dateStr: string): { from: Date; to: Date } {
  return { from: israelToUtc(dateStr, "06:00"), to: israelToUtc(addDays(dateStr, 1), "06:00") };
}

/** Thu–Sat of the current week (Israel), as [thursday, window]. */
export function weekendDates(): { thursday: string; friday: string; saturday: string } {
  const today = todayInIsrael();
  const dow = new Date(`${today}T12:00:00Z`).getUTCDay(); // 0=Sun … 6=Sat
  const thursday = addDays(today, 4 - dow); // Sun–Wed → upcoming Thu; Fri/Sat → this week's Thu
  return { thursday, friday: addDays(thursday, 1), saturday: addDays(thursday, 2) };
}

export function weekendWindow(): { from: Date; to: Date } {
  const { thursday, saturday } = weekendDates();
  return { from: israelToUtc(thursday, "06:00"), to: israelToUtc(addDays(saturday, 1), "06:00") };
}

/** "יום חמישי, 3 בספטמבר" */
export function hebrewDate(dateStr: string): string {
  const d = israelToUtc(dateStr, "12:00");
  const weekday = new Intl.DateTimeFormat("he-IL", { timeZone: TZ, weekday: "long" }).format(d);
  const dayMonth = new Intl.DateTimeFormat("he-IL", { timeZone: TZ, day: "numeric", month: "long" }).format(d);
  return `${weekday}, ${dayMonth}`;
}

/** "23:00" in Israel time for a stored UTC timestamp. */
export function israelTime(iso: string): string {
  return new Intl.DateTimeFormat("he-IL", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

/** Israel calendar date (yyyy-mm-dd) an event belongs to (06:00 cutoff). */
export function eventNightDate(iso: string): string {
  const d = new Date(new Date(iso).getTime() - 6 * 3600_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(d);
}

/** "עודכן לפני X שעות" from the freshest updated_at. */
export function updatedAgoHe(isoTimes: string[]): string | null {
  if (isoTimes.length === 0) return null;
  const newest = Math.max(...isoTimes.map((t) => new Date(t).getTime()));
  const hours = Math.max(0, Math.floor((Date.now() - newest) / 3600_000));
  if (hours === 0) return "עודכן לפני פחות משעה";
  if (hours === 1) return "עודכן לפני שעה";
  if (hours === 2) return "עודכן לפני שעתיים";
  if (hours < 24) return `עודכן לפני ${hours} שעות`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "עודכן לפני יום";
  if (days === 2) return "עודכן לפני יומיים";
  return `עודכן לפני ${days} ימים`;
}
