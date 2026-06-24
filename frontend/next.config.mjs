/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [
      {
        // Apply to every route
        source: '/(.*)',
        headers: [
          // Prevent browsers from MIME-sniffing a response away from the declared content-type
          { key: 'X-Content-Type-Options', value: 'nosniff' },

          // Prevents this site from being embedded in an iframe on another site (clickjacking)
          { key: 'X-Frame-Options', value: 'DENY' },

          // Force HTTPS for 2 years, including subdomains
          { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },

          // Stop the browser sending the full referrer URL to third-party sites
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },

          // Disable FLoC / interest-cohort tracking
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },

          // Content Security Policy — Report-Only mode first so we can validate
          // before switching to enforced mode (change to Content-Security-Policy when ready).
          // Allows: our own Vercel origin, Supabase auth, Railway backend, Google Fonts.
          {
            key: 'Content-Security-Policy-Report-Only',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",   // unsafe-eval needed for Next.js dev mode
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob:",
              "connect-src 'self' https://*.supabase.co https://convey-ai-production-be43.up.railway.app",
              "frame-src 'self' https://convey-ai-production-be43.up.railway.app",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join('; '),
          },
        ],
      },
    ]
  },
}

export default nextConfig
