'use client'
// app/case/[titleNumber]/form-filler/page.js
//
// Form Auto-Filler Tool — extracts data from case documents to populate legal forms.
//
// UX Flow:
//   Left Panel  — Document selector (same pattern as Smart Extract / Title Report)
//   Middle Panel — Form type selector dropdown → renders the form's panel guide once selected
//   Right Panel  — Editable extracted data fields, one per form panel

import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '../../../../lib/auth'
import { apiFetch } from '../../../../lib/api'
import { SUPPORTED_FORMS, FORM_OPTIONS } from './forms'

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

export default function FormFillerPage() {
  const { titleNumber } = useParams()
  const { loading: authLoading } = useAuth()

  const [caseData,    setCaseData]    = useState(null)
  const [pageLoading, setPageLoading] = useState(true)

  // Left panel: selected documents
  const [selectedFilenames, setSelectedFilenames] = useState([])

  // Middle panel: chosen form type
  const [selectedFormId, setSelectedFormId] = useState(null)

  // Right panel: extraction state + results
  const [extracting,  setExtracting]  = useState(false)
  const [extractError, setExtractError] = useState(null)
  const [panels,      setPanels]      = useState({})      // { panel_1: "...", ... }
  const [edited,      setEdited]      = useState({})      // local edits mirror
  const [hasResults,  setHasResults]  = useState(false)

  // Copy feedback
  const [copiedId, setCopiedId] = useState(null)

  // Active panel highlight (click in middle → scroll right)
  const [activePanel, setActivePanel] = useState(null)
  const panelRefs = useRef({})

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

  // ── Document selection ──────────────────────────────────────────────────
  const toggleDoc = (filename) =>
    setSelectedFilenames(prev =>
      prev.includes(filename) ? prev.filter(f => f !== filename) : [...prev, filename]
    )
  const selectAll = () => setSelectedFilenames(caseData?.documents?.map(d => d.filename) || [])
  const clearAll  = () => setSelectedFilenames([])

  // ── Form selection ──────────────────────────────────────────────────────
  const selectForm = (formId) => {
    setSelectedFormId(formId)
    setPanels({})
    setEdited({})
    setHasResults(false)
    setExtractError(null)
    setActivePanel(null)
  }

  // ── Extract ─────────────────────────────────────────────────────────────
  const runExtraction = async () => {
    if (!selectedFormId || selectedFilenames.length === 0) return
    setExtracting(true)
    setExtractError(null)
    setPanels({})
    setEdited({})
    setHasResults(false)

    try {
      const res = await apiFetch('/form-extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title_number: titleNumber,
          filenames: selectedFilenames,
          form_type: selectedFormId
        })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Extraction failed')
      setPanels(data.panels || {})
      setEdited(data.panels || {})
      setHasResults(true)
    } catch (err) {
      setExtractError(err.message)
    } finally {
      setExtracting(false)
    }
  }

  // ── Panel click → scroll right panel ───────────────────────────────────
  const focusPanel = (panelId) => {
    setActivePanel(panelId)
    panelRefs.current[panelId]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  // ── Edit ────────────────────────────────────────────────────────────────
  const updatePanel = (panelId, value) =>
    setEdited(prev => ({ ...prev, [panelId]: value }))

  // ── Copy ────────────────────────────────────────────────────────────────
  const copyPanel = (panelId) => {
    navigator.clipboard.writeText(edited[panelId] || '')
    setCopiedId(panelId)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const copyAll = () => {
    const form = SUPPORTED_FORMS[selectedFormId]
    if (!form) return
    const lines = [`${form.name} — ${titleNumber}`, '']
    form.panels.forEach(p => {
      lines.push(`${p.number}. ${p.title}`)
      lines.push(edited[p.id] || '[Not found]')
      lines.push('')
    })
    navigator.clipboard.writeText(lines.join('\n'))
    setCopiedId('all')
    setTimeout(() => setCopiedId(null), 2000)
  }

  // ── Guards ──────────────────────────────────────────────────────────────
  if (authLoading || pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-400 text-sm">Loading...</p>
      </div>
    )
  }

  const documents   = caseData?.documents || []
  const form        = selectedFormId ? SUPPORTED_FORMS[selectedFormId] : null
  const canExtract  = !!selectedFormId && selectedFilenames.length > 0 && !extracting

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* ── Breadcrumb ───────────────────────────────────────────────────── */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
        <div className="max-w-[1600px] mx-auto flex items-center gap-3">
          <a href="/" className="text-sm text-gray-400 hover:text-gray-600">← All Cases</a>
          <span className="text-gray-200">/</span>
          <a href={`/case/${titleNumber}`} className="text-sm text-gray-400 hover:text-gray-600">{titleNumber}</a>
          <span className="text-gray-200">/</span>
          <span className="text-sm font-semibold text-gray-900">Form Auto-Filler</span>
        </div>
      </div>

      {/* ── Three-pane layout ────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden max-w-[1600px] w-full mx-auto px-4 py-6 gap-4">

        {/* ══ LEFT PANEL: Document selector ══════════════════════════════ */}
        <div className="w-64 flex-shrink-0 flex flex-col">
          <div className="bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden flex-1">

            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-800">Source Documents</h2>
              <span className="text-xs text-gray-400">{selectedFilenames.length}/{documents.length}</span>
            </div>

            <div className="px-4 py-2 border-b border-gray-100 flex gap-3">
              <button onClick={selectAll} className="text-xs text-blue-600 hover:underline">All</button>
              <span className="text-gray-200">|</span>
              <button onClick={clearAll} className="text-xs text-gray-400 hover:underline">Clear</button>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-gray-50">
              {documents.length === 0 ? (
                <p className="p-4 text-xs text-gray-400">No documents in this case.</p>
              ) : (
                documents.map(doc => {
                  const isSel = selectedFilenames.includes(doc.filename)
                  return (
                    <label
                      key={doc.id}
                      className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${isSel ? 'bg-teal-50' : 'hover:bg-gray-50'}`}
                    >
                      <input
                        type="checkbox"
                        checked={isSel}
                        onChange={() => toggleDoc(doc.filename)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-gray-500 mb-0.5">
                          {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                        </p>
                        <p className="text-xs text-gray-700 truncate" title={doc.filename}>{doc.filename}</p>
                      </div>
                    </label>
                  )
                })
              )}
            </div>

            <div className="p-3 border-t border-gray-100">
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
              {!selectedFormId && <p className="text-xs text-gray-400 text-center mt-1.5">Select a form type first →</p>}
              {selectedFormId && selectedFilenames.length === 0 && <p className="text-xs text-gray-400 text-center mt-1.5">Select at least one document</p>}
            </div>
          </div>
        </div>

        {/* ══ MIDDLE PANEL: Form type selector + soft copy ══════════════ */}
        <div className="w-72 flex-shrink-0 flex flex-col">
          <div className="bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden flex-1">

            {/* Form selector */}
            <div className="px-4 py-3 border-b border-gray-100">
              <p className="text-xs text-gray-500 font-medium mb-2">Form Type</p>
              <div className="space-y-2">
                {FORM_OPTIONS.map(opt => (
                  <button
                    key={opt.id}
                    onClick={() => selectForm(opt.id)}
                    className={`w-full text-left rounded-lg border px-3 py-2.5 transition-all ${
                      selectedFormId === opt.id
                        ? 'bg-teal-50 border-teal-400 ring-1 ring-teal-400'
                        : 'border-gray-200 hover:border-teal-300 hover:bg-teal-50/50'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{opt.icon}</span>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{opt.name}</p>
                        <p className="text-xs text-gray-400 leading-tight">{opt.fullName}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Panel guide (soft copy) — shown once form is selected */}
            {form ? (
              <div className="flex-1 overflow-y-auto">
                <div className="px-4 py-2 border-b border-gray-100">
                  <p className="text-xs text-gray-400">Click a panel to jump to it →</p>
                </div>
                <div className="divide-y divide-gray-50">
                  {form.panels.map(p => (
                    <button
                      key={p.id}
                      onClick={() => focusPanel(p.id)}
                      className={`w-full text-left px-4 py-3 transition-colors ${
                        activePanel === p.id
                          ? 'bg-teal-50 border-l-2 border-teal-500'
                          : 'hover:bg-gray-50 border-l-2 border-transparent'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <span className={`text-xs font-bold w-5 flex-shrink-0 mt-0.5 ${activePanel === p.id ? 'text-teal-600' : 'text-gray-400'}`}>
                          {p.number}
                        </span>
                        <div>
                          <p className={`text-xs font-semibold leading-tight ${activePanel === p.id ? 'text-teal-700' : 'text-gray-700'}`}>
                            {p.title}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5 leading-snug">{p.description}</p>
                          {/* Show status badge if extracted */}
                          {hasResults && (
                            <span className={`mt-1 inline-block text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                              edited[p.id] && edited[p.id] !== '[Not found in documents]'
                                ? 'bg-green-100 text-green-700'
                                : 'bg-gray-100 text-gray-400'
                            }`}>
                              {edited[p.id] && edited[p.id] !== '[Not found in documents]' ? '✓ Extracted' : '— Not found'}
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center px-6 text-gray-400">
                <div className="text-4xl mb-3">📋</div>
                <p className="text-sm font-medium text-gray-600 mb-1">Select a form type above</p>
                <p className="text-xs">The form's panels will appear here as a visual guide.</p>
              </div>
            )}
          </div>
        </div>

        {/* ══ RIGHT PANEL: Extracted data ════════════════════════════════ */}
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden flex-1">

            {/* Header */}
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
              <div>
                <h2 className="text-sm font-semibold text-gray-800">
                  {form ? `${form.name} — Extracted Data` : 'Extracted Data'}
                </h2>
                <p className="text-xs text-gray-400 mt-0.5">
                  {hasResults
                    ? `AI-extracted from ${selectedFilenames.length} document${selectedFilenames.length !== 1 ? 's' : ''} · all fields are editable`
                    : 'Run extraction to populate the fields below'}
                </p>
              </div>
              {hasResults && (
                <button
                  onClick={copyAll}
                  className="text-xs text-gray-500 border border-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors flex-shrink-0"
                >
                  {copiedId === 'all' ? '✓ Copied All' : 'Copy All'}
                </button>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">

              {/* Error */}
              {extractError && (
                <div className="m-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                  <p className="text-sm text-red-600 font-medium">Extraction failed</p>
                  <p className="text-xs text-red-500 mt-1">{extractError}</p>
                </div>
              )}

              {/* Loading */}
              {extracting && (
                <div className="flex flex-col items-center justify-center h-full gap-4 py-20">
                  <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin" />
                  <div className="text-center">
                    <p className="text-sm font-semibold text-gray-700">Reading documents...</p>
                    <p className="text-xs text-gray-400 mt-1">Gemini is extracting {form?.name} panel data</p>
                  </div>
                </div>
              )}

              {/* Panel fields — shown after extraction */}
              {!extracting && hasResults && form && (
                <div className="divide-y divide-gray-100">
                  {form.panels.map(p => {
                    const value = edited[p.id] || ''
                    const isEmpty = !value || value === '[Not found in documents]'
                    return (
                      <div
                        key={p.id}
                        ref={el => { panelRefs.current[p.id] = el }}
                        className={`px-5 py-4 transition-colors ${activePanel === p.id ? 'bg-teal-50/40' : ''}`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-teal-600 bg-teal-100 w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0">
                              {p.number}
                            </span>
                            <p className="text-sm font-semibold text-gray-800">{p.title}</p>
                          </div>
                          <button
                            onClick={() => copyPanel(p.id)}
                            disabled={isEmpty}
                            className="text-xs text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0 disabled:opacity-30"
                          >
                            {copiedId === p.id ? '✓ Copied' : 'Copy'}
                          </button>
                        </div>
                        <textarea
                          value={isEmpty ? '' : value}
                          onChange={e => updatePanel(p.id, e.target.value)}
                          placeholder={isEmpty ? `[Not found in documents] — ${p.placeholder}` : p.placeholder}
                          rows={3}
                          className={`w-full text-sm border rounded-lg px-3 py-2 focus:ring-2 focus:ring-teal-500 focus:border-teal-400 outline-none resize-y transition-all leading-relaxed ${
                            isEmpty
                              ? 'border-gray-200 text-gray-400 bg-gray-50 placeholder-gray-300'
                              : 'border-teal-200 text-gray-800 bg-white'
                          }`}
                        />
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Empty state */}
              {!extracting && !hasResults && !extractError && (
                <div className="flex flex-col items-center justify-center h-full py-24 text-center px-8">
                  <div className="text-5xl mb-4">📝</div>
                  <p className="text-gray-600 font-semibold mb-1">
                    {form ? `Ready to extract ${form.name} data` : 'Select a form type to begin'}
                  </p>
                  <p className="text-sm text-gray-400 max-w-sm">
                    {form
                      ? 'Select source documents on the left, then click Run Extraction.'
                      : 'Choose a form format from the middle panel, then select your source documents.'}
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