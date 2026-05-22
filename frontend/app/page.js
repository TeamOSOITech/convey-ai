'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '../lib/auth'

export default function Dashboard() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [newTitleNumber, setNewTitleNumber] = useState('')
  const [creating, setCreating] = useState(false)
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  useEffect(() => {
    fetchCases()
  }, [])

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-400">Loading...</p>
      </div>
    )
  }

  const fetchCases = async () => {
    try {
      const res = await fetch('https://convey-ai-production.up.railway.app/cases')
      const data = await res.json()
      setCases(data.cases || [])
    } catch (err) {
      console.error('Failed to fetch cases:', err)
    } finally {
      setLoading(false)
    }
  }

  const createCase = async () => {
    if (!newTitleNumber.trim()) return
    setCreating(true)
    try {
      const res = await fetch(`https://convey-ai-production.up.railway.app/cases?title_number=${newTitleNumber}`, {
        method: 'POST'
      })
      const data = await res.json()
      if (data.success) {
        setNewTitleNumber('')
        fetchCases()
      }
    } catch (err) {
      console.error('Failed to create case:', err)
    } finally {
      setCreating(false)
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Convey AI</h1>
            <p className="text-gray-500 mt-1">UK Property Conveyancing Assistant</p>
          </div>
          <button
            onClick={async () => {
              const { supabase } = await import('../lib/supabase')
              await supabase.auth.signOut()
              router.push('/login')
            }}
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            Sign out
          </button>
        </div>

        {/* Create new case */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">New Case</h2>
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Enter title number e.g. EX332661"
              value={newTitleNumber}
              onChange={(e) => setNewTitleNumber(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && createCase()}
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={createCase}
              disabled={creating}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? 'Creating...' : 'Create Case'}
            </button>
          </div>
        </div>

        {/* Cases list */}
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-800">All Cases</h2>
          </div>
          {loading ? (
            <div className="p-6 text-gray-400 text-sm">Loading cases...</div>
          ) : cases.length === 0 ? (
            <div className="p-6 text-gray-400 text-sm">No cases yet. Create one above.</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {cases.map((c) => (
                <div
                  key={c.id}
                  onClick={() => router.push(`/case/${c.title_number}`)}
                  className="p-6 hover:bg-gray-50 cursor-pointer flex items-center justify-between"
                >
                  <div>
                    <p className="font-medium text-gray-900">{c.title_number}</p>
                    <p className="text-sm text-gray-400 mt-1">
                      Created {new Date(c.created_at).toLocaleDateString('en-GB')}
                    </p>
                  </div>
                  <span className="text-blue-500 text-sm">Open →</span>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </main>
  )
}