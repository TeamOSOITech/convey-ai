'use client'
import { useEffect, useState } from 'react'
import { useAuth } from '../lib/auth'

export default function Home() {
  const [status, setStatus] = useState('checking...')
  const { user, loading: authLoading } = useAuth()

  useEffect(() => {
    fetch('https://convey-ai-production.up.railway.app/health')
      .then(res => res.json())
      .then(data => setStatus(data.status))
      .catch(() => setStatus('cannot reach backend'))
  }, [])
  
  if (authLoading) {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-gray-400">Loading...</p>
    </div>
  )
}

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-semibold mb-4">Convey AI</h1>
        <p className="text-gray-500">Backend status: <span className="text-green-500 font-medium">{status}</span></p>
      </div>
    </main>
  )
}