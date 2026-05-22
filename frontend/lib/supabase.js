// lib/supabase.js — Supabase client configured to use cookies for auth
// Cookies are needed so middleware can read the session server-side

import { createBrowserClient } from '@supabase/ssr'

export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
)