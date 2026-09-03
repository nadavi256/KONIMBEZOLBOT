import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site";

const AI_BOTS = [
  "GPTBot",
  "ClaudeBot",
  "Claude-Web",
  "PerplexityBot",
  "Google-Extended",
  "CCBot",
  "Applebot-Extended",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: ["/admin"] },
      // explicit welcome mat for AI crawlers (GEO)
      ...AI_BOTS.map((bot) => ({ userAgent: bot, allow: "/" as const, disallow: ["/admin"] })),
    ],
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
