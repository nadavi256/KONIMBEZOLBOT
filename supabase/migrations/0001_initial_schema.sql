-- NIGHTLIFE — initial schema
-- Phase 1: manual entry via admin panel.
-- Phase 2 (scrapers) is covered by events.source / events.source_ref — no schema change needed.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- cities
-- ---------------------------------------------------------------------------
create table public.cities (
  id          uuid primary key default gen_random_uuid(),
  slug        text not null unique,
  name_he     text not null,
  name_en     text not null,
  region      text,
  lat         double precision,
  lng         double precision,
  is_active   boolean not null default true
);

-- ---------------------------------------------------------------------------
-- venues
-- ---------------------------------------------------------------------------
create table public.venues (
  id             uuid primary key default gen_random_uuid(),
  slug           text not null unique,
  name_he        text not null,
  city_id        uuid not null references public.cities(id),
  address        text,
  lat            double precision,
  lng            double precision,
  instagram      text,
  website        text,
  description_he text,
  image_url      text,
  is_active      boolean not null default true
);

-- ---------------------------------------------------------------------------
-- organizers
-- ---------------------------------------------------------------------------
create table public.organizers (
  id        uuid primary key default gen_random_uuid(),
  slug      text not null unique,
  name_he   text not null,
  instagram text,
  website   text
);

-- ---------------------------------------------------------------------------
-- genres
-- ---------------------------------------------------------------------------
create table public.genres (
  id      uuid primary key default gen_random_uuid(),
  slug    text not null unique,
  name_he text not null
);

-- ---------------------------------------------------------------------------
-- events
-- ---------------------------------------------------------------------------
create type public.event_status as enum ('draft', 'published', 'cancelled');
create type public.ticket_provider as enum ('eventer', 'tixwise', 'zappa', 'other', 'free', 'door');

create table public.events (
  id              uuid primary key default gen_random_uuid(),
  slug            text not null unique,
  title_he        text not null,
  description_he  text,
  venue_id        uuid not null references public.venues(id),
  -- denormalized so list queries never join through venues
  city_id         uuid not null references public.cities(id),
  organizer_id    uuid references public.organizers(id),
  starts_at       timestamptz not null,
  ends_at         timestamptz,
  doors_at        timestamptz,
  price_min       numeric(10, 2),
  price_max       numeric(10, 2),
  currency        text not null default 'ILS',
  min_age         smallint,
  ticket_url      text,
  ticket_provider public.ticket_provider,
  image_url       text,
  is_free         boolean not null default false,
  is_sold_out     boolean not null default false,
  status          public.event_status not null default 'draft',
  source          text not null default 'manual',
  source_ref      text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create table public.event_genres (
  event_id uuid not null references public.events(id) on delete cascade,
  genre_id uuid not null references public.genres(id) on delete cascade,
  primary key (event_id, genre_id)
);

create index events_city_starts_idx  on public.events (city_id, starts_at);
create index events_status_starts_idx on public.events (status, starts_at);
create index events_slug_idx          on public.events (slug);
create index events_venue_idx         on public.events (venue_id);
create index event_genres_genre_idx   on public.event_genres (genre_id);

-- keep updated_at fresh
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger events_set_updated_at
  before update on public.events
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- Public (anon) may read everything the site renders; only authenticated
-- users (the single admin) may write. Phase 2 scrapers will use the service
-- role key, which bypasses RLS.
-- ---------------------------------------------------------------------------
alter table public.cities       enable row level security;
alter table public.venues       enable row level security;
alter table public.organizers   enable row level security;
alter table public.genres       enable row level security;
alter table public.events       enable row level security;
alter table public.event_genres enable row level security;

create policy "public read cities"     on public.cities       for select using (true);
create policy "public read venues"     on public.venues       for select using (true);
create policy "public read organizers" on public.organizers   for select using (true);
create policy "public read genres"     on public.genres       for select using (true);
create policy "public read events"     on public.events       for select using (true);
create policy "public read event_genres" on public.event_genres for select using (true);

create policy "admin write cities"     on public.cities       for all to authenticated using (true) with check (true);
create policy "admin write venues"     on public.venues       for all to authenticated using (true) with check (true);
create policy "admin write organizers" on public.organizers   for all to authenticated using (true) with check (true);
create policy "admin write genres"     on public.genres       for all to authenticated using (true) with check (true);
create policy "admin write events"     on public.events       for all to authenticated using (true) with check (true);
create policy "admin write event_genres" on public.event_genres for all to authenticated using (true) with check (true);

-- ---------------------------------------------------------------------------
-- Storage bucket for event images
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('event-images', 'event-images', true)
on conflict (id) do nothing;

create policy "public read event images"
  on storage.objects for select
  using (bucket_id = 'event-images');

create policy "admin upload event images"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'event-images');

create policy "admin update event images"
  on storage.objects for update to authenticated
  using (bucket_id = 'event-images');

create policy "admin delete event images"
  on storage.objects for delete to authenticated
  using (bucket_id = 'event-images');
