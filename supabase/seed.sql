-- NIGHTLIFE — seed data
-- 4 cities, 10 genres, 5 venues, 1 organizer, 10 fake events.
-- Event dates are relative to now() so the seed is always "fresh".

-- cities ---------------------------------------------------------------------
insert into public.cities (slug, name_he, name_en, region, lat, lng, is_active) values
  ('haifa',     'חיפה',     'Haifa',     'north',  32.7940, 34.9896, true),
  ('krayot',    'קריות',    'Krayot',    'north',  32.8398, 35.0771, true),
  ('tel-aviv',  'תל אביב',  'Tel Aviv',  'center', 32.0853, 34.7818, true),
  ('jerusalem', 'ירושלים',  'Jerusalem', 'center', 31.7683, 35.2137, true)
on conflict (slug) do nothing;

-- genres ---------------------------------------------------------------------
insert into public.genres (slug, name_he) values
  ('techno',     'טכנו'),
  ('hiphop',     'היפ הופ'),
  ('mainstream', 'מיינסטרים'),
  ('latin',      'לאטינו'),
  ('mizrahi',    'מזרחית'),
  ('rock',       'רוק'),
  ('indie',      'אינדי'),
  ('drag',       'דראג'),
  ('student',    'סטודנטים'),
  ('karaoke',    'קריוקי')
on conflict (slug) do nothing;

-- venues ---------------------------------------------------------------------
insert into public.venues (slug, name_he, city_id, address, lat, lng, instagram, website, description_he, is_active) values
  ('barbara',      'ברברה',        (select id from public.cities where slug = 'haifa'),     'שדרות בן גוריון 6, חיפה',  32.8184, 34.9885, 'https://instagram.com/barbara.haifa', null, 'בר מועדון במושבה הגרמנית עם ליינים מתחלפים.', true),
  ('sirena',       'הסירנה',       (select id from public.cities where slug = 'haifa'),     'רחוב הנמל 32, חיפה',       32.8206, 34.9992, null, null, 'מועדון אנדרגראונד בעיר התחתית.', true),
  ('block',        'הבלוק',        (select id from public.cities where slug = 'tel-aviv'),  'שדרות הר ציון 157, תל אביב', 32.0532, 34.7794, 'https://instagram.com/theblocktlv', 'https://block-club.com', 'מועדון הטכנו המרכזי של תל אביב בתחנה המרכזית.', true),
  ('kuli-alma',    'קולי עלמא',    (select id from public.cities where slug = 'tel-aviv'),  'מקווה ישראל 10, תל אביב',  32.0629, 34.7757, 'https://instagram.com/kulialma', 'https://kulialma.com', 'גלריה-מועדון עם מוזיקה ואמנות מקומית.', true),
  ('yellow',       'ילו סאבמרין',  (select id from public.cities where slug = 'jerusalem'), 'הרכבים 13, ירושלים',       31.7515, 35.2093, null, 'https://yellowsubmarine.org.il', 'מרכז מוזיקה חי בתלפיות.', true)
on conflict (slug) do nothing;

-- organizers -----------------------------------------------------------------
insert into public.organizers (slug, name_he, instagram) values
  ('night-owls', 'ינשופי לילה', 'https://instagram.com/night.owls.il')
on conflict (slug) do nothing;

-- events ---------------------------------------------------------------------
-- helper CTE-style inserts; slug rule: {venue-slug}-{yyyy-mm-dd}-{short-title}
with v as (
  select slug, id, city_id from public.venues
), day0 as (
  select (now() at time zone 'Asia/Jerusalem')::date as d
)
insert into public.events
  (slug, title_he, description_he, venue_id, city_id, organizer_id, starts_at, ends_at, price_min, price_max, min_age, ticket_url, ticket_provider, is_free, status)
