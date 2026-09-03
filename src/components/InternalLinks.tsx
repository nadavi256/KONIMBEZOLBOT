import Link from "next/link";

export type LinkGroup = { title: string; links: { name: string; href: string }[] };

export function InternalLinks({ groups }: { groups: LinkGroup[] }) {
  const nonEmpty = groups.filter((g) => g.links.length > 0);
  if (nonEmpty.length === 0) return null;
  return (
    <section className="surface mt-12 p-5">
      <h2 className="text-lg font-black">עוד באתר</h2>
      <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {nonEmpty.map((g) => (
          <div key={g.title}>
            <h3 className="text-xs font-bold uppercase tracking-wide text-zinc-500">{g.title}</h3>
            <ul className="mt-2 space-y-1.5">
              {g.links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="text-sm text-glow-300 transition hover:text-neon-300">
                    {l.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
