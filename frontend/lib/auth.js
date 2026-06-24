// lib/auth.js — checks if user is logged in on every protected page

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from './supabase'

export function useAuth() {
  const router = useRouter()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if user is already logged in
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        // No session — redirect to login
        router.push('/login')
      } else {
        setUser(session.user)  // store user details
        setLoading(false)
      }
    })

    // Listen for auth changes (logout etc)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (!session) {
          router.push('/login')
        } else {
          setUser(session.user)
          setLoading(false)
        }
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  return { user, loading }
}

/**
 * getToken — returns the current Supabase JWT access token.
 * Used by apiFetch() to attach Authorization headers to backend requests.
 * Returns null if the user is not signed in (caller should handle redirect).
 */
export async function getToken() {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? null
}