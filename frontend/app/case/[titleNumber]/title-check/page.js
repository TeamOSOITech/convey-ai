'use client'
// app/case/[titleNumber]/title-check/page.js
//
// Title Check Tool — AI-assisted form review and enquiry drafting
//
// UX Flow:
//   Phase 1 (Select)    — User picks a TA6/TA10/TA13 from their uploaded documents
//   Phase 2 (Running)   — Backend pipeline: classify → Gemini extract → rules engine → draft
//   Phase 3 (Review)    — Human Review Board: Approve / Edit / Discard each finding
//   Phase 4 (Generate)  — All approved/edited findings compiled into a final report text

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '../../../../lib/auth'
import { apiFetch } from '../../../../lib/api'
import ReactMarkdown from 'react-markdown'

// Document types this tool supports — shown as hints in the selection panel
const SUPPORTED_FORMS = ["TA6", "TA10", "TA13"]

export default function TitleCheckPage() {
  const { titleNumber } = useParams()
  const { user, loading: authLoading } = useAuth()

  // ── State ──────────────────────────────────────────────────────────────────
  const [caseData,     setCaseData]     = useState(null)
  const [pageLoading,  setPageLoading]  = useState(true)

  // Which document the user has selected from the left panel
  const [selectedDoc,  setSelectedDoc]  = useState(null)

  // Tracks which PDF page to jump to when an evidence link is clicked
  const [pdfPage,      setPdfPage]      = useState(null)

  // Pipeline state
  const [phase,        setPhase]        = useState('select')  // 'select' | 'running' | 'review' | 'generate'
  const [runError,     setRunError]     = useState(null)
  const [evaluationMode, setEvaluationMode] = useState(null)  // 'vision' | 'text-fallback'

  // Findings returned by the backend — each finding has: enquiry_code, topic, reason, draft, status
  // The user can change status to 'approved' | 'edited' | 'discarded'
  // editedDraft stores the modified text for 'edited' findings
  const [findings,     setFindings]     = useState([])
  const [editedDrafts, setEditedDrafts] = useState({})  // { index: "draft text" }

  // Final compiled report
  const [finalReport,  setFinalReport]  = useState(null)

  // Manual enquiry addition state
  const [manualCode, setManualCode] = useState('')
  const [addingManual, setAddingManual] = useState(false)
  const [manualError, setManualError] = useState(null)

  // ── Data Fetch ─────────────────────────────────────────────────────────────
  useEffect(() => { fetchCase() }, [titleNumber])

  const fetchCase = async () => {
    try {
      const res = await apiFetch(`/cases/${titleNumber}`)
      const data = await res.json()
      if (data.success) setCaseData(data)
    } catch (err) {
      console.error('Failed to fetch case:', err)
    } finally {
      setPageLoading(false)
    }
  }

  const addManualEnquiry = async () => {
    if (!manualCode.trim()) return
    setAddingManual(true)
    setManualError(null)
    
    try {
      const res = await apiFetch(`/formats/${encodeURIComponent(manualCode.trim())}`)
      const data = await res.json()
      
      if (!res.ok) {
        throw new Error(data.detail || 'Format not found')
      }
      
      const newFinding = {
        enquiry_code: data.code,
        topic: data.topic,
        reason: "Manually added by user.",
        draft: data.draft,
        status: 'pending'
      }
      
      setFindings(prev => [...prev, newFinding])
      setManualCode('')
    } catch (err) {
      setManualError(err.message)
    } finally {
      setAddingManual(false)
    }
  }

  // ── Pipeline Trigger ───────────────────────────────────────────────────────
  // Called when the user clicks "Run Title Check" after selecting a document.
  // Sends the filename to the backend and waits for structured findings.
  const runTitleCheck = async () => {
    if (!selectedDoc) return

    setPhase('running')
    setRunError(null)
    setFindings([])
    setEditedDrafts({})
    setFinalReport(null)

    try {
      const res = await apiFetch('/title-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title_number: titleNumber,
          filename: selectedDoc.filename
        })
      })
      const data = await res.json()

      // Backend returns {error: "..."} for classification failures
      if (data.error || data.detail) {
        setRunError(data.error || data.detail)
        setPhase('select')
        return
      }

      // Initialise each finding as 'pending' — user must action all of them
      setFindings(data.findings || [])
      setEvaluationMode(data.evaluation_mode || null)
      setPhase('review')

    } catch (err) {
      setRunError('Connection error. Please try again.')
      setPhase('select')
    }
  }

  // ── Review Board Actions ───────────────────────────────────────────────────
  const setFindingStatus = (index, status) => {
    setFindings(prev =>
      prev.map((f, i) => i === index ? { ...f, status } : f)
    )
  }

  const updateEditedDraft = (index, text) => {
    setEditedDrafts(prev => ({ ...prev, [index]: text }))
    // Auto-mark as 'edited' whenever the user types in the draft box
    setFindingStatus(index, 'edited')
  }

  // Check if all findings have been actioned before allowing generation
  const allActioned = findings.every(f =>
    f.status === 'approved' || f.status === 'edited' || f.status === 'discarded'
  )

  const pendingCount   = findings.filter(f => f.status === 'pending').length
  const approvedCount  = findings.filter(f => f.status === 'approved' || f.status === 'edited').length
  const discardedCount = findings.filter(f => f.status === 'discarded').length

  // ── Final Report Generation ────────────────────────────────────────────────
  // Compiles all approved/edited findings into one text block
  const generateReport = () => {
    const approved = findings
      .map((f, i) => ({ ...f, draft: f.status === 'edited' ? (editedDrafts[i] || f.draft) : f.draft }))
      .filter(f => f.status === 'approved' || f.status === 'edited')

    if (approved.length === 0) {
      setFinalReport('No enquiries were approved. Nothing to generate.')
      setPhase('generate')
      return
    }

    const lines = approved.map((f, i) =>
      `**Enquiry ${i + 1} [${f.enquiry_code}] — ${f.topic}**\n\n${f.draft}`
    )

    setFinalReport(lines.join('\n\n---\n\n'))
    setPhase('generate')
  }

  const copyReport = () => {
    navigator.clipboard.writeText(finalReport || '')
  }

  // ── Filter documents to show only supported form types ────────────────────
  const supportedDocs = caseData?.documents?.filter(doc =>
    SUPPORTED_FORMS.some(form =>
      doc.doc_type?.toUpperCase().includes(form) ||
      doc.filename?.toUpperCase().includes(form)
    )
  ) || []

  // All docs shown in panel — supported ones highlighted, others dimmed
  const allDocs = caseData?.documents || []

  // ── Loading / Auth guards ─────────────────────────────────────────────────
  if (authLoading || pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-400 text-sm">Loading...</p>
      </div>
    )
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">

      {/* ── LEFT PANEL — Document Selector ──────────────────────────────── */}
      <div className="w-72 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">

        {/* Header */}
        <div className="p-4 border-b border-gray-100">
          <a href={`/case/${titleNumber}`} className="text-blue-500 text-sm hover:underline">
            ← Back to Case
          </a>
          <h1 className="font-bold text-gray-900 mt-2 text-base">Title Check</h1>
          <p className="text-xs text-gray-400 mt-0.5">{titleNumber}</p>
        </div>

        {/* Instructions */}
        <div className="px-4 py-3 bg-orange-50 border-b border-orange-100">
          <p className="text-xs text-orange-700 font-medium">Supported forms</p>
          <p className="text-xs text-orange-600 mt-0.5">TA6 · TA10 · TA13</p>
          <p className="text-xs text-gray-500 mt-1">
            Select a form below, then click "Run Title Check".
          </p>
        </div>

        {/* Document List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {allDocs.length === 0 ? (
            <p className="text-xs text-gray-400 p-2">No documents uploaded yet.</p>
          ) : (
            allDocs.map((doc) => {
              const isSupported = SUPPORTED_FORMS.some(form =>
                doc.doc_type?.toUpperCase().includes(form) ||
                doc.filename?.toUpperCase().includes(form)
              )
              const isSelected = selectedDoc?.id === doc.id

              return (
                <div
                  key={doc.id}
                  onClick={() => {
                    if (isSupported) {
                      setSelectedDoc(doc)
                      setPdfPage(null)
                      // Reset pipeline if user switches document mid-review
                      if (phase !== 'select') {
                        setPhase('select')
                        setFindings([])
                        setFinalReport(null)
                        setRunError(null)
                      }
                    }
                  }}
                  className={`
                    p-3 rounded-lg border transition-all
                    ${isSupported ? 'cursor-pointer' : 'cursor-not-allowed opacity-40'}
                    ${isSelected
                      ? 'bg-orange-50 border-orange-300'
                      : isSupported
                        ? 'hover:bg-gray-50 border-transparent'
                        : 'border-transparent'
                    }
                  `}
                >
                  {/* Doc type badge */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                      isSupported ? 'bg-orange-100 text-orange-700' : 'bg-gray-100 text-gray-400'
                    }`}>
                      {doc.doc_type || 'OTHER'}
                    </span>
                    {!isSupported && (
                      <span className="text-xs text-gray-300">not supported</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-700 truncate">{doc.filename}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(doc.uploaded_at).toLocaleDateString('en-GB')}
                  </p>
                </div>
              )
            })
          )}
        </div>

        {/* Run Button */}
        <div className="p-3 border-t border-gray-100">
          <button
            onClick={runTitleCheck}
            disabled={!selectedDoc || phase === 'running'}
            className="w-full bg-orange-600 hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium py-2.5 rounded-lg transition-colors"
          >
            {phase === 'running' ? '⏳ Running Check...' : '▶ Run Title Check'}
          </button>
          {runError && (
            <p className="mt-2 text-xs text-red-500 text-center">{runError}</p>
          )}
        </div>
      </div>

      {/* ── MIDDLE PANEL — PDF Viewer ────────────────────────────────────── */}
      <div className="flex-1 flex flex-col border-r border-gray-200 bg-white">

        {/* Viewer header */}
        <div className="p-3 border-b border-gray-100 flex items-center justify-between">
          <p className="text-sm text-gray-600 truncate">
            {selectedDoc
              ? `${selectedDoc.doc_type} — ${selectedDoc.filename}`
              : 'No document selected'
            }
          </p>
          {pdfPage && (
            <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
              Page {pdfPage}
            </span>
          )}
        </div>

        {/* iframe PDF viewer — #page=N fragment applied when evidence link is clicked */}
        <div className="flex-1 overflow-hidden">
          {selectedDoc?.file_url ? (
            <iframe
              key={selectedDoc.file_url + (pdfPage ?? '')}
              src={pdfPage ? `${selectedDoc.file_url}#page=${pdfPage}` : selectedDoc.file_url}
              className="w-full h-full border-0"
              title={selectedDoc.filename}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <div className="text-4xl mb-3">✅</div>
              <p className="text-gray-400 text-sm">Select a TA6, TA10, or TA13 from the left panel to begin.</p>
            </div>
          )}
        </div>
      </div>

      {/* ── RIGHT PANEL — Review Board ───────────────────────────────────── */}
      <div className="w-[460px] flex flex-col bg-white flex-shrink-0 border-l border-gray-200">

        {/* Panel Header */}
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <p className="font-semibold text-gray-900 text-sm">Review Board</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {phase === 'select'   && 'Select a document and run the check.'}
              {phase === 'running'  && 'AI is reading the form...'}
              {phase === 'review'   && (
            <span className="flex items-center gap-2">
              <span>{findings.length} issue{findings.length !== 1 ? 's' : ''} found · {pendingCount} pending</span>
              {evaluationMode === 'vision' && (
                <span className="text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full font-medium">👁 Vision</span>
              )}
              {evaluationMode === 'text-fallback' && (
                <span className="text-[10px] bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded-full font-medium">⚠ Text fallback</span>
              )}
            </span>
          )}
              {phase === 'generate' && 'Final report ready.'}
            </p>
          </div>

          {/* Status counters — shown during review */}
          {phase === 'review' && (
            <div className="flex items-center gap-2 text-xs">
              <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                {approvedCount} approved
              </span>
              <span className="bg-red-100 text-red-500 px-2 py-0.5 rounded-full font-medium">
                {discardedCount} discarded
              </span>
            </div>
          )}
        </div>

        {/* ── Phase: Running ──────────────────────────────────────────────── */}
        {phase === 'running' && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-8">
            <div className="w-10 h-10 border-4 border-orange-200 border-t-orange-600 rounded-full animate-spin" />
            <p className="text-sm text-gray-600 font-medium">Reading form checkboxes...</p>
            <p className="text-xs text-gray-400">
              Gemini is extracting form fields, then the Rules Engine will map them to enquiry codes.
            </p>
          </div>
        )}

        {/* ── Phase: Review Board ─────────────────────────────────────────── */}
        {phase === 'review' && (
          <div className="flex-1 flex flex-col overflow-hidden">

            {/* Findings list */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
              {findings.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                  <div className="text-5xl">🎉</div>
                  <p className="text-gray-700 font-semibold text-sm">No issues found by AI!</p>
                  <p className="text-xs text-gray-400">
                    You can generate a clean report, or manually add enquiries below.
                  </p>
                </div>
              ) : (
                findings.map((finding, index) => (
                  <FindingCard
                    key={index}
                    index={index}
                    finding={finding}
                    editedDraft={editedDrafts[index] ?? finding.draft}
                    onApprove={() => setFindingStatus(index, 'approved')}
                    onDiscard={() => setFindingStatus(index, 'discarded')}
                    onEditChange={(text) => updateEditedDraft(index, text)}
                    onJumpToPage={(page) => setPdfPage(page)}
                  />
                ))
              )}
            </div>

            {/* Manual Enquiry Addition + Generate button */}
            <div className="p-4 border-t border-gray-100 bg-white">
              
              <div className="mb-4">
                 <div className="flex gap-2">
                    <input 
                      type="text" 
                      placeholder="Enquiry Code (e.g. A1)" 
                      value={manualCode}
                      onChange={e => setManualCode(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && addManualEnquiry()}
                      className="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                    />
                    <button 
                      onClick={addManualEnquiry}
                      disabled={addingManual || !manualCode.trim()}
                      className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-sm font-medium px-4 rounded-lg transition-colors disabled:opacity-50"
                    >
                      {addingManual ? 'Adding...' : 'Add Enquiry'}
                    </button>
                 </div>
                 {manualError && <p className="text-xs text-red-500 mt-1.5">{manualError}</p>}
              </div>

              {!allActioned && findings.length > 0 && (
                <p className="text-xs text-amber-600 text-center mb-2">
                  ⚠️ Please approve, edit, or discard all {pendingCount} remaining finding{pendingCount !== 1 ? 's' : ''} before generating.
                </p>
              )}
              <button
                onClick={generateReport}
                disabled={!allActioned && findings.length > 0}
                className="w-full bg-gray-900 hover:bg-black disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium py-2.5 rounded-lg transition-colors"
              >
                Generate Enquiry Report ({approvedCount} enquir{approvedCount !== 1 ? 'ies' : 'y'})
              </button>
            </div>
          </div>
        )}

        {/* ── Phase: Final Report ─────────────────────────────────────────── */}
        {phase === 'generate' && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto p-4">
              <div className="prose prose-sm max-w-none text-gray-800 text-sm whitespace-pre-wrap border border-gray-200 rounded-lg p-4 bg-gray-50">
                <ReactMarkdown>{finalReport}</ReactMarkdown>
              </div>
            </div>
            <div className="p-4 border-t border-gray-100 flex gap-2">
              <button
                onClick={copyReport}
                className="flex-1 border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-medium py-2 rounded-lg transition-colors"
              >
                Copy Text
              </button>
              <button
                onClick={() => setPhase('review')}
                className="flex-1 bg-orange-600 hover:bg-orange-700 text-white text-sm font-medium py-2 rounded-lg transition-colors"
              >
                ← Back to Review
              </button>
            </div>
          </div>
        )}

        {/* ── Phase: Select (idle) ────────────────────────────────────────── */}
        {phase === 'select' && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-8">
            <div className="text-4xl">📋</div>
            <p className="text-sm text-gray-500">
              Select a <span className="font-semibold text-gray-700">TA6, TA10, or TA13</span> from the left panel, then click <span className="font-semibold text-gray-700">Run Title Check</span>.
            </p>
            <p className="text-xs text-gray-400">
              The AI will read the form checkboxes, apply your firm's checklist rules, and draft any required enquiries for you to review.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}


// ── FindingCard Component ──────────────────────────────────────────────────
// Renders one triggered finding in the Review Board.
// Each card has: reason (why triggered) · draft text · three action buttons.
// The user must take an action on every card before report generation is enabled.

function FindingCard({ index, finding, editedDraft, onApprove, onDiscard, onEditChange, onJumpToPage }) {
  // Local state to toggle between "view draft" and "edit draft" mode
  const [editing, setEditing] = useState(false)

  const statusColors = {
    pending:   'border-gray-200 bg-white',
    approved:  'border-green-300 bg-green-50',
    edited:    'border-blue-300 bg-blue-50',
    discarded: 'border-red-200 bg-red-50 opacity-60'
  }

  const statusBadge = {
    pending:   null,
    approved:  <span className="text-[10px] bg-green-600 text-white px-2 py-0.5 rounded-full font-medium">Approved</span>,
    edited:    <span className="text-[10px] bg-blue-600 text-white px-2 py-0.5 rounded-full font-medium">Edited</span>,
    discarded: <span className="text-[10px] bg-red-400 text-white px-2 py-0.5 rounded-full font-medium">Discarded</span>
  }

  return (
    <div className={`rounded-xl border-2 p-4 transition-all ${statusColors[finding.status]}`}>

      {/* Card header — code badge + topic + status badge */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs bg-orange-100 text-orange-800 px-2 py-0.5 rounded-full font-bold font-mono">
            {finding.enquiry_code}
          </span>
          <p className="text-xs font-semibold text-gray-800 leading-tight">{finding.topic}</p>
        </div>
        {statusBadge[finding.status]}
      </div>

      {/* Reason + Evidence — why this rule was triggered */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 mb-3">
        <p className="text-xs text-amber-800 font-medium mb-0.5">📌 Why triggered:</p>
        <p className="text-xs text-amber-700">{finding.reason}</p>
        {finding.evidence && (
          <>
            <p className="text-xs text-amber-800 font-medium mt-2 mb-0.5">🔍 Evidence in document:</p>
            <p className="text-xs text-amber-600 italic">"{finding.evidence}"</p>
          </>
        )}
      </div>

      {/* Draft text — view or edit mode */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs font-medium text-gray-600">Draft Enquiry</p>
          {finding.status !== 'discarded' && (
            <button
              onClick={() => setEditing(e => !e)}
              className="text-xs text-blue-500 hover:text-blue-700"
            >
              {editing ? 'Done editing' : '✏️ Edit'}
            </button>
          )}
        </div>
        {editing ? (
          // Editable textarea — typing auto-marks as 'edited'
          <textarea
            value={editedDraft}
            onChange={(e) => onEditChange(e.target.value)}
            rows={6}
            className="w-full text-xs text-gray-700 border border-blue-300 rounded-lg p-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        ) : (
          // Read-only view
          <div className="text-xs text-gray-700 bg-gray-50 border border-gray-200 rounded-lg p-2 whitespace-pre-wrap max-h-32 overflow-y-auto">
            {editedDraft}
          </div>
        )}
      </div>

      {/* Action buttons — only shown while pending or to change status */}
      {finding.status !== 'discarded' && (
        <div className="flex gap-2">
          <button
            onClick={onApprove}
            className={`flex-1 text-xs py-1.5 rounded-lg font-medium transition-colors ${
              finding.status === 'approved' || finding.status === 'edited'
                ? 'bg-green-600 text-white'
                : 'border border-green-300 text-green-700 hover:bg-green-50'
            }`}
          >
            ✓ Approve
          </button>
          <button
            onClick={onDiscard}
            className="flex-1 text-xs py-1.5 rounded-lg font-medium border border-red-200 text-red-500 hover:bg-red-50 transition-colors"
          >
            ✕ Discard
          </button>
        </div>
      )}

      {/* Undo discard */}
      {finding.status === 'discarded' && (
        <button
          onClick={onApprove}
          className="w-full text-xs py-1.5 rounded-lg font-medium border border-gray-300 text-gray-500 hover:bg-gray-50 transition-colors"
        >
          Undo — restore this enquiry
        </button>
      )}
    </div>
  )
}
