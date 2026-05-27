'use client'
import { useEffect, useState, useRef } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '../../../lib/auth'

export default function CasePage() {
  const { titleNumber } = useParams()
  const [caseData, setCaseData] = useState(null)
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pageLoading, setPageLoading] = useState(true)
  const messagesEndRef = useRef(null)
  const { user, loading: authLoading } = useAuth()

  useEffect(() => { fetchCase() }, [titleNumber])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const fetchCase = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/cases/${titleNumber}`, {
      headers: {
        'ngrok-skip-browser-warning': 'true'
        }
      })
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

  const sendMessage = async (type) => {
    if (!input.trim()) return
    const userMessage = input
    setInput('')

    // Add user message to chat history
    const newMessages = [...messages, { role: 'user', content: userMessage }]
    setMessages(newMessages)
    setLoading(true)

    try {
      let res, data

      // Build conversation history to send to backend
      // This is what gives the AI memory of previous messages
      const history = newMessages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))

      if (type === 'question') {
        res = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/chat?title_number=${titleNumber}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json',
                      'ngrok-skip-browser-warning': 'true'
             },
            body: JSON.stringify({
              question: userMessage,
              history: history  // send full history
            })
          }
        )
        data = await res.json()
        setMessages(prev => [...prev, {
          role: 'assistant',
          type: 'answer',
          content: data.answer
        }])

      } else {
        res = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/raise-enquiry?title_number=${titleNumber}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' , 'ngrok-skip-browser-warning': 'true' },
            body: JSON.stringify({
              issue: userMessage,
              history: history  // send full history
            })
          }
        )
        data = await res.json()
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

  if (pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-400">Loading case...</p>
      </div>
    )
  }

  if (authLoading) {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-gray-400">Loading...</p>
    </div>
  )
}

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">

      {/* LEFT PANEL */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-gray-100">
          <a href="/" className="text-blue-500 text-sm">← All Cases</a>
          <h1 className="font-bold text-gray-900 mt-2">{titleNumber}</h1>
          <p className="text-xs text-gray-400">{caseData?.documents?.length || 0} document(s)</p>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {caseData?.documents?.length === 0 ? (
            <p className="text-xs text-gray-400 p-2">No documents yet</p>
          ) : (
            caseData?.documents?.map((doc) => (
              <div
                key={doc.id}
                onClick={() => setSelectedDoc(doc)}
                className={`p-3 rounded-lg cursor-pointer mb-2 ${selectedDoc?.id === doc.id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50 border border-transparent'}`}
              >
                <p className="text-sm font-medium text-gray-800">{doc.doc_type}</p>
                <p className="text-xs text-gray-400 mt-1 truncate">{doc.filename}</p>
                <p className="text-xs text-gray-300 mt-1">{new Date(doc.uploaded_at).toLocaleDateString('en-GB')}</p>
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
                  await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/cases/${titleNumber}/documents/${doc.id}`, {
                    method: 'DELETE',
                    headers: {
                      'ngrok-skip-browser-warning': 'true'
                    }
                  })
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


{/* MIDDLE PANEL - inline PDF viewer using iframe */}
<div className="flex-1 flex flex-col border-r border-gray-200 bg-white">

  {/* Header shows the currently selected document name */}
  <div className="p-4 border-b border-gray-100">
    <p className="text-sm font-medium text-gray-700">
      {selectedDoc ? `${selectedDoc.doc_type} — ${selectedDoc.filename}` : 'No document selected'}
    </p>
  </div>

  {/* PDF viewer — fills remaining height */}
  <div className="flex-1 overflow-hidden">
    {selectedDoc && selectedDoc.file_url ? (
      // iframe points to Railway /view-pdf/ endpoint
      // that endpoint serves the OCR'd PDF with Content-Disposition: inline
      // so the browser renders it directly instead of downloading
      <iframe
        src={selectedDoc.file_url}
        className="w-full h-full border-0"
        title={selectedDoc.filename}
      />
    ) : (
      // shown when no doc is selected or file_url is missing
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-300 text-sm">Select a document from the left panel</p>
      </div>
    )}
  </div>

</div>

      {/* RIGHT PANEL - Chatbot */}
      <div className="w-96 flex flex-col bg-white flex-shrink-0">
        <div className="p-4 border-b border-gray-100">
          <p className="font-semibold text-gray-800">AI Assistant</p>
          <p className="text-xs text-gray-400">Searching all documents in {titleNumber}</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-300 text-sm mt-8">
              <p>Ask a question about this case</p>
              <p className="mt-1">or describe an issue to raise an enquiry</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div className={`max-w-[85%] ${
                msg.role === 'user' ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2 text-sm' :
                msg.type === 'enquiry' ? 'bg-green-50 border border-green-200 rounded-2xl rounded-tl-sm p-3' :
                msg.type === 'error' ? 'bg-red-50 border border-red-200 rounded-2xl rounded-tl-sm p-3' :
                'bg-gray-100 rounded-2xl rounded-tl-sm p-3'
              }`}>
                {msg.type === 'enquiry' && (
                  <div className="flex items-center gap-2 mb-2">
                    <span className="bg-green-600 text-white text-xs px-2 py-0.5 rounded-full font-medium">{msg.enquiry_code}</span>
                    <span className="text-xs text-green-700">{msg.enquiry_topic}</span>
                  </div>
                )}
                <p className="text-sm text-gray-800 whitespace-pre-wrap">{msg.content}</p>
                {msg.role === 'assistant' && msg.type !== 'error' && (
                  <button onClick={() => copyToClipboard(msg.content)} className="mt-2 text-xs text-gray-400 hover:text-gray-600">
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
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
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