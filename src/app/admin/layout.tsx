import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "ניהול",
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <nav className="mb-6 flex items-center gap-4 border-b border-zinc-200 pb-3 text-sm">
        <Link href="/admin" className="font-bold text-violet-700">
          ניהול אירועים
        </Link>
        <Link href="/admin/events/new" className="text-zinc-600 hover:text-violet-700">
          אירוע חדש
        </Link>
        <Link href="/" className="mr-auto text-zinc-500 hover:text-violet-700">
          לאתר ←
        </Link>
      </nav>
      {children}
    </div>
  );
}
