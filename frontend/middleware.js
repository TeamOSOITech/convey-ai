// middleware.js — protects all pages, redirects to login if not authenticated

import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'

export async function middleware(req) {
  const res = NextResponse.next()

  // Create supabase client for middleware
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    {
      cookies: {
        get: (name) => req.cookies.get(name)?.value,
        set: (name, value, options) => res.cookies.set({ name, value, ...options }),
        remove: (name, options) => res.cookies.set({ name, value: '', ...options })
      }
    }
  )

  // Check if user has valid session
  const { data: { session } } = await supabase.auth.getSession()

  // No session and not on login page → redirect to login
  if (!session && !req.nextUrl.pathname.startsWith('/login')) {
    return NextResponse.redirect(new URL('/login', req.url))
  }

  return res
}

// Protect all pages except static files
export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)']
}