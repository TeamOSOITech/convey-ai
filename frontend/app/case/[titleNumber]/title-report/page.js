'use client'
// app/case/[titleNumber]/title-report/page.js
// Title Report Tool — employee selects documents, system extracts:
//   - OCE: the exact search date ("29 Sep 2016 at 10:08:02" format)
//   - All other docs: date + Rights Granted, Rights Reserved, Covenants, Provisions
//   - All legal field content is rendered as markdown for proper structure

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '../../../../lib/auth'
import ReactMarkdown from 'react-markdown'

// Human-readable labels for document types shown in the selection panel
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

export default function TitleReportPage() {
  const { titleNumber } = useParams()
  const { user, loading: authLoading } = useAuth()

  const [caseData, setCaseData] = useState(null)
  const [pageLoading, setPageLoading] = useState(true)

  // Filenames the employee has ticked for inclusion in the report
  const [selectedFilenames, setSelectedFilenames] = useState([])

  // Report generation state
  const [generating, setGenerating] = useState(false)
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)

  // Tracks which field was just copied for visual "Copied!" feedback
  const [copiedField, setCopiedField] = useState(null)

  useEffect(() => { fetchCase() }, [titleNumber])

  const fetchCase = async () => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/cases/${titleNumber}`,
        { headers: { 'ngrok-skip-browser-warning': 'true' } }
      )
      const data = await res.json()
      if (data.success) setCaseData(data)
    } catch (err) {
      console.error('Failed to fetch case:', err)
    } finally {
      setPageLoading(false)
    }
  }

  // Toggle a document in/out of the selected list
  const toggleDocument = (filename) => {
    setSelectedFilenames(prev =>
      prev.includes(filename)
        ? prev.filter(f => f !== filename)
        : [...prev, filename]
    )
  }

  const selectAll = () => {
    setSelectedFilenames(caseData?.documents?.map(d => d.filename) || [])
  }

  const clearAll = () => setSelectedFilenames([])

  // Send selected filenames to backend and retrieve the structured report
// Process documents sequentially to avoid Vercel 100s Timeouts!
  const generateReport = async () => {
    if (selectedFilenames.length === 0) return

    setGenerating(true)
    setError(null)

    // Shell for the live updating report
    const liveReport = {
      title_number: titleNumber,
      total_documents: selectedFilenames.length,
      documents: []
    }
    setReport({ ...liveReport })

    let hasErrors = false;

    // Loop through selected files and fetch them one at a time
    for (let i = 0; i < selectedFilenames.length; i++) {
      const filename = selectedFilenames[i];

      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/generate-title-report?title_number=${titleNumber}`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'ngrok-skip-browser-warning': 'true'
            },
            // Send ONLY ONE file to keep the request fast
            body: JSON.stringify({ selected_filenames: [filename] })
          }
        )

        let data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || `Failed to extract ${filename}`);
        }

        // Successfully extracted! Append it to the live report and update UI
        if (data.documents && data.documents.length > 0) {
          liveReport.documents.push(data.documents[0]);
          setReport({ ...liveReport });
        }

      } catch (err) {
        hasErrors = true;
        // Don't crash the whole screen, just show an error for this specific file
        liveReport.documents.push({
            filename: filename,
            is_oce: false,
            date: "[ERROR]",
            error: err.message,
            rights_granted: "*Failed to extract.*",
            rights_reserved: "*Failed to extract.*",
            covenants: "*Failed to extract.*",
            provisions: "*Failed to extract.*"
        });
        setReport({ ...liveReport });
      }
    }

    setGenerating(false)
    
    if (hasErrors) {
        setError("Report generated, but some documents failed to extract.")
    }
  }

  // Copy text to clipboard with 2s visual feedback
  const copyToClipboard = (text, fieldId) => {
    navigator.clipboard.writeText(text)
    setCopiedField(fieldId)
    setTimeout(() => setCopiedField(null), 2000)
  }

  // Build and copy the entire report as plain text
  const copyFullReport = () => {
    if (!report) return

    const lines = [`TITLE REPORT — ${report.title_number}`, '']

    report.documents.forEach(doc => {
      lines.push('─'.repeat(60))
      lines.push(`Document: ${doc.filename}`)
      lines.push(`Date: ${doc.date}`)

      if (!doc.is_oce) {
        lines.push('')
        lines.push(`RIGHTS GRANTED:\n${doc.rights_granted || '[NOT FOUND]'}`)
        lines.push('')
        lines.push(`RIGHTS RESERVED:\n${doc.rights_reserved || '[NOT FOUND]'}`)
        lines.push('')
        lines.push(`COVENANTS:\n${doc.covenants || '[NOT FOUND]'}`)
        lines.push('')
        lines.push(`PROVISIONS:\n${doc.provisions || '[NOT FOUND]'}`)
      }

      lines.push('')
    })

    copyToClipboard(lines.join('\n'), 'full-report')
  }

  if (authLoading || pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-400 text-sm">Loading...</p>
      </div>
    )
  }

  const documents = caseData?.documents || []

  return (
    <div className="min-h-screen bg-gray-50">

      {/* ── Breadcrumb navigation ───────────────────────────────────── */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <a href="/" className="text-sm text-gray-400 hover:text-gray-600">← All Cases</a>
          <span className="text-gray-200">/</span>
          <a href={`/case/${titleNumber}`} className="text-sm text-gray-400 hover:text-gray-600">
            {titleNumber}
          </a>
          <span className="text-gray-200">/</span>
          <span className="text-sm font-semibold text-gray-900">Title Report</span>
        </div>
      </div>

      {/* ── Two-column layout ───────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6 py-8 flex gap-6 items-start">

        {/* ── LEFT: Document selection ─────────────────────────────── */}
        <div className="w-72 flex-shrink-0">
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">

            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-800">Select Documents</h2>
              <span className="text-xs text-gray-400">
                {selectedFilenames.length}/{documents.length}
              </span>
            </div>

            {/* Select all / clear buttons */}
            <div className="px-4 py-2 border-b border-gray-100 flex gap-3">
              <button onClick={selectAll} className="text-xs text-blue-600 hover:underline">
                Select all
              </button>
              <span className="text-gray-200">|</span>
              <button onClick={clearAll} className="text-xs text-gray-400 hover:underline">
                Clear
              </button>
            </div>

            {/* Document checkboxes */}
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
                        isSelected ? 'bg-indigo-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleDocument(doc.filename)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
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

            {/* Generate button */}
            <div className="p-4 border-t border-gray-100">
              <button
                onClick={generateReport}
                disabled={selectedFilenames.length === 0 || generating}
                className="w-full bg-indigo-600 text-white text-sm py-2.5 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {generating
                  ? 'Extracting...'
                  : `Generate Report (${selectedFilenames.length} doc${selectedFilenames.length !== 1 ? 's' : ''})`
                }
              </button>
              {selectedFilenames.length === 0 && (
                <p className="text-xs text-gray-400 text-center mt-2">
                  Select at least one document
                </p>
              )}
            </div>
          </div>
        </div>

        {/* ── RIGHT: Report output ─────────────────────────────────── */}
        <div className="flex-1 min-w-0">

          {/* Empty state */}
          {!report && !generating && !error && (
            <div className="bg-white rounded-xl border border-dashed border-gray-300 py-20 flex flex-col items-center justify-center">
              <div className="text-4xl mb-4">📋</div>
              <p className="text-gray-500 font-medium mb-1">No report generated yet</p>
              <p className="text-sm text-gray-400">Select documents and click Generate Report</p>
            </div>
          )}

          {/* Loading state */}
          {generating && (
            <div className="bg-white rounded-xl border border-gray-200 py-20 flex flex-col items-center justify-center">
              <div className="animate-pulse text-4xl mb-4">⚙️</div>
              <p className="text-gray-600 font-medium mb-1">Extracting information...</p>
              <p className="text-sm text-gray-400">This may take a moment for multiple documents</p>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-6">
              <p className="text-red-700 font-medium text-sm">{error}</p>
            </div>
          )}

          {/* Report output */}
          {report && (
            <div className="space-y-4">

              {/* Report header */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-gray-900">
                    Title Report — {report.title_number}
                  </h2>
                  <p className="text-sm text-gray-400">
                    {report.total_documents} document{report.total_documents !== 1 ? 's' : ''} processed
                  </p>
                </div>
                <button
                  onClick={copyFullReport}
                  className="text-sm text-gray-500 border border-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  {copiedField === 'full-report' ? '✓ Copied' : 'Copy Full Report'}
                </button>
              </div>

              {/* Per-document sections */}
              {report.documents.map((doc, index) => (
                <div key={index} className="bg-white rounded-xl border border-gray-200 overflow-hidden">

                  {/* Document header */}
                  <div className="px-5 py-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          doc.is_oce
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-indigo-100 text-indigo-700'
                        }`}>
                          {doc.is_oce ? 'Title Register (OCE)' : 'Title Document'}
                        </span>
                        {/* Show error badge if document wasn't found in ChromaDB */}
                        {doc.error && (
                          <span className="text-xs text-red-500">⚠ {doc.error}</span>
                        )}
                      </div>
                      <p className="text-sm font-medium text-gray-800">{doc.filename}</p>
                    </div>

                    {/* Date extracted from document — prominently displayed */}
                    <div className="text-right">
                      <p className="text-xs text-gray-400 mb-0.5">Date</p>
                      <p className="text-sm font-semibold text-gray-800">{doc.date}</p>
                    </div>
                  </div>

                  {/* OCE note — date only, no legal fields */}
                  {doc.is_oce && (
                    <div className="px-5 py-3">
                      <p className="text-xs text-gray-400 italic">
                        Title Register — search date extracted. Rights and covenants are contained in the title deeds listed below.
                      </p>
                    </div>
                  )}

                  {/* Legal fields with markdown rendering — non-OCE documents only */}
                  {!doc.is_oce && (
                    <div className="divide-y divide-gray-100">
                      {[
                        { key: 'rights_granted', label: 'Rights Granted' },
                        { key: 'rights_reserved', label: 'Rights Reserved' },
                        { key: 'covenants', label: 'Covenants' },
                        { key: 'provisions', label: 'Provisions' }
                      ].map(({ key, label }) => {
                        const fieldId = `${index}-${key}`
                        const value = doc[key] || '[NOT FOUND]'
                        const isCopied = copiedField === fieldId
                        const isPlaceholder = value.startsWith('[') || value.startsWith('*Not present')

                        return (
                          <div key={key} className="px-5 py-4">

                            {/* Field label + copy button */}
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                                {label}
                              </h4>
                              <button
                                onClick={() => copyToClipboard(value, fieldId)}
                                className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                              >
                                {isCopied ? '✓ Copied' : 'Copy'}
                              </button>
                            </div>

                            {/* Markdown rendered content */}
                            {isPlaceholder ? (
                              // Show placeholder values dimmed and italic — no markdown needed
                              <p className="text-sm text-gray-400 italic">{value}</p>
                            ) : (
                              // Render LLM markdown output with proper formatting
                              // prose class from Tailwind Typography gives clean text styling
                              <div className="prose prose-sm max-w-none prose-indigo text-gray-800">
                              <ReactMarkdown>{value}</ReactMarkdown>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}