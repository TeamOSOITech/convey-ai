'use client'
// app/case/[titleNumber]/form-filler/page.js
//
// Form Auto-Filler Tool
//
// UX Flow:
//   Left Panel   — Source document selector (case documents from ChromaDB)
//   Middle Panel — Upload your blank TR1 form PDF from PC → displays it live
//   Right Panel  — AI-extracted panel data, editable, copy-paste ready

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '../../../../lib/auth'
import { apiFetch } from '../../../../lib/api'
import { SUPPORTED_FORMS } from './forms'

const DOC_TYPE_LABELS = {
  OCE:      'Title Register',
  LEASE:    'Lease',
  TR1:      'Transfer',
  CONTRACT: 'Contract',
  TA6:      'Property Information Form (TA6)',
  TA10:     'Fittings & Contents (TA10)',
  EPC:      'Energy Performance Certificate',
  OTHER:    'Other Document'
}

// Detect form type from filename — extend as more forms are added
function detectFormType(filename) {
  const lower = filename.toLowerCase()
  if (lower.includes('tr1')) return 'TR1'
  return 'TR1' // default
}

export default function FormFillerPage() {
  const { titleNumber } = useParams()
  const { loading: authLoading } = useAuth()

  const [caseData,    setCaseData]    = useState(null)
  const [pageLoading, setPageLoading] = useState(true)

  // Left panel
  const [selectedFilenames, setSelectedFilenames] = useState([])

  // Middle panel — uploaded form PDF
  const [formFile,    setFormFile]    = useState(null)   // File object
  const [formPdfUrl,  setFormPdfUrl]  = useState(null)   // blob URL for <iframe>
  const [formType,    setFormType]    = useState('TR1')  // detected/selected form type
  const [dragging,    setDragging]    = useState(false)
  const fileInputRef = useRef(null)

  // Right panel — extraction
  const [extracting,   setExtracting]   = useState(false)
  const [extractError, setExtractError] = useState(null)
  const [edited,       setEdited]       = useState({})
  const [hasResults,   setHasResults]   = useState(false)

  // Copy feedback
  const [copiedId, setCopiedId] = useState(null)

  // Panel navigation
  const [activePanel, setActivePanel] = useState(null)
  const panelRefs = useRef({})

  useEffect(() => { fetchCase() }, [titleNumber])

  // Revoke blob URL on unmount to avoid memory leaks
  useEffect(() => {
    return () => { if (formPdfUrl) URL.revokeObjectURL(formPdfUrl) }
  }, [formPdfUrl])

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

  // ── Document selection ──────────────────────────────────────────────────
  const toggleDoc = (filename) =>
    setSelectedFilenames(prev =>
      prev.includes(filename) ? prev.filter(f => f !== filename) : [...prev, filename]
    )
  const selectAll = () => setSelectedFilenames(caseData?.documents?.map(d => d.filename) || [])
  const clearAll  = () => setSelectedFilenames([])

  // ── Form PDF upload ─────────────────────────────────────────────────────
  const handleFormFile = (file) => {
    if (!file || file.type !== 'application/pdf') return
    if (formPdfUrl) URL.revokeObjectURL(formPdfUrl)
    const url = URL.createObjectURL(file)
    setFormFile(file)
    setFormPdfUrl(url)
    setFormType(detectFormType(file.name))
    // Reset results when a new form is loaded
    setEdited({})
    setHasResults(false)
    setExtractError(null)
  }

  const onFileInputChange = (e) => {
    const file = e.target.files?.[0]
    if (file) handleFormFile(file)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFormFile(file)
  }, [formPdfUrl])

  const onDragOver = (e) => { e.preventDefault(); setDragging(true) }
  const onDragLeave = () => setDragging(false)

  // ── Run extraction ──────────────────────────────────────────────────────
  const runExtraction = async () => {
    if (!formFile || selectedFilenames.length === 0) return
    setExtracting(true)
    setExtractError(null)
    setEdited({})
    setHasResults(false)

    try {
      const res = await apiFetch('/form-extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title_number: titleNumber,
          filenames: selectedFilenames,
          form_type: formType
        })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Extraction failed')
      setEdited(data.panels || {})
      setHasResults(true)
    } catch (err) {
      setExtractError(err.message)
    } finally {
      setExtracting(false)
    }
  }

  // ── Copy helpers ────────────────────────────────────────────────────────
  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text || '')
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const copyAll = () => {
    const form = SUPPORTED_FORMS[formType]
    if (!form) return
    const lines = [`${form.name} — ${titleNumber}`, '']
    form.panels.forEach(p => {
      lines.push(`${p.number}. ${p.title}`)
      lines.push(edited[p.id] || '[Not found]')
      lines.push('')
    })
    copyToClipboard(lines.join('\n'), 'all')
  }

  const updatePanel = (panelId, value) =>
    setEdited(prev => ({ ...prev, [panelId]: value }))

  if (authLoading || pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-400 text-sm">Loading...</p>
      </div>
    )
  }

  const documents  = caseData?.documents || []
  const form       = SUPPORTED_FORMS[formType]
  const canExtract = !!formFile && selectedFilenames.length > 0 && !extracting

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* Breadcrumb */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex-shrink-0">
        <div className="max-w-[1800px] mx-auto flex items-center gap-3">
          <a href="/" className="text-sm text-gray-400 hover:text-gray-600">← All Cases</a>
          <span className="text-gray-200">/</span>
          <a href={`/case/${titleNumber}`} className="text-sm text-gray-400 hover:text-gray-600">{titleNumber}</a>
          <span className="text-gray-200">/</span>
          <span className="text-sm font-semibold text-gray-900">Form Auto-Filler</span>
          {formFile && (
            <>
              <span className="text-gray-200">/</span>
              <span className="text-sm text-teal-700 font-medium">{formFile.name}</span>
            </>
          )}
        </div>
      </div>

      {/* Three-pane layout */}
      <div className="flex-1 flex overflow-hidden max-w-[1800px] w-full mx-auto px-4 py-4 gap-3" style={{height: 'calc(100vh - 57px)'}}>

        {/* ══ LEFT: Source document selector ══════════════════════════════ */}
        <div className="w-60 flex-shrink-0 flex flex-col">
          <div className="bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden flex-1">

            <div className="px-4 py-3 border-b border-gray-100">
              <p className="text-sm font-semibold text-gray-800">Source Documents</p>
              <p className="text-xs text-gray-400 mt-0.5">Documents to extract data from</p>
            </div>

            <div className="px-4 py-2 border-b border-gray-100 flex gap-3">
              <button onClick={selectAll} className="text-xs text-blue-600 hover:underline">All</button>
              <span className="text-gray-200">|</span>
              <button onClick={clearAll}  className="text-xs text-gray-400 hover:underline">Clear</button>
              <span className="ml-auto text-xs text-gray-400">{selectedFilenames.length}/{documents.length}</span>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-gray-50">
              {documents.length === 0 ? (
                <p className="p-4 text-xs text-gray-400">No documents in this case.</p>
              ) : documents.map(doc => {
                const isSel = selectedFilenames.includes(doc.filename)
                return (
                  <label
                    key={doc.id}
                    className={`flex items-start gap-2.5 px-4 py-3 cursor-pointer transition-colors ${isSel ? 'bg-teal-50' : 'hover:bg-gray-50'}`}
                  >
                    <input
                      type="checkbox"
                      checked={isSel}
                      onChange={() => toggleDoc(doc.filename)}
                      className="mt-0.5 h-4 w-4 rounded border-gray-300 text-teal-600 focus:ring-teal-500 flex-shrink-0"
                    />
                    <div className="min-w-0">
                      <p className="text-[11px] font-medium text-gray-500">
                        {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                      </p>
                      <p className="text-xs text-gray-700 truncate" title={doc.filename}>{doc.filename}</p>
                    </div>
                  </label>
                )
              })}
            </div>

            <div className="p-3 border-t border-gray-100 space-y-2">
              <button
                onClick={runExtraction}
                disabled={!canExtract}
                className="w-full bg-teal-600 text-white text-sm py-2.5 rounded-lg font-medium hover:bg-teal-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {extracting ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Extracting...
                  </span>
                ) : 'Run Extraction'}
              </button>
              {!formFile && (
                <p className="text-[11px] text-gray-400 text-center">Upload a form in the middle panel first</p>
              )}
              {formFile && selectedFilenames.length === 0 && (
                <p className="text-[11px] text-gray-400 text-center">Select at least one document above</p>
              )}
            </div>
          </div>
        </div>

        {/* ══ MIDDLE: Form upload + PDF viewer ════════════════════════════ */}
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden flex-1">

            {/* Upload header */}
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
              <div>
                <p className="text-sm font-semibold text-gray-800">Form Template</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {formFile ? formFile.name : 'Upload your blank TR1 (or other form) PDF from your computer'}
                </p>
              </div>
              {formFile && (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="text-xs text-teal-600 border border-teal-200 bg-teal-50 hover:bg-teal-100 px-3 py-1.5 rounded-lg transition-colors font-medium"
                >
                  Change PDF
                </button>
              )}
            </div>

            {/* PDF viewer or upload zone */}
            <div className="flex-1 overflow-hidden">
              {formPdfUrl ? (
                <iframe
                  src={formPdfUrl}
                  className="w-full h-full border-0"
                  title="Form PDF"
                />
              ) : (
                <div
                  onDrop={onDrop}
                  onDragOver={onDragOver}
                  onDragLeave={onDragLeave}
                  onClick={() => fileInputRef.current?.click()}
                  className={`h-full flex flex-col items-center justify-center cursor-pointer transition-colors ${
                    dragging
                      ? 'bg-teal-50 border-2 border-teal-400 border-dashed'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="text-6xl mb-4 select-none">📄</div>
                  <p className="text-gray-700 font-semibold mb-1">
                    {dragging ? 'Drop your PDF here' : 'Upload your form PDF'}
                  </p>
                  <p className="text-sm text-gray-400 text-center max-w-xs">
                    Click to browse, or drag and drop your blank TR1 (or other form) PDF here.
                  </p>
                  <p className="text-xs text-gray-300 mt-4">PDF files only</p>
                </div>
              )}
            </div>

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={onFileInputChange}
            />
          </div>
        </div>

        {/* ══ RIGHT: Extracted data ════════════════════════════════════════ */}
        <div className="w-[420px] flex-shrink-0 flex flex-col">
          <div className="bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden flex-1">

            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
              <div>
                <p className="text-sm font-semibold text-gray-800">
                  {form ? `${form.name} — Extracted Data` : 'Extracted Data'}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {hasResults
                    ? 'Copy each field and paste into the form · all editable'
                    : 'Run extraction to populate'}
                </p>
              </div>
              {hasResults && (
                <button
                  onClick={copyAll}
                  className="text-xs text-gray-500 border border-gray-200 px-2.5 py-1.5 rounded-lg hover:bg-gray-50 transition-colors flex-shrink-0 whitespace-nowrap"
                >
                  {copiedId === 'all' ? '✓ Copied' : 'Copy All'}
                </button>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">

              {extractError && (
                <div className="m-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                  <p className="text-sm text-red-600 font-medium">Extraction failed</p>
                  <p className="text-xs text-red-500 mt-1">{extractError}</p>
                </div>
              )}

              {extracting && (
                <div className="flex flex-col items-center justify-center h-full gap-4 py-16">
                  <div className="w-10 h-10 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin" />
                  <div className="text-center">
                    <p className="text-sm font-semibold text-gray-700">Reading documents...</p>
                    <p className="text-xs text-gray-400 mt-1">Extracting {form?.name} panel data</p>
                  </div>
                </div>
              )}

              {!extracting && hasResults && form && (
                <div className="divide-y divide-gray-100">
                  {form.panels.map(p => {
                    const value   = edited[p.id] || ''
                    const isEmpty = !value || value === '[Not found in documents]'
                    return (
                      <div
                        key={p.id}
                        ref={el => { panelRefs.current[p.id] = el }}
                        className="px-4 py-3"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[11px] font-bold text-teal-600 bg-teal-100 w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0">
                              {p.number}
                            </span>
                            <p className="text-xs font-semibold text-gray-800">{p.title}</p>
                          </div>
                          <button
                            onClick={() => copyToClipboard(value, p.id)}
                            disabled={isEmpty}
                            className="text-[11px] text-teal-600 hover:text-teal-800 font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0 ml-2"
                          >
                            {copiedId === p.id ? '✓ Copied' : 'Copy'}
                          </button>
                        </div>
                        <textarea
                          value={isEmpty ? '' : value}
                          onChange={e => updatePanel(p.id, e.target.value)}
                          placeholder={isEmpty ? 'Not found in documents' : p.placeholder}
                          rows={isEmpty ? 2 : 3}
                          className={`w-full text-xs border rounded-lg px-3 py-2 focus:ring-2 focus:ring-teal-500 focus:border-teal-400 outline-none resize-y transition-all leading-relaxed ${
                            isEmpty
                              ? 'border-gray-200 text-gray-400 bg-gray-50 placeholder-gray-300 italic'
                              : 'border-teal-200 text-gray-800 bg-white'
                          }`}
                        />
                      </div>
                    )
                  })}
                </div>
              )}

              {!extracting && !hasResults && !extractError && (
                <div className="flex flex-col items-center justify-center h-full py-16 text-center px-6">
                  <div className="text-4xl mb-3">📋</div>
                  <p className="text-gray-600 font-semibold text-sm mb-1">
                    {formFile ? 'Ready to extract' : 'No form loaded yet'}
                  </p>
                  <p className="text-xs text-gray-400 max-w-xs">
                    {formFile
                      ? 'Select source documents on the left, then click Run Extraction.'
                      : 'Upload your blank form PDF in the middle panel, then select source documents and run extraction.'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}