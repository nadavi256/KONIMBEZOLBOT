import Link from "next/link";
import type { Crumb } from "@/lib/seo";

export function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="פירורי לחם" className="text-sm text-zinc-500">
      <ol className="flex flex-wrap items-center gap-1">
        {crumbs.map((c, i) => (
          <li key={c.href} className="flex items-center gap-1">
            {i > 0 ? <span aria-hidden className="text-zinc-600">‹</span> : null}
            {i === crumbs.length - 1 ? (
              <span className="text-zinc-300">{c.name}</span>
            ) : (
              <Link href={c.href} className="transition hover:text-neon-300">
                {c.name}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
