import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Anonymous, cookie-free client for public (ISR) pages. Never uses auth,
 * so server components stay statically renderable and cacheable.
 * Returns null when Supabase env vars are absent (e.g. CI build) so pages
 * can render their empty-state fallback instead of crashing.
 */
let cached: SupabaseClient | null | undefined;

export function supabasePublic(): SupabaseClient | null {
  if (cached !== undefined) return cached;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  cached = url && key ? createClient(url, key, { auth: { persistSession: false } }) : null;
  return cached;
}
