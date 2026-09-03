import { ImageResponse } from "next/og";
import { SITE_NAME } from "@/lib/site";

export const revalidate = 86400;

/** Heebo supports Hebrew; fetched once per server instance, cached. */
let fontPromise: Promise<ArrayBuffer | null> | null = null;

function loadFont(): Promise<ArrayBuffer | null> {
  fontPromise ??= (async () => {
    try {
      const css = await (
        await fetch("https://fonts.googleapis.com/css2?family=Heebo:wght@700", {
          headers: { "User-Agent": "Mozilla/5.0" },
        })
      ).text();
      const url = css.match(/src: url\((.+?)\)/)?.[1];
      if (!url) return null;
      return await (await fetch(url)).arrayBuffer();
    } catch {
      return null;
    }
  })();
  return fontPromise;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const title = (searchParams.get("title") ?? SITE_NAME).slice(0, 90);
  const subtitle = (searchParams.get("subtitle") ?? "").slice(0, 60);
  const font = await loadFont();

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "72px",
          background:
            "radial-gradient(48rem 30rem at 90% -10%, rgba(255,45,132,0.35), transparent 60%), linear-gradient(135deg, #0a0713 0%, #251b3a 55%, #7c3aed 130%)",
          color: "white",
          fontFamily: font ? "Heebo" : "sans-serif",
        }}
      >
        <div style={{ display: "flex", fontSize: 32, color: "#ff5ca2", marginBottom: 24 }}>
          {SITE_NAME}
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 64,
            fontWeight: 700,
            lineHeight: 1.2,
            direction: "rtl",
            textAlign: "right",
          }}
        >
          {title}
        </div>
        {subtitle ? (
          <div
            style={{
              display: "flex",
              fontSize: 36,
              color: "#ddd6fe",
              marginTop: 20,
              direction: "rtl",
              textAlign: "right",
            }}
          >
            {subtitle}
          </div>
        ) : null}
      </div>
    ),
    {
      width: 1200,
      height: 630,
      ...(font ? { fonts: [{ name: "Heebo", data: font, weight: 700 as const }] } : {}),
    },
  );
}
