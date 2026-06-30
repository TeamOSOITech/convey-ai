'use client'
// app/case/[titleNumber]/extract/page.js
//
// Smart Extract Tool — general-purpose AI document extraction.
//
// UX Flow:
//   Phase 1 (Setup)    — User selects documents + writes extraction instructions
//   Phase 2 (Running)  — Documents processed one at a time, results stream in live
//   Phase 3 (Results)  — Per-document markdown cards with copy buttons

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '../../../../lib/auth'
import { apiFetch } from '../../../../lib/api'
import ReactMarkdown from 'react-markdown'

// Quick Templates
const TEMPLATES = [
  {
    label: 'Key Dates',
    icon: '📅',
    instructions: `Extract all key dates from this document. For each date found, provide:
- The exact date
- What the date refers to (e.g. completion date, exchange date, offer expiry, mortgage offer expiry, search result date, registration date)
- The exact clause or sentence it appears in

Format as a clear list. If a date type is not present, omit it.`
  },
  {
    label: 'Parties & Roles',
    icon: '👥',
    instructions: `Extract all parties named in this document and their roles. For each party provide:
- Full legal name (exactly as written)
- Their role (e.g. Buyer, Seller, Lender, Solicitor, Guarantor, Landlord, Tenant, Trustee)
- Their address if stated
- Any reference number (e.g. company number, SRA number)

Format as a structured list grouped by role.`
  },
  {
    label: 'Financial Summary',
    icon: '£',
    instructions: `Extract all financial figures and monetary amounts from this document. For each amount provide:
- The exact figure (amount)
- What it represents (e.g. purchase price, deposit, mortgage amount, ground rent, service charge, legal fee, SDLT, redemption figure)
- The clause or context it appears in

Also note any payment due dates, interest rates, or financial conditions. Format as a clear table or list.`
  },
  {
    label: 'Restrictions & Obligations',
    icon: '⚖️',
    instructions: `Extract all restrictions, obligations, covenants, conditions and easements from this document. For each item:
- State the type (e.g. Restrictive Covenant, Positive Covenant, Easement, Condition, Restriction)
- Describe exactly what it requires or prohibits
- Note who is bound by it and who benefits from it
- Include the exact clause reference if present

Format as a structured list.`
  },
  {
    label: 'Property Details',
    icon: '🏠',
    instructions: `Extract all information about the property itself from this document:
- Full property address (as stated)
- Title number
- Tenure (Freehold / Leasehold)
- Description of the property
- Boundaries mentioned
- Any title plan references
- Any planning permissions or conditions noted

Format as a clear structured summary.`
  }
]

const DOC_TYPE_LABELS = {
  OCE: 'Title Register',
  LEASE: 'Lease',
  TR1: 'Transfer',
  CONTRACT: 'Contract',
  TA6: 'Property Information Form (TA6)',
  TA10: 'Fittings & Contents (TA10)',
  EPC: 'Energy Performance Certificate',
  OTHER: 'Other Document'
}

