'use client'
// app/case/[titleNumber]/chatbot/page.js
// The existing AI chatbot — moved here from the root case page
// Now lives at /case/[titleNumber]/chatbot
// Back button returns to the case dashboard at /case/[titleNumber]
// All logic is identical to the original page.js — only routing changed

import { useEffect, useState, useRef } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '../../../../lib/auth'
import ReactMarkdown from 'react-markdown'

export default function ChatbotPage() {
  const { titleNumber } = useParams()
  const [caseData, setCaseData] = useState(null)
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [pdfPage, setPdfPage] = useState(null)    // drives the #page=N fragment on the iframe
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pageLoading, setPageLoading] = useState(true)
  const messagesEndRef = useRef(null)
  const { user, loading: authLoading } = useAuth()

  useEffect(() => { fetchCase() }, [titleNumber])

  // Auto-scroll to latest message whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchCase = async () => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/cases/${titleNumber}`,
        { headers: { 'ngrok-skip-browser-warning': 'true' } }
      )
      const data = await res.json()
      if (data.success) {
        setCaseData(data)
        // Auto-select first document so the PDF viewer shows something immediately
        if (data.documents.length > 0) setSelectedDoc(data.documents[0])
      }
    } catch (err) {
      console.error(err)
    } finally {
      setPageLoading(false)
    }
  }

  // Opens a document in the middle-panel viewer by filename.
  // Clears any active #page fragment so the PDF loads from page 1.
  const openSourceDocument = (filename) => {
    if (!filename) return
    const doc = caseData?.documents?.find(
      d => d.filename.trim().toLowerCase() === filename.trim().toLowerCase()
    )
    if (doc) {
      setSelectedDoc(doc)
      setPdfPage(null)   // clear page jump so the doc opens at the beginning
    } else {
      alert(`Document '${filename}' not found.`)
    }
  }

  // Opens a document AND jumps to the estimated page containing the ref phrase.
  // Calls /find-page on the backend which searches ChromaDB chunks for the phrase,
  // then uses #page=N — the one PDF fragment Chrome's native viewer actually supports.
  const openCitation = async (filename, ref) => {
    if (!filename || !ref) return
    const doc = caseData?.documents?.find(
      d => d.filename.trim().toLowerCase() === filename.trim().toLowerCase()
    )
    if (!doc) return

    // Load the document immediately so the user sees it switching
    setSelectedDoc(doc)
    setPdfPage(null)  // reset while we look up the page

    try {
      // Ask the backend to search chunk texts and return an estimated page number
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/find-page?` +
        `title_number=${encodeURIComponent(titleNumber)}` +
        `&filename=${encodeURIComponent(filename)}` +
        `&query=${encodeURIComponent(ref)}`,
        { headers: { 'ngrok-skip-browser-warning': 'true' } }
      )
      const data = await res.json()
      // Set the page — the iframe key will remount to apply #page=N
      setPdfPage(data.page || 1)
    } catch {
      // If the lookup fails, the doc is still open — just no page jump
      setPdfPage(1)
    }
  }

  const sendMessage = async (type) => {
    if (!input.trim()) return

    const userMessage = input
    setInput('')

    // Append user message to chat history immediately for responsive feel
    const newMessages = [...messages, { role: 'user', content: userMessage }]
    setMessages(newMessages)
    setLoading(true)

    try {
      // Build full conversation history to give the AI memory of prior turns
      const history = newMessages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))

      if (type === 'question') {
        // General Q&A — searches case documents for relevant context
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/chat?title_number=${titleNumber}`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify({
              question: userMessage,
              history,
              // Pass currently open document so backend can prioritise it
              current_document: selectedDoc ? selectedDoc.filename : null
            })
          }
        )
        const data = await res.json()
        setMessages(prev => [...prev, {
          role: 'assistant',
          type: 'answer',
          content: data.answer,
          sources: data.sources || [],      // filenames LLM cited → source pills
          citations: data.citations || []   // [{source, ref}] → InPage Ref pills
        }])

      } else {
        // Enquiry generation — matches format library + fills with case facts
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/raise-enquiry?title_number=${titleNumber}`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify({
              issue: userMessage,
              history,
              current_document: selectedDoc ? selectedDoc.filename : null
            })
          }
        )
        const data = await res.json()
        setMessages(prev => [...prev, {
          role: 'assistant',
          type: 'enquiry',
          content: data.generated_text,
          enquiry_code: data.enquiry_code,
          enquiry_topic: data.enquiry_topic
        }])
      }

    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        type: 'error',
        content: 'Something went wrong. Please try again.'
      }])
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
    alert('Copied!')
  }

  if (pageLoading || authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-400">Loading case...</p>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">

      {/* ── LEFT PANEL: Document list ──────────────────────────────── */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-gray-100">
          {/* Back to case dashboard — updated from original "/" to case page */}
          <a
            href={`/case/${titleNumber}`}
            className="text-blue-500 text-sm"
          >
            ← Case Dashboard
          </a>
          <h1 className="font-bold text-gray-900 mt-2">{titleNumber}</h1>
          <p className="text-xs text-gray-400">
            {caseData?.documents?.length || 0} document(s)
          </p>
        </div>

        {/* Scrollable document list */}
        <div className="flex-1 overflow-y-auto p-3">
          {caseData?.documents?.length === 0 ? (
            <p className="text-xs text-gray-400 p-2">No documents yet</p>
          ) : (
            caseData?.documents?.map((doc) => (
              <div
                key={doc.id}
                onClick={() => setSelectedDoc(doc)}
                className={`p-3 rounded-lg cursor-pointer mb-2 ${
                  selectedDoc?.id === doc.id
                    ? 'bg-blue-50 border border-blue-200'
                    : 'hover:bg-gray-50 border border-transparent'
                }`}
              >
                <p className="text-sm font-medium text-gray-800">{doc.doc_type}</p>
                <p className="text-xs text-gray-400 mt-1 truncate">{doc.filename}</p>
                <p className="text-xs text-gray-300 mt-1">
                  {new Date(doc.uploaded_at).toLocaleDateString('en-GB')}
                </p>
                {doc.file_url && (
                  <a
                    href={doc.file_url}
                    target="_blank"
                    onClick={(e) => e.stopPropagation()}
                    className="text-xs text-blue-500 mt-1 block hover:underline"
                  >
                    Download OCR PDF
                  </a>
                )}
                {/* Delete document */}
                <button
                  onClick={async (e) => {
                    e.stopPropagation()
                    if (!confirm('Delete this document? This cannot be undone.')) return
                    await fetch(
                      `${process.env.NEXT_PUBLIC_BACKEND_URL}/cases/${titleNumber}/documents/${doc.id}`,
                      {
                        method: 'DELETE',
                        headers: { 'ngrok-skip-browser-warning': 'true' }
                      }
                    )
                    fetchCase()
                  }}
                  className="text-xs text-red-400 hover:text-red-600 mt-1 block"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>

        {/* Upload new document link */}
        <div className="p-3 border-t border-gray-100">
          <a
            href={`/case/${titleNumber}/upload`}
            className="block w-full bg-blue-600 text-white text-center py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            + Upload Document
          </a>
        </div>
      </div>

      {/* ── MIDDLE PANEL: Inline PDF viewer ───────────────────────── */}
      <div className="flex-1 flex flex-col border-r border-gray-200 bg-white">
        {/* Header shows currently selected document */}
        <div className="p-4 border-b border-gray-100">
          <p className="text-sm font-medium text-gray-700">
            {selectedDoc
              ? `${selectedDoc.doc_type} — ${selectedDoc.filename}`
              : 'No document selected'
            }
          </p>
        </div>

        {/* PDF iframe — #page=N fragment used when an InPage Ref is clicked.
             Chrome's built-in PDF viewer supports #page=N and jumps to that page.
             The key prop forces a full iframe remount whenever the URL or page changes,
             ensuring the browser actually loads the new fragment. */}
        <div className="flex-1 overflow-hidden">
          {selectedDoc && selectedDoc.file_url ? (
            <iframe
              key={selectedDoc.file_url + (pdfPage ?? '')}  // remount on doc or page change
              src={
                pdfPage
                  ? `${selectedDoc.file_url}#page=${pdfPage}`
                  : selectedDoc.file_url
              }
              className="w-full h-full border-0"
              title={selectedDoc.filename}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-300 text-sm">
                Select a document from the left panel
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── RIGHT PANEL: AI Chatbot ────────────────────────────────── */}
      <div className="w-96 flex flex-col bg-white flex-shrink-0">
        <div className="p-4 border-b border-gray-100">
          <p className="font-semibold text-gray-800">AI Assistant</p>
          <p className="text-xs text-gray-400">
            Searching all documents in {titleNumber}
          </p>
        </div>

        {/* Message history */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-300 text-sm mt-8">
              <p>Ask a question about this case</p>
              <p className="mt-1">or describe an issue to raise an enquiry</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
            >
              <div className={`max-w-[85%] ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2 text-sm'
                  : msg.type === 'enquiry'
                    ? 'bg-green-50 border border-green-200 rounded-2xl rounded-tl-sm p-3'
                    : msg.type === 'error'
                      ? 'bg-red-50 border border-red-200 rounded-2xl rounded-tl-sm p-3'
                      : 'bg-gray-100 rounded-2xl rounded-tl-sm p-3'
              }`}>
                {/* Enquiry code badge */}
                {msg.type === 'enquiry' && (
                  <div className="flex items-center gap-2 mb-2">
                    <span className="bg-green-600 text-white text-xs px-2 py-0.5 rounded-full font-medium">
                      {msg.enquiry_code}
                    </span>
                    <span className="text-xs text-green-700">{msg.enquiry_topic}</span>
                  </div>
                )}
                {/* Render answer/error text — use ReactMarkdown so inline [Source:] refs render nicely */}
                {msg.role === 'assistant' ? (
                  <div className="text-sm text-gray-800 prose prose-sm max-w-none">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  // User bubble — plain text is fine
                  <p className="text-sm text-white">{msg.content}</p>
                )}

                {/* ── SOURCE DOCUMENT PILLS ─────────────────────────────────────────
                     Shown only on answer messages that have associated sources.
                     Each pill is a button that calls openSourceDocument() to swap
                     the middle-panel PDF viewer to that document — no redirect,
                     no new tab, everything stays in the same page session.
                ─────────────────────────────────────────────────────────────────── */}
                {msg.type === 'answer' && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-gray-200">
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                      📄 Sources
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.sources.map((src, si) => (
                        <button
                          key={si}
                          onClick={() => openSourceDocument(src)}
                          title={`Open ${src} in the viewer`}
                          className="inline-flex items-center gap-1 bg-blue-50 hover:bg-blue-100 active:bg-blue-200 border border-blue-200 text-blue-700 rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors cursor-pointer max-w-[200px]"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span className="truncate">{src}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* ── INPAGE REF PILLS ────────────────────────────────────────────
                     Each citation is a {source, ref} pair from the backend.
                     Clicking loads the paired source doc AND applies #search=ref
                     to the iframe, making Chrome's PDF viewer jump to that phrase.
                     Purple colour distinguishes them from blue source pills.
                ─────────────────────────────────────────────────────────────────── */}
                {msg.type === 'answer' && msg.citations && msg.citations.length > 0 && (
                  <div className="mt-2">
                    <p className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider mb-1.5">
                      📍 In-Page References
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.citations.map((cite, ci) => (
                        <button
                          key={ci}
                          onClick={() => openCitation(cite.source, cite.ref)}
                          title={`Jump to "${cite.ref}" in ${cite.source}`}
                          className="inline-flex items-center gap-1 bg-purple-50 hover:bg-purple-100 active:bg-purple-200 border border-purple-200 text-purple-700 rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors cursor-pointer max-w-[200px]"
                        >
                          {/* Location pin icon */}
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          <span className="truncate">{cite.ref}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {/* Copy button for assistant messages */}
                {msg.role === 'assistant' && msg.type !== 'error' && (
                  <button
                    onClick={() => copyToClipboard(msg.content)}
                    className="mt-2 text-xs text-gray-400 hover:text-gray-600"
                  >
                    Copy
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* Thinking indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-2">
                <p className="text-sm text-gray-400">Thinking...</p>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="p-4 border-t border-gray-100">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question or describe an issue..."
            rows={3}
            className="w-full border text-black border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => sendMessage('question')}
              disabled={loading || !input.trim()}
              className="flex-1 bg-gray-800 text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-900 disabled:opacity-50"
            >
              Ask Question
            </button>
            <button
              onClick={() => sendMessage('enquiry')}
              disabled={loading || !input.trim()}
              className="flex-1 bg-green-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              Raise Enquiry
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}