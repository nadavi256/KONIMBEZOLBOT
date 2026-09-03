import type { Metadata } from "next";
import Link from "next/link";
import Script from "next/script";
import { SITE_DESCRIPTION, SITE_NAME, siteUrl } from "@/lib/site";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
  description: SITE_DESCRIPTION,
  alternates: { languages: { "he-IL": "/" } },
  ...(process.env.NEXT_PUBLIC_GSC_VERIFICATION
    ? { verification: { google: process.env.NEXT_PUBLIC_GSC_VERIFICATION } }
    : {}),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const ga4 = process.env.NEXT_PUBLIC_GA4_ID;
  return (
    <html lang="he" dir="rtl">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <header className="sticky top-0 z-40 border-b border-white/8 bg-night-950/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <Link href="/" className="text-2xl font-black tracking-tight">
              <span className="text-neon-gradient">{SITE_NAME}</span>
              <span className="text-neon-500">.</span>
            </Link>
            <span className="text-sm text-zinc-400">מה קורה הלילה בישראל</span>
          </div>
        </header>
        {children}
        <footer className="mt-16 border-t border-white/8 bg-night-900/60 py-8 text-center text-sm text-zinc-500">
          <p>
            <span className="font-bold text-zinc-300">{SITE_NAME}</span> — {SITE_DESCRIPTION}
          </p>
        </footer>
        {ga4 ? (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${ga4}`}
              strategy="afterInteractive"
            />
            <Script id="ga4" strategy="afterInteractive">
              {`window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', '${ga4}');`}
            </Script>
          </>
        ) : null}
      </body>
    </html>
  );
}
