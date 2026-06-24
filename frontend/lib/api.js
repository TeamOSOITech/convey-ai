// lib/api.js — authenticated fetch wrapper for all backend API calls
//
// WHY: The Railway backend requires a valid Supabase JWT on every request.
// This helper automatically attaches the Authorization: Bearer header so
// no individual page has to manage token retrieval manually.
//
// USAGE:
//   import { apiFetch } from '../../../lib/api'
//   const res = await apiFetch('/cases')
//   const res = await apiFetch('/upload-pdf?title_number=EX123', { method: 'POST', body: formData })

import { getToken } from './auth'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL

/**
 * apiFetch — authenticated wrapper around window.fetch.
 *
 * Automatically:
 *   1. Prepends the backend base URL
 *   2. Attaches the Supabase JWT as Authorization: Bearer <token>
 *   3. Adds ngrok-skip-browser-warning (harmless in production)
 *
 * @param {string} path   - API path, e.g. '/cases' or '/upload-pdf?title_number=EX123'
 * @param {object} options - Standard fetch options (method, body, headers, etc.)
 * @returns {Promise<Response>}
 */
export async function apiFetch(path, options = {}) {
  const token = await getToken()

  const defaultHeaders = {
    'ngrok-skip-browser-warning': 'true',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  }

  // If caller provides headers, merge them (caller headers take precedence)
  // but do NOT set Content-Type for FormData — the browser sets it with the boundary
  const mergedHeaders = {
    ...defaultHeaders,
    ...(options.headers || {}),
  }

  return fetch(`${BACKEND}${path}`, {
    ...options,
    headers: mergedHeaders,
  })
}
