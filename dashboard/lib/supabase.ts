// Supabase client for the Edit page. The URL and publishable (anon) key are public by design:
// what anyone can do is decided by the row-level-security rules in supabase/schema.sql
// (only people listed in `editors` can read or add edits). Never put the service-role key here.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabase: SupabaseClient | null = url && key ? createClient(url, key) : null;

export type Edit = {
  id: number; created_at: string; created_by: string; editor_name: string;
  feature: "kiln" | "school"; action: "add" | "move" | "not_present" | "note";
  target_id: string | null; name: string | null; lat: number | null; lon: number | null;
  evidence: string; imagery: string | null; imagery_date: string | null;
  status: "pending" | "applied" | "rejected";
};

export const ACTION_LABEL: Record<Edit["action"], string> = {
  add: "Add missing", move: "Wrong location (new position)", not_present: "Not present / not a real one", note: "Note only",
};