export default function SmartExtractPage() {
  const { titleNumber } = useParams()
  const { user, loading: authLoading } = useAuth()

  const [caseData,    setCaseData]    = useState(null)
  const [pageLoading, setPageLoading] = useState(true)
  const [selectedFilenames, setSelectedFilenames] = useState([])
  const [instructions,   setInstructions]   = useState('')
  const [activeTemplate, setActiveTemplate] = useState(null)
  const [phase,       setPhase]       = useState('setup')
  const [results,     setResults]     = useState([])
  const [extracting,  setExtracting]  = useState(false)
  const [currentFile, setCurrentFile] = useState(null)
  const [copiedId,    setCopiedId]    = useState(null)

  useEffect(() => { fetchCase() }, [titleNumber])

  const fetchCase = async () => {
    try {
      const res  = await apiFetch(`/cases/${titleNumber}`)
      const data = await res.json()
      if (data.success) setCaseData(data)
    } catch (err) {
      console.error('Failed to fetch case:', err)
    } finally {
      setPageLoading(false)
    }
  }

  const toggleDocument = (filename) => {
    setSelectedFilenames(prev =>
      prev.includes(filename) ? prev.filter(f => f !== filename) : [...prev, filename]
    )
  }
  const selectAll = () => setSelectedFilenames(caseData?.documents?.map(d => d.filename) || [])
  const clearAll  = () => setSelectedFilenames([])

  const applyTemplate = (template) => {
    setInstructions(template.instructions)
    setActiveTemplate(template.label)
  }

  const runExtraction = async () => {
    if (selectedFilenames.length === 0 || !instructions.trim()) return

    setExtracting(true)
    setPhase('running')
    setResults([])

    const liveResults = []

    for (let i = 0; i < selectedFilenames.length; i++) {
      const filename = selectedFilenames[i]
      setCurrentFile(filename)

      try {
        const res = await apiFetch('/smart-extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title_number: titleNumber,
            filename,
            instructions: instructions.trim()
          })
        })

        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || `Failed to extract ${filename}`)
        liveResults.push({ filename, result: data.result })
      } catch (err) {
        liveResults.push({ filename, result: null, error: err.message })
      }

      setResults([...liveResults])
    }

    setCurrentFile(null)
    setExtracting(false)
    setPhase('results')
  }

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const copyAll = () => {
    const lines = [`SMART EXTRACT — ${titleNumber}`, '']
    results.forEach(r => {
      lines.push('─'.repeat(60))
      lines.push(`DOCUMENT: ${r.filename}`)
      lines.push('')
      lines.push(r.error ? `[ERROR] ${r.error}` : (r.result || ''))
      lines.push('')
    })
    copyToClipboard(lines.join('\n'), 'all')
  }

  const resetTool = () => {
    setPhase('setup')
    setResults([])
    setCurrentFile(null)
  }

  if (authLoading || pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-400 text-sm">Loading...</p>
      </div>
    )
  }

  const documents = caseData?.documents || []
  const canRun    = selectedFilenames.length > 0 && instructions.trim().length > 0 && !extracting

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Breadcrumb */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center gap-3">
          <a href="/" className="text-sm text-gray-400 hover:text-gray-600">← All Cases</a>
          <span className="text-gray-200">/</span>
          <a href={`/case/${titleNumber}`} className="text-sm text-gray-400 hover:text-gray-600">{titleNumber}</a>
          <span className="text-gray-200">/</span>
          <span className="text-sm font-semibold text-gray-900">Smart Extract</span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 flex gap-6 items-start">

        {/* LEFT: Document selector */}
        <div className="w-72 flex-shrink-0">
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">

            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-800">Select Documents</h2>
              <span className="text-xs text-gray-400">{selectedFilenames.length}/{documents.length}</span>
            </div>

            <div className="px-4 py-2 border-b border-gray-100 flex gap-3">
              <button onClick={selectAll} className="text-xs text-blue-600 hover:underline">Select all</button>
              <span className="text-gray-200">|</span>
              <button onClick={clearAll} className="text-xs text-gray-400 hover:underline">Clear</button>
            </div>

            <div className="divide-y divide-gray-50 max-h-96 overflow-y-auto">
              {documents.length === 0 ? (
                <p className="p-4 text-xs text-gray-400">No documents in this case yet.</p>
              ) : (
                documents.map((doc) => {
                  const isSelected = selectedFilenames.includes(doc.filename)
                  return (
                    <label
                      key={doc.id}
                      className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${
                        isSelected ? 'bg-purple-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleDocument(doc.filename)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-gray-500 mb-0.5">
                          {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                        </p>
                        <p className="text-xs text-gray-700 truncate">{doc.filename}</p>
                      </div>
                    </label>
                  )
                })
              )}
            </div>

            <div className="p-4 border-t border-gray-100">
              <button
                onClick={runExtraction}
                disabled={!canRun}
                className="w-full bg-purple-600 text-white text-sm py-2.5 rounded-lg font-medium hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {extracting
                  ? 'Extracting...'
                  : `Run Extraction (${selectedFilenames.length} doc${selectedFilenames.length !== 1 ? 's' : ''})`
                }
              </button>
              {selectedFilenames.length === 0 && (
                <p className="text-xs text-gray-400 text-center mt-2">Select at least one document</p>
              )}
              {selectedFilenames.length > 0 && !instructions.trim() && (
                <p className="text-xs text-gray-400 text-center mt-2">Add instructions on the right →</p>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: Instructions + Results */}
        <div className="flex-1 min-w-0 space-y-5">

          {/* Instructions panel */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-gray-800">Extraction Instructions</h2>
                <p className="text-xs text-gray-400 mt-0.5">Tell the AI exactly what to find and how to format it</p>
              </div>
              {phase === 'results' && (
                <button
                  onClick={resetTool}
                  className="text-xs text-purple-600 border border-purple-200 bg-purple-50 hover:bg-purple-100 px-3 py-1.5 rounded-lg transition-colors font-medium"
                >
                  ← New Extraction
                </button>
              )}
            </div>

            {/* Quick templates */}
            <div className="px-5 py-3 border-b border-gray-100">
              <p className="text-xs text-gray-500 font-medium mb-2">Quick Templates</p>
              <div className="flex flex-wrap gap-2">
                {TEMPLATES.map(t => (
                  <button
                    key={t.label}
                    onClick={() => applyTemplate(t)}
                    className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
                      activeTemplate === t.label
                        ? 'bg-purple-600 text-white border-purple-600'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-purple-300 hover:text-purple-600'
                    }`}
                  >
                    {t.icon} {t.label}
                  </button>
                ))}
                <button
                  onClick={() => { setInstructions(''); setActiveTemplate(null) }}
                  className="text-xs px-3 py-1.5 rounded-full border font-medium transition-colors bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                >
                  ✏️ Custom
                </button>
              </div>
            </div>

            <div className="px-5 py-4">
              <textarea
                value={instructions}
                onChange={e => { setInstructions(e.target.value); setActiveTemplate(null) }}
                placeholder={`Write your extraction rules here.\n\nExample:\nExtract the following:\n1. Names of all parties and their roles\n2. The property address\n3. The completion date\n4. The purchase price\n\nFormat as a clear numbered list.`}
                rows={8}
                className="w-full text-sm border border-gray-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-purple-500 focus:border-purple-400 outline-none resize-y transition-all text-gray-800 placeholder-gray-400 leading-relaxed"
              />
              <p className="text-xs text-gray-400 mt-1.5 text-right">
                {instructions.length} characters · the more precise, the better the result
              </p>
            </div>
          </div>

          {/* Running indicator */}
          {extracting && (
            <div className="bg-white rounded-xl border border-gray-200 px-5 py-4 flex items-center gap-4">
              <div className="w-8 h-8 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-gray-800">
                  Extracting from <span className="text-purple-700 font-semibold">{currentFile}</span>
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {results.length} of {selectedFilenames.length} documents done
                </p>
              </div>
            </div>
          )}

          {/* Results */}
          {results.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-gray-900">Extraction Results</h2>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {results.length} of {selectedFilenames.length} document{selectedFilenames.length !== 1 ? 's' : ''} processed
                  </p>
                </div>
                {!extracting && (
                  <button
                    onClick={copyAll}
                    className="text-sm text-gray-500 border border-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    {copiedId === 'all' ? '✓ Copied' : 'Copy All'}
                  </button>
                )}
              </div>

              {results.map((r, idx) => (
                <div key={idx} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-5 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${
                        r.error ? 'bg-red-100 text-red-600' : 'bg-purple-100 text-purple-700'
                      }`}>
                        {r.error ? '⚠ Error' : '✓ Extracted'}
                      </span>
                      <p className="text-sm font-medium text-gray-800 truncate">{r.filename}</p>
                    </div>
                    {!r.error && (
                      <button
                        onClick={() => copyToClipboard(r.result, `doc-${idx}`)}
                        className="text-xs text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0 ml-2"
                      >
                        {copiedId === `doc-${idx}` ? '✓ Copied' : 'Copy'}
                      </button>
                    )}
                  </div>
                  <div className="px-5 py-4">
                    {r.error ? (
                      <p className="text-sm text-red-500 italic">{r.error}</p>
                    ) : (
                      <div className="prose prose-sm max-w-none prose-purple text-gray-800 prose-headings:font-semibold prose-headings:text-gray-900">
                        <ReactMarkdown>{r.result}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {extracting && (
                <div className="bg-white rounded-xl border border-dashed border-gray-300 px-5 py-8 flex items-center justify-center gap-3 text-gray-400">
                  <div className="w-5 h-5 border-2 border-gray-200 border-t-gray-400 rounded-full animate-spin" />
                  <p className="text-sm">Processing remaining documents...</p>
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {results.length === 0 && !extracting && phase === 'setup' && (
            <div className="bg-white rounded-xl border border-dashed border-gray-300 py-20 flex flex-col items-center justify-center">
              <div className="text-5xl mb-4">🔍</div>
              <p className="text-gray-600 font-semibold mb-1">No extraction run yet</p>
              <p className="text-sm text-gray-400 text-center max-w-sm">
                Select documents on the left, write your instructions above (or pick a template), then click Run Extraction.
              </p>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}