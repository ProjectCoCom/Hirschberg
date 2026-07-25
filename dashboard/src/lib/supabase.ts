/**
 * Frontend JavaScript/TypeScript module 'Supabase'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Supabase'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL || "";
const key = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

export const supabase = createClient(url, key);
