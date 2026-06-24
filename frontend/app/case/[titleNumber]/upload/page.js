'use client'
import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '../../../../lib/auth'
import { apiFetch } from '../../../../lib/api'

// All document types used in UK conveyancing
const DOC_TYPES = ['LEASE', 'OCE', 'TA6', 'TA7', 'TA10', 'TR1', 'TA13' , 'EPC', 'CONTRACT', 'OTHER']

export default function UploadPage() {
  const { titleNumber } = useParams()
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()  // auth guard — redirects to /login if not signed in

  const [file, setFile] = useState(null)
  const [docType, setDocType] = useState('TA6')
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await apiFetch(
        `/upload-pdf?title_number=${encodeURIComponent(titleNumber)}&doc_type=${encodeURIComponent(docType)}`,
        { method: 'POST', body: formData }
      )
      const data = await res.json()

      if (data.success) {
        setResult(data)
      } else {
        setError(data.error || 'Upload failed')
      }
    } catch (err) {
      setError('Something went wrong. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  // Show loading spinner while auth is being checked
  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-400 text-sm">Loading...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-lg mx-auto">

        {/* Header with back link */}
        <div className="mb-6">
          <a href={`/case/${titleNumber}`} className="text-blue-500 text-sm">← Back to {titleNumber}</a>
          <h1 className="text-2xl font-bold text-gray-900 mt-2">Upload Document</h1>
          <p className="text-gray-400 text-sm mt-1">Case: {titleNumber}</p>
        </div>

        {/* Upload form card */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">

          {/* Dropdown to select what type of document this is */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Document Type
            </label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {/* Renders one option per doc type */}
              {DOC_TYPES.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          {/* File input — only accepts PDFs */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              PDF File
            </label>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files[0])}  // stores selected file in state
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
            />
            {/* Shows filename once selected */}
            {file && (
              <p className="text-xs text-gray-400 mt-1">{file.name}</p>
            )}
          </div>

          {/* Upload button — disabled until file is selected */}
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {uploading ? 'Processing... this may take a minute' : 'Upload & Process'}
          </button>
        </div>

        {/* Success message shown after upload */}
        {result && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-xl p-4">
            <p className="text-green-700 font-medium text-sm">Upload successful!</p>
            <p className="text-green-600 text-xs mt-1">{result.pages} pages processed · {result.total_chunks} chunks stored</p>
            <button
              onClick={() => router.push(`/case/${titleNumber}`)}
              className="mt-3 bg-green-600 text-white px-4 py-1.5 rounded-lg text-xs font-medium hover:bg-green-700"
            >
              Back to Case
            </button>
          </div>
        )}

        {/* Error message shown if upload fails */}
        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-xl p-4">
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}

      </div>
    </div>
  )
}