import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-16 text-center">
      <h1 className="text-3xl font-black">העמוד לא נמצא</h1>
      <p className="mt-3 text-zinc-500">
        אולי האירוע כבר עבר, או שהקישור שגוי.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block btn-neon !px-6 !py-3 !text-base"
      >
        מה יש הערב?
      </Link>
    </main>
  );
}
