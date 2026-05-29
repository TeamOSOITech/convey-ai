'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '../lib/auth'

export default function Dashboard() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  
  // Form State
  const [newTitleNumber, setNewTitleNumber] = useState('')
  const [zipFile, setZipFile] = useState(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  const fetchCases = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/cases`, {
        headers: {
          'ngrok-skip-browser-warning': 'true'
        }
      })
      const data = await res.json()
      setCases(data.cases || [])
    } catch (err) {
      console.error('Failed to fetch cases:', err)
    } finally {
      setLoading(false)
    }
  }
  
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

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file && (file.type === 'application/zip' || file.name.endsWith('.zip'))) {
      setZipFile(file);
      setError('');
    } else if (file) {
      setError('Please select a valid .zip file');
      setZipFile(null);
    }
  };

  const createCase = async () => {
    if (!newTitleNumber.trim()) {
      setError('Title number is required');
      return;
    }
    
    setCreating(true)
    setError('')
    
    const formattedTitle = newTitleNumber.trim().toUpperCase()

    try {
      if (zipFile) {
        // Path 1: User uploaded a ZIP - route to the heavy processor
        const formData = new FormData()
        formData.append('title_number', formattedTitle)
        formData.append('file', zipFile)

        const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/upload-zip`, {
          method: 'POST',
          body: formData,
          headers: {
            'ngrok-skip-browser-warning': 'true'
            // NO Content-Type header here - browser handles the multipart boundary
          }
        })
        
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || data.error || 'Failed to process ZIP pack')
        
      } else {
        // Path 2: No ZIP uploaded - just create an empty case
        const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/cases?title_number=${formattedTitle}`, {
          method: 'POST',
          headers: {
            'ngrok-skip-browser-warning': 'true'
          }
        })
        
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Failed to create case')
      }

      // On Success: Clear form, refresh the list, or optionally route straight to the case
      setNewTitleNumber('')
      setZipFile(null)
      fetchCases()
      
      // Uncomment this if you want to immediately open the case after creating/uploading it:
      // router.push(`/case/${formattedTitle}`)

    } catch (err) {
      console.error('Failed to create case:', err)
      setError(err.message || 'An error occurred')
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

        {/* Create new case Widget */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">New Case</h2>
          
          <div className="space-y-4">
            {/* Title Number Input */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Title Number <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                placeholder="e.g. EX332661"
                value={newTitleNumber}
                onChange={(e) => setNewTitleNumber(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createCase()}
                className="w-full text-gray-900 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Optional ZIP Upload Dropzone */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contract Pack (Optional .zip)
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:bg-gray-50 transition cursor-pointer relative">
                <input
                  type="file"
                  accept=".zip,application/zip"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <div className="space-y-1">
                  <svg
                    className="mx-auto h-8 w-8 text-gray-400"
                    stroke="currentColor"
                    fill="none"
                    viewBox="0 0 48 48"
                  >
                    <path
                      d="M24 8v24m0-24L16 16m8-8l8 8m-16 24h16"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <div className="text-sm text-gray-600">
                    {zipFile ? (
                      <span className="font-semibold text-blue-600">{zipFile.name}</span>
                    ) : (
                      <span>Click or drag a zip file here</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="text-sm text-red-600 font-medium bg-red-50 p-2 rounded">
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              onClick={createCase}
              disabled={creating}
              className="w-full bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {creating ? 'Processing Case...' : 'Create Case'}
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
                  className="p-6 hover:bg-gray-50 cursor-pointer flex items-center justify-between transition-colors"
                >
                  <div>
                    <p className="font-medium text-gray-900">{c.title_number}</p>
                    <p className="text-sm text-gray-400 mt-1">
                      Created {new Date(c.created_at).toLocaleDateString('en-GB')}
                    </p>
                  </div>
                  <span className="text-blue-500 text-sm font-medium group-hover:underline">Open →</span>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </main>
  )
}