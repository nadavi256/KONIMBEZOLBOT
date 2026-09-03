import type { Faq } from "@/lib/answer";

export function FaqSection({ faqs }: { faqs: Faq[] }) {
  if (faqs.length === 0) return null;
  return (
    <section className="mt-10">
      <h2 className="text-xl font-bold">שאלות נפוצות</h2>
      <dl className="mt-4 space-y-4">
        {faqs.map((f) => (
          <div key={f.q} className="rounded-xl border border-zinc-200 bg-white p-4">
            <dt className="font-semibold">{f.q}</dt>
            <dd className="mt-1 text-zinc-600">{f.a}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
