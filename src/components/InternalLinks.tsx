import Link from "next/link";

export type LinkGroup = { title: string; links: { name: string; href: string }[] };

export function InternalLinks({ groups }: { groups: LinkGroup[] }) {
  const nonEmpty = groups.filter((g) => g.links.length > 0);
  if (nonEmpty.length === 0) return null;
  return (
    <section className="mt-10 rounded-2xl bg-zinc-100 p-5">
      <h2 className="text-lg font-bold">עוד באתר</h2>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {nonEmpty.map((g) => (
          <div key={g.title}>
            <h3 className="text-sm font-semibold text-zinc-500">{g.title}</h3>
            <ul className="mt-1 space-y-1">
              {g.links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="text-violet-700 hover:underline">
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
