// app/case/[titleNumber]/chatbot/page.js - Updated version

'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '../../../../lib/auth'
import { apiFetch } from '../../../../lib/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ChatbotPage() {
  const { titleNumber } = useParams()
  const [caseData, setCaseData] = useState(null)
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [pdfPage, setPdfPage] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pageLoading, setPageLoading] = useState(true)
  const messagesEndRef = useRef(null)
  const { user, loading: authLoading } = useAuth()
  const [pdfHighlight, setPdfHighlight] = useState(null)
  const [showHighlight, setShowHighlight] = useState(false)
  const [highlightPosition, setHighlightPosition] = useState({ x: 0, y: 0, width: 0, height: 0 })
  const [iframeLoaded, setIframeLoaded] = useState(false)
  const containerRef = useRef(null)
  const iframeRef = useRef(null)

  useEffect(() => { fetchCase() }, [titleNumber])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    setPdfHighlight(null)
    setShowHighlight(false)
    setPdfPage(null)
    setIframeLoaded(false)
    setHighlightPosition({ x: 0, y: 0, width: 0, height: 0 })
  }, [selectedDoc])

  const fetchCase = async () => {
    try {
      const res = await apiFetch(`/cases/${titleNumber}`)
      const data = await res.json()
      if (data.success) {
        setCaseData(data)
        if (data.documents.length > 0) setSelectedDoc(data.documents[0])
      }
    } catch (err) {
      console.error(err)
    } finally {
      setPageLoading(false)
    }
  }

  const openSourceDocument = (filename) => {
    if (!filename) return
    const doc = caseData?.documents?.find(
      d => d.filename.trim().toLowerCase() === filename.trim().toLowerCase()
    )
    if (doc) {
      setSelectedDoc(doc)
      setPdfPage(null)
      setPdfHighlight(null)
      setShowHighlight(false)
      setIframeLoaded(false)
    } else {
      alert(`Document '${filename}' not found.`)
    }
  }

  const openCitation = (chunk) => {
    if (!chunk) return
    const doc = caseData?.documents?.find(
      d => d.filename.trim().toLowerCase() === chunk.source.trim().toLowerCase()
    )
    if (!doc) return
    
    setSelectedDoc(doc)
    setPdfPage(chunk.page)
    setPdfHighlight(chunk.bbox || null)
    setShowHighlight(true)
    setIframeLoaded(false)
    setHighlightPosition({ x: 0, y: 0, width: 0, height: 0 })
  }

  const calculateHighlightPosition = useCallback((bbox) => {
    if (!bbox || !iframeRef.current || !containerRef.current) {
      return
    }
    
    try {
      const iframe = iframeRef.current
      const container = containerRef.current
      const iframeRect = iframe.getBoundingClientRect()
      const containerRect = container.getBoundingClientRect()
      
      // Check if bbox values are normalized (0-1) or in points (0-~600)
      const maxVal = Math.max(...bbox)
      const isNormalized = maxVal <= 1.0
      
      let normalizedBbox
      
      if (isNormalized) {
        normalizedBbox = bbox
      } else {
        // Convert points to normalized using standard A4 page size
        const pageWidth = 595.28
        const pageHeight = 841.89
        
        normalizedBbox = [
          bbox[0] / pageWidth,
          bbox[1] / pageHeight,
          bbox[2] / pageWidth,
          bbox[3] / pageHeight
        ]
      }
      
      // Calculate pixel positions relative to container
      const x = normalizedBbox[0] * iframeRect.width + (iframeRect.left - containerRect.left)
      const y = normalizedBbox[1] * iframeRect.height + (iframeRect.top - containerRect.top)
      const width = (normalizedBbox[2] - normalizedBbox[0]) * iframeRect.width
      const height = (normalizedBbox[3] - normalizedBbox[1]) * iframeRect.height
      
      setHighlightPosition({ x, y, width, height })
    } catch (err) {
      console.error('Error calculating highlight position:', err)
    }
  }, [])

  const handleIframeLoad = useCallback(() => {
    setIframeLoaded(true)
    if (pdfHighlight && showHighlight) {
      setTimeout(() => {
        calculateHighlightPosition(pdfHighlight)
      }, 500)
    }
  }, [pdfHighlight, showHighlight, calculateHighlightPosition])

  // Recalculate on resize
  useEffect(() => {
    const handleResize = () => {
      if (pdfHighlight && showHighlight && iframeLoaded) {
        calculateHighlightPosition(pdfHighlight)
      }
    }
    
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [pdfHighlight, showHighlight, iframeLoaded, calculateHighlightPosition])

  const sendMessage = async (type) => {
    if (!input.trim()) return

    const userMessage = input
    setInput('')

    const newMessages = [...messages, { role: 'user', content: userMessage }]
    setMessages(newMessages)
    setLoading(true)

    try {
      const history = newMessages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))

      if (type === 'question') {
        const res = await apiFetch(`/chat?title_number=${encodeURIComponent(titleNumber)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: userMessage,
            history,
            current_document: selectedDoc ? selectedDoc.filename : null
          })
        })
        const data = await res.json()
        
        // Clean citations
        const cleanedAnswer = data.answer
          .replace(/【C(\d+)】/g, '[C$1]')
          .replace(/\[C(\d+)\]/g, '[C$1]')
        
        setMessages(prev => [...prev, {
          role: 'assistant',
          type: 'answer',
          content: cleanedAnswer,
          chunks: data.chunks || []
        }])
      } else {
        const res = await apiFetch(`/raise-enquiry?title_number=${encodeURIComponent(titleNumber)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            issue: userMessage,
            history,
            current_document: selectedDoc ? selectedDoc.filename : null
          })
        })
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
          <a href={`/case/${titleNumber}`} className="text-blue-500 text-sm">
            ← Case Dashboard
          </a>
          <h1 className="font-bold text-gray-900 mt-2">{titleNumber}</h1>
          <p className="text-xs text-gray-400">
            {caseData?.documents?.length || 0} document(s)
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {caseData?.documents?.length === 0 ? (
            <p className="text-xs text-gray-400 p-2">No documents yet</p>
          ) : (
            caseData?.documents?.map((doc) => (
              <div
                key={doc.id}
                onClick={() => {
                  setSelectedDoc(doc)
                  setPdfHighlight(null)
                  setShowHighlight(false)
                  setPdfPage(null)
                  setIframeLoaded(false)
                }}
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
                <button
                  onClick={async (e) => {
                    e.stopPropagation()
                    if (!confirm('Delete this document? This cannot be undone.')) return
                    await apiFetch(`/cases/${titleNumber}/documents/${doc.id}`, { method: 'DELETE' })
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

        <div className="p-3 border-t border-gray-100">
          <a
            href={`/case/${titleNumber}/upload`}
            className="block w-full bg-blue-600 text-white text-center py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            + Upload Document
          </a>
        </div>
      </div>

      {/* ── MIDDLE PANEL: PDF Viewer with Highlight ────────────────── */}
      <div className="flex-1 flex flex-col border-r border-gray-200 bg-white">
        <div className="p-4 border-b border-gray-100 flex justify-between items-center">
          <p className="text-sm font-medium text-gray-700 truncate">
            {selectedDoc
              ? `${selectedDoc.doc_type} — ${selectedDoc.filename}`
              : 'No document selected'
            }
          </p>
          {showHighlight && (
            <button
              onClick={() => {
                setShowHighlight(false)
                setPdfHighlight(null)
                setHighlightPosition({ x: 0, y: 0, width: 0, height: 0 })
              }}
              className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-300 hover:border-gray-500"
            >
              ✕ Clear highlight
            </button>
          )}
        </div>

        <div ref={containerRef} className="flex-1 overflow-hidden bg-gray-100 relative">
          {selectedDoc && selectedDoc.file_url ? (
            <>
              <iframe
                ref={iframeRef}
                key={`${selectedDoc.id}-${pdfPage || 1}`}
                src={`${selectedDoc.file_url}${pdfPage ? `#page=${pdfPage}` : ''}`}
                className="w-full h-full"
                style={{
                  border: 'none',
                  backgroundColor: 'white'
                }}
                title={`PDF Viewer: ${selectedDoc.filename}`}
                allow="fullscreen"
                onLoad={handleIframeLoad}
              />
              
              {/* Highlight Overlay - fixed position over the iframe */}
              {showHighlight && pdfHighlight && highlightPosition.width > 0 && highlightPosition.height > 0 && (
                <div
                  className="absolute pointer-events-none"
                  style={{
                    left: `${highlightPosition.x}px`,
                    top: `${highlightPosition.y}px`,
                    width: `${Math.max(highlightPosition.width, 2)}px`,
                    height: `${Math.max(highlightPosition.height, 2)}px`,
                    border: '3px solid #fbbf24',
                    backgroundColor: 'rgba(251, 191, 36, 0.25)',
                    borderRadius: '2px',
                    boxShadow: '0 0 20px rgba(251, 191, 36, 0.3), inset 0 0 20px rgba(251, 191, 36, 0.1)',
                    zIndex: 10
                  }}
                />
              )}
            </>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-300 text-sm">
                Select a document from the left panel
              </p>
            </div>
          )}
        </div>

        {/* Page navigation */}
        {selectedDoc && (
          <div className="p-2 border-t border-gray-100 flex justify-center items-center gap-4 bg-white">
            <button
              onClick={() => {
                const currentPage = pdfPage || 1
                if (currentPage > 1) {
                  setPdfPage(currentPage - 1)
                  setShowHighlight(false)
                  setPdfHighlight(null)
                  setIframeLoaded(false)
                }
              }}
              disabled={(pdfPage || 1) <= 1}
              className="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ← Previous
            </button>
            <span className="text-sm text-gray-600">
              Page {pdfPage || 1}
            </span>
            <button
              onClick={() => {
                const currentPage = pdfPage || 1
                setPdfPage(currentPage + 1)
                setShowHighlight(false)
                setPdfHighlight(null)
                setIframeLoaded(false)
              }}
              className="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200"
            >
              Next →
            </button>
          </div>
        )}
      </div>

      {/* ── RIGHT PANEL: AI Chatbot ────────────────────────────────── */}
      <div className="w-96 flex flex-col bg-white flex-shrink-0">
        <div className="p-4 border-b border-gray-100">
          <p className="font-semibold text-gray-800">AI Assistant</p>
          <p className="text-xs text-gray-400">
            Searching all documents in {titleNumber}
          </p>
        </div>

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
                {msg.type === 'enquiry' && (
                  <div className="flex items-center gap-2 mb-2">
                    <span className="bg-green-600 text-white text-xs px-2 py-0.5 rounded-full font-medium">
                      {msg.enquiry_code}
                    </span>
                    <span className="text-xs text-green-700">{msg.enquiry_topic}</span>
                  </div>
                )}
                
                {msg.role === 'assistant' ? (
                  <div className="text-sm text-gray-800 prose prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm text-white">{msg.content}</p>
                )}

                {/* ── In-Page References ────────────────────────────────────────── */}
                {msg.type === 'answer' && msg.chunks && msg.chunks.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-gray-200">
                    <p className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider mb-1.5">
                      📍 In-Page References
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.chunks.map((cite, ci) => {
                        const source = cite.source || cite.filename || 'Unknown'
                        const page = cite.page || 1
                        const bbox = cite.bbox || null
                        const isActive = showHighlight && 
                          bbox && 
                          pdfHighlight === bbox &&
                          selectedDoc?.filename === source
                        
                        return (
                          <button
                            key={ci}
                            onClick={() => openCitation(cite)}
                            title={`Jump to page ${page} in ${source}`}
                            className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-md transition-colors ${
                              isActive
                                ? 'bg-purple-200 border-purple-400 text-purple-900'
                                : 'bg-purple-50 hover:bg-purple-100 border border-purple-200 text-purple-700'
                            }`}
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 0111.314 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            <span>
                              {source.split('.')[0]}
                              {page && ` • Pg ${page}`}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}
                
                {/* Copy button */}
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

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-2">
                <p className="text-sm text-gray-400">Thinking...</p>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

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