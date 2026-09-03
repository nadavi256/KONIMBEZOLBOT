import type { Faq } from "@/lib/answer";

export function FaqSection({ faqs }: { faqs: Faq[] }) {
  if (faqs.length === 0) return null;
  return (
    <section className="mt-12">
      <h2 className="text-xl font-black">שאלות נפוצות</h2>
      <dl className="mt-4 space-y-3">
        {faqs.map((f) => (
          <div key={f.q} className="surface p-4">
            <dt className="font-bold text-zinc-100">{f.q}</dt>
            <dd className="mt-1 text-zinc-400">{f.a}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
