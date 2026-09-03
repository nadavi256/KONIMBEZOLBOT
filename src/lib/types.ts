export type City = {
  id: string;
  slug: string;
  name_he: string;
  name_en: string;
  region: string | null;
  lat: number | null;
  lng: number | null;
  is_active: boolean;
};

export type Venue = {
  id: string;
  slug: string;
  name_he: string;
  city_id: string;
  address: string | null;
  lat: number | null;
  lng: number | null;
  instagram: string | null;
  website: string | null;
  description_he: string | null;
  image_url: string | null;
  is_active: boolean;
};

export type Organizer = {
  id: string;
  slug: string;
  name_he: string;
  instagram: string | null;
  website: string | null;
};

export type Genre = {
  id: string;
  slug: string;
  name_he: string;
};

export type EventStatus = "draft" | "published" | "cancelled";
export type TicketProvider = "eventer" | "tixwise" | "zappa" | "other" | "free" | "door";

export type EventRow = {
  id: string;
  slug: string;
  title_he: string;
  description_he: string | null;
  venue_id: string;
  city_id: string;
  organizer_id: string | null;
  starts_at: string;
  ends_at: string | null;
  doors_at: string | null;
  price_min: number | null;
  price_max: number | null;
  currency: string;
  min_age: number | null;
  ticket_url: string | null;
  ticket_provider: TicketProvider | null;
  image_url: string | null;
  is_free: boolean;
  is_sold_out: boolean;
  status: EventStatus;
  source: string;
  source_ref: string | null;
  created_at: string;
  updated_at: string;
};

/** Event with the joins every list/detail page needs. */
export type EventFull = EventRow & {
  venue: Venue;
  city: City;
  organizer: Organizer | null;
  genres: Genre[];
};