select * from (
  values
  (
    'barbara-' || to_char((select d from day0), 'YYYY-MM-DD') || '-techno-night',
    'לילה של טכנו בברברה',
    'ליין טכנו שבועי עם דיג׳יים מקומיים.',
    (select id from v where slug = 'barbara'), (select city_id from v where slug = 'barbara'),
    (select id from public.organizers where slug = 'night-owls'),
    ((select d from day0)::timestamp + interval '23 hours') at time zone 'Asia/Jerusalem',
    ((select d from day0)::timestamp + interval '29 hours') at time zone 'Asia/Jerusalem',
    60::numeric, 80::numeric, 21::smallint, 'https://example.com/tickets/1', 'eventer'::public.ticket_provider, false, 'published'::public.event_status
  ),
  (
    'sirena-' || to_char((select d from day0), 'YYYY-MM-DD') || '-hiphop-party',
    'מסיבת היפ הופ בהסירנה',
    'כל הבנגרים של הסצנה, סט פתיחה מקומי.',
    (select id from v where slug = 'sirena'), (select city_id from v where slug = 'sirena'),
    null,
    ((select d from day0)::timestamp + interval '23 hours 30 minutes') at time zone 'Asia/Jerusalem',
    null,
    50::numeric, 70::numeric, 18::smallint, 'https://example.com/tickets/2', 'tixwise'::public.ticket_provider, false, 'published'::public.event_status
  ),
  (
    'block-' || to_char((select d from day0), 'YYYY-MM-DD') || '-techno-marathon',
    'מרתון טכנו בהבלוק',
    'שמונה שעות של טכנו עם אורח בינלאומי.',
    (select id from v where slug = 'block'), (select city_id from v where slug = 'block'),
    (select id from public.organizers where slug = 'night-owls'),
    ((select d from day0)::timestamp + interval '23 hours') at time zone 'Asia/Jerusalem',
    ((select d from day0)::timestamp + interval '31 hours') at time zone 'Asia/Jerusalem',
    90::numeric, 120::numeric, 21::smallint, 'https://example.com/tickets/3', 'eventer'::public.ticket_provider, false, 'published'::public.event_status
  ),
  (
    'kuli-alma-' || to_char((select d from day0), 'YYYY-MM-DD') || '-free-entry',
    'ערב כניסה חופשית בקולי עלמא',
    'דיג׳יי סטים, אמנות מקומית וכניסה חופשית.',
    (select id from v where slug = 'kuli-alma'), (select city_id from v where slug = 'kuli-alma'),
    null,
    ((select d from day0)::timestamp + interval '22 hours') at time zone 'Asia/Jerusalem',
    null,
    null::numeric, null::numeric, 24::smallint, null, 'free'::public.ticket_provider, true, 'published'::public.event_status
  ),
  (
    'yellow-' || to_char((select d from day0), 'YYYY-MM-DD') || '-indie-live',
    'הופעת אינדי חיה בילו סאבמרין',
    'שלוש להקות אינדי מקומיות על במה אחת.',
    (select id from v where slug = 'yellow'), (select city_id from v where slug = 'yellow'),
    null,
    ((select d from day0)::timestamp + interval '21 hours') at time zone 'Asia/Jerusalem',
    null,
    70::numeric, 70::numeric, null::smallint, 'https://example.com/tickets/5', 'other'::public.ticket_provider, false, 'published'::public.event_status
  ),
  (
    'barbara-' || to_char((select d from day0) + 1, 'YYYY-MM-DD') || '-karaoke',
    'קריוקי בברברה',
    'ערב קריוקי פתוח, שירה על הבר.',
    (select id from v where slug = 'barbara'), (select city_id from v where slug = 'barbara'),
    null,
    (((select d from day0) + 1)::timestamp + interval '21 hours') at time zone 'Asia/Jerusalem',
    null,
    null::numeric, null::numeric, 18::smallint, null, 'free'::public.ticket_provider, true, 'published'::public.event_status
  ),
  (
    'block-' || to_char((select d from day0) + 1, 'YYYY-MM-DD') || '-mainstream',
    'מסיבת מיינסטרים בהבלוק',
    'להיטים של עכשיו כל הלילה.',
    (select id from v where slug = 'block'), (select city_id from v where slug = 'block'),
    null,
    (((select d from day0) + 1)::timestamp + interval '23 hours') at time zone 'Asia/Jerusalem',
    null,
    80::numeric, 100::numeric, 18::smallint, 'https://example.com/tickets/7', 'tixwise'::public.ticket_provider, false, 'published'::public.event_status
  ),
  (
    'sirena-' || to_char((select d from day0) + 2, 'YYYY-MM-DD') || '-latin-night',
    'לילה לאטיני בהסירנה',
    'סלסה, באצ׳אטה ורגטון עד הבוקר.',
    (select id from v where slug = 'sirena'), (select city_id from v where slug = 'sirena'),
    null,
    (((select d from day0) + 2)::timestamp + interval '22 hours') at time zone 'Asia/Jerusalem',
    null,
    40::numeric, 60::numeric, 18::smallint, 'https://example.com/tickets/8', 'eventer'::public.ticket_provider, false, 'published'::public.event_status
  ),
  (
    'kuli-alma-' || to_char((select d from day0) + 3, 'YYYY-MM-DD') || '-drag-show',
    'מופע דראג בקולי עלמא',
    'מופע דראג מלא נצנצים ואחריו מסיבה.',
    (select id from v where slug = 'kuli-alma'), (select city_id from v where slug = 'kuli-alma'),
    (select id from public.organizers where slug = 'night-owls'),
    (((select d from day0) + 3)::timestamp + interval '22 hours') at time zone 'Asia/Jerusalem',
    null,
    65::numeric, 85::numeric, 21::smallint, 'https://example.com/tickets/9', 'eventer'::public.ticket_provider, false, 'published'::public.event_status
  ),
  (
    'yellow-' || to_char((select d from day0) + 5, 'YYYY-MM-DD') || '-student-party',
    'מסיבת סטודנטים בילו סאבמרין',
    'מסיבת פתיחת סמסטר עם הנחה לסטודנטים.',
    (select id from v where slug = 'yellow'), (select city_id from v where slug = 'yellow'),
    null,
    (((select d from day0) + 5)::timestamp + interval '23 hours') at time zone 'Asia/Jerusalem',
    null,
    30::numeric, 50::numeric, 18::smallint, 'https://example.com/tickets/10', 'tixwise'::public.ticket_provider, false, 'published'::public.event_status
  )
) as t
on conflict (slug) do nothing;

-- event_genres ---------------------------------------------------------------
insert into public.event_genres (event_id, genre_id)
select e.id, g.id
from public.events e
join public.genres g on g.slug = any(
  case
    when e.slug like '%techno%'     then array['techno']
    when e.slug like '%hiphop%'     then array['hiphop']
    when e.slug like '%karaoke%'    then array['karaoke']
    when e.slug like '%mainstream%' then array['mainstream']
    when e.slug like '%latin%'      then array['latin']
    when e.slug like '%drag%'       then array['drag', 'mainstream']
    when e.slug like '%student%'    then array['student', 'mainstream']
    when e.slug like '%indie%'      then array['indie', 'rock']
    when e.slug like '%free-entry%' then array['indie', 'mainstream']
    else array[]::text[]
  end
)
on conflict do nothing;
