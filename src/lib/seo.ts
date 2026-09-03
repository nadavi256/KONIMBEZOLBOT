import { absoluteUrl } from "./site";
import type { Faq } from "./answer";
import type { EventFull, Venue } from "./types";

/**
 * JSON-LD builders. Every object targets zero errors / zero warnings in
 * Google's Rich Results test, so optional-but-recommended fields are always
 * populated when the data exists.
 */

type JsonLd = Record<string, unknown>;

export function eventJsonLd(e: EventFull): JsonLd {
  const offers =
    e.is_free || e.price_min != null || e.price_max != null
      ? {
          "@type": "Offer",
          price: e.is_free ? 0 : Number(e.price_min ?? e.price_max ?? 0),
          priceCurrency: e.currency || "ILS",
          url: e.ticket_url ?? absoluteUrl(`/event/${e.slug}`),
          availability: e.is_sold_out
            ? "https://schema.org/SoldOut"
            : "https://schema.org/InStock",
          validFrom: e.created_at,
        }
      : undefined;

  return {
    "@context": "https://schema.org",
    "@type": "Event",
    name: e.title_he,
    description: e.description_he ?? e.title_he,
    startDate: e.starts_at,
    ...(e.ends_at ? { endDate: e.ends_at } : {}),
    ...(e.doors_at ? { doorTime: e.doors_at } : {}),
    eventStatus:
      e.status === "cancelled"
        ? "https://schema.org/EventCancelled"
        : "https://schema.org/EventScheduled",
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    location: placeJsonLd(e.venue, e.city.name_he),
    ...(e.image_url ? { image: [e.image_url] } : {}),
    ...(offers ? { offers } : {}),
    ...(e.organizer
      ? {
          organizer: {
            "@type": "Organization",
            name: e.organizer.name_he,
            ...(e.organizer.website ? { url: e.organizer.website } : {}),
          },
        }
      : {
          organizer: { "@type": "Organization", name: e.venue.name_he },
        }),
    performer: { "@type": "PerformingGroup", name: e.title_he },
    url: absoluteUrl(`/event/${e.slug}`),
  };
}

function placeJsonLd(venue: Venue, cityNameHe: string): JsonLd {
  return {
    "@type": "Place",
    name: venue.name_he,
    address: {
      "@type": "PostalAddress",
      streetAddress: venue.address ?? venue.name_he,
      addressLocality: cityNameHe,
      addressCountry: "IL",
    },
    ...(venue.lat != null && venue.lng != null
      ? { geo: { "@type": "GeoCoordinates", latitude: venue.lat, longitude: venue.lng } }
      : {}),
  };
}

export function itemListJsonLd(events: EventFull[]): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    itemListElement: events.map((e, i) => ({
      "@type": "ListItem",
      position: i + 1,
      item: eventJsonLd(e),
    })),
  };
}

export function faqJsonLd(faqs: Faq[]): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };
}

export type Crumb = { name: string; href: string };

export function breadcrumbJsonLd(crumbs: Crumb[]): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.name,
      item: absoluteUrl(c.href),
    })),
  };
}

export function venueJsonLd(venue: Venue, cityNameHe: string): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "NightClub",
    name: venue.name_he,
    ...(venue.description_he ? { description: venue.description_he } : {}),
    address: {
      "@type": "PostalAddress",
      streetAddress: venue.address ?? venue.name_he,
      addressLocality: cityNameHe,
      addressCountry: "IL",
    },
    ...(venue.lat != null && venue.lng != null
      ? { geo: { "@type": "GeoCoordinates", latitude: venue.lat, longitude: venue.lng } }
      : {}),
    ...(venue.image_url ? { image: [venue.image_url] } : {}),
    ...(venue.website ? { url: venue.website } : { url: absoluteUrl(`/venue/${venue.slug}`) }),
    ...(venue.instagram ? { sameAs: [venue.instagram] } : {}),
  };
}
