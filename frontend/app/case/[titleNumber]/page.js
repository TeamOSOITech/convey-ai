// 'use client'
// import { useEffect, useState, useRef } from 'react'
// import { useParams } from 'next/navigation'
// import { useAuth } from '../../../lib/auth'

// export default function CasePage() {
//   const { titleNumber } = useParams()
//   const [caseData, setCaseData] = useState(null)
//   const [selectedDoc, setSelectedDoc] = useState(null)
//   const [messages, setMessages] = useState([])
//   const [input, setInput] = useState('')
//   const [loading, setLoading] = useState(false)
//   const [pageLoading, setPageLoading] = useState(true)
//   const messagesEndRef = useRef(null)
//   const { user, loading: authLoading } = useAuth()

//   useEffect(() => { fetchCase() }, [titleNumber])
//   useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

//   const fetchCase = async () => {
//     try {
//       const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/cases/${titleNumber}`, {
//       headers: {
//         'ngrok-skip-browser-warning': 'true'
//         }
//       })
//       const data = await res.json()
//       if (data.success) {
//         setCaseData(data)
//         if (data.documents.length > 0) setSelectedDoc(data.documents[0])
//       }
//     } catch (err) {
//       console.error(err)
//     } finally {
//       setPageLoading(false)
//     }
//   }

//   // const sendMessage = async (type) => {
//   //   if (!input.trim()) return
//   //   const userMessage = input
//   //   setInput('')

//   //   // Add user message to chat history
//   //   const newMessages = [...messages, { role: 'user', content: userMessage }]
//   //   setMessages(newMessages)
//   //   setLoading(true)

//   //   try {
//   //     let res, data

//   //     // Build conversation history to send to backend
//   //     // This is what gives the AI memory of previous messages
//   //     const history = newMessages.map(msg => ({
//   //       role: msg.role,
//   //       content: msg.content
//   //     }))

//   //     if (type === 'question') {
//   //       res = await fetch(
//   //         `${process.env.NEXT_PUBLIC_BACKEND_URL}/chat?title_number=${titleNumber}`,
//   //         {
//   //           method: 'POST',
//   //           headers: { 'Content-Type': 'application/json',
//   //                     'ngrok-skip-browser-warning': 'true'
//   //            },
//   //           body: JSON.stringify({
//   //             question: userMessage,
//   //             history: history  // send full history
//   //           })
//   //         }
//   //       )
//   //       data = await res.json()
//   //       setMessages(prev => [...prev, {
//   //         role: 'assistant',
//   //         type: 'answer',
//   //         content: data.answer
//   //       }])

//   //     } else {
//   //       res = await fetch(
//   //         `${process.env.NEXT_PUBLIC_BACKEND_URL}/raise-enquiry?title_number=${titleNumber}`,
//   //         {
//   //           method: 'POST',
//   //           headers: { 'Content-Type': 'application/json' , 'ngrok-skip-browser-warning': 'true' },
//   //           body: JSON.stringify({
//   //             issue: userMessage,
//   //             history: history  // send full history
//   //           })
//   //         }
//   //       )
//   //       data = await res.json()
//   //       setMessages(prev => [...prev, {
//   //         role: 'assistant',
//   //         type: 'enquiry',
//   //         content: data.generated_text,
//   //         enquiry_code: data.enquiry_code,
//   //         enquiry_topic: data.enquiry_topic
//   //       }])
//   //     }

//   //   } catch (err) {
//   //     setMessages(prev => [...prev, {
//   //       role: 'assistant',
//   //       type: 'error',
//   //       content: 'Something went wrong. Please try again.'
//   //     }])
//   //   } finally {
//   //     setLoading(false)
//   //   }
//   // }
//   const sendMessage = async (type) => {
//     if (!input.trim()) return
//     const userMessage = input
//     setInput('')

//     // Add user message to chat history
//     const newMessages = [...messages, { role: 'user', content: userMessage }]
//     setMessages(newMessages)
//     setLoading(true)

//     try {
//       let res, data

//       // Build conversation history to send to backend
//       // This is what gives the AI memory of previous messages
//       const history = newMessages.map(msg => ({
//         role: msg.role,
//         content: msg.content
//       }))

//       if (type === 'question') {
//         res = await fetch(
//           `${process.env.NEXT_PUBLIC_BACKEND_URL}/chat?title_number=${titleNumber}`,
//           {
//             method: 'POST',
//             headers: { 
//               'Content-Type': 'application/json',
//               'ngrok-skip-browser-warning': 'true'
//             },
//             body: JSON.stringify({
//               question: userMessage,
//               history: history,
//               // CRITICAL ADDITION: Tell the backend which document is on screen
//               current_document: selectedDoc ? selectedDoc.filename : null
//             })
//           }
//         )
//         data = await res.json()
//         setMessages(prev => [...prev, {
//           role: 'assistant',
//           type: 'answer',
//           content: data.answer
//         }])

//       } else {
//         res = await fetch(
//           `${process.env.NEXT_PUBLIC_BACKEND_URL}/raise-enquiry?title_number=${titleNumber}`,
//           {
//             method: 'POST',
//             headers: { 
//               'Content-Type': 'application/json', 
//               'ngrok-skip-browser-warning': 'true' 
//             },
//             body: JSON.stringify({
//               issue: userMessage,
//               history: history,
//               // CRITICAL ADDITION: Tell the backend which document is on screen
//               current_document: selectedDoc ? selectedDoc.filename : null
//             })
//           }
//         )
//         data = await res.json()
//         setMessages(prev => [...prev, {
//           role: 'assistant',
//           type: 'enquiry',
//           content: data.generated_text,
//           enquiry_code: data.enquiry_code,
//           enquiry_topic: data.enquiry_topic
//         }])
//       }

//     } catch (err) {
//       setMessages(prev => [...prev, {
//         role: 'assistant',
//         type: 'error',
//         content: 'Something went wrong. Please try again.'
//       }])
//     } finally {
//       setLoading(false)
//     }
//   }

//   const copyToClipboard = (text) => {
//     navigator.clipboard.writeText(text)
//     alert('Copied!')
//   }

//   if (pageLoading) {
//     return (
//       <div className="flex items-center justify-center min-h-screen">
//         <p className="text-gray-400">Loading case...</p>
//       </div>
//     )
//   }

//   if (authLoading) {
//   return (
//     <div className="flex items-center justify-center min-h-screen">
//       <p className="text-gray-400">Loading...</p>
//     </div>
//   )
// }

//   return (
//     <div className="flex h-screen bg-gray-50 overflow-hidden">

//       {/* LEFT PANEL */}
//       <div className="w-64 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
//         <div className="p-4 border-b border-gray-100">
//           <a href="/" className="text-blue-500 text-sm">← All Cases</a>
//           <h1 className="font-bold text-gray-900 mt-2">{titleNumber}</h1>
//           <p className="text-xs text-gray-400">{caseData?.documents?.length || 0} document(s)</p>
//         </div>

//         <div className="flex-1 overflow-y-auto p-3">
//           {caseData?.documents?.length === 0 ? (
//             <p className="text-xs text-gray-400 p-2">No documents yet</p>
//           ) : (
//             caseData?.documents?.map((doc) => (
//               <div
//                 key={doc.id}
//                 onClick={() => setSelectedDoc(doc)}
//                 className={`p-3 rounded-lg cursor-pointer mb-2 ${selectedDoc?.id === doc.id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50 border border-transparent'}`}
//               >
//                 <p className="text-sm font-medium text-gray-800">{doc.doc_type}</p>
//                 <p className="text-xs text-gray-400 mt-1 truncate">{doc.filename}</p>
//                 <p className="text-xs text-gray-300 mt-1">{new Date(doc.uploaded_at).toLocaleDateString('en-GB')}</p>
//                 {doc.file_url && (
//                   <a                                      
//                     href={doc.file_url}
//                     target="_blank"
//                     onClick={(e) => e.stopPropagation()}
//                     className="text-xs text-blue-500 mt-1 block hover:underline"
//                   >
//                     Download OCR PDF
//                   </a>
//                 )}
//                 <button
//                   onClick={async (e) => {
//                   e.stopPropagation()
//                   if (!confirm('Delete this document? This cannot be undone.')) return
//                   await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/cases/${titleNumber}/documents/${doc.id}`, {
//                     method: 'DELETE',
//                     headers: {
//                       'ngrok-skip-browser-warning': 'true'
//                     }
//                   })
//                   fetchCase()
//                 }}
//                 className="text-xs text-red-400 hover:text-red-600 mt-1 block"
//               >
//                 Delete
//               </button>
//               </div>
//             ))
//           )}
//         </div>

//         <div className="p-3 border-t border-gray-100">
//           <a                                              
//             href={`/case/${titleNumber}/upload`}
//             className="block w-full bg-blue-600 text-white text-center py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
//           >
//             + Upload Document
//           </a>
//         </div>
//       </div>


// {/* MIDDLE PANEL - inline PDF viewer using iframe */}
// <div className="flex-1 flex flex-col border-r border-gray-200 bg-white">

//   {/* Header shows the currently selected document name */}
//   <div className="p-4 border-b border-gray-100">
//     <p className="text-sm font-medium text-gray-700">
//       {selectedDoc ? `${selectedDoc.doc_type} — ${selectedDoc.filename}` : 'No document selected'}
//     </p>
//   </div>

//   {/* PDF viewer — fills remaining height */}
//   <div className="flex-1 overflow-hidden">
//     {selectedDoc && selectedDoc.file_url ? (
//       // iframe points to Railway /view-pdf/ endpoint
//       // that endpoint serves the OCR'd PDF with Content-Disposition: inline
//       // so the browser renders it directly instead of downloading
//       <iframe
//         src={selectedDoc.file_url}
//         className="w-full h-full border-0"
//         title={selectedDoc.filename}
//       />
//     ) : (
//       // shown when no doc is selected or file_url is missing
//       <div className="flex items-center justify-center h-full">
//         <p className="text-gray-300 text-sm">Select a document from the left panel</p>
//       </div>
//     )}
//   </div>

// </div>

//       {/* RIGHT PANEL - Chatbot */}
//       <div className="w-96 flex flex-col bg-white flex-shrink-0">
//         <div className="p-4 border-b border-gray-100">
//           <p className="font-semibold text-gray-800">AI Assistant</p>
//           <p className="text-xs text-gray-400">Searching all documents in {titleNumber}</p>
//         </div>

//         <div className="flex-1 overflow-y-auto p-4 space-y-4">
//           {messages.length === 0 && (
//             <div className="text-center text-gray-300 text-sm mt-8">
//               <p>Ask a question about this case</p>
//               <p className="mt-1">or describe an issue to raise an enquiry</p>
//             </div>
//           )}

//           {messages.map((msg, i) => (
//             <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
//               <div className={`max-w-[85%] ${
//                 msg.role === 'user' ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2 text-sm' :
//                 msg.type === 'enquiry' ? 'bg-green-50 border border-green-200 rounded-2xl rounded-tl-sm p-3' :
//                 msg.type === 'error' ? 'bg-red-50 border border-red-200 rounded-2xl rounded-tl-sm p-3' :
//                 'bg-gray-100 rounded-2xl rounded-tl-sm p-3'
//               }`}>
//                 {msg.type === 'enquiry' && (
//                   <div className="flex items-center gap-2 mb-2">
//                     <span className="bg-green-600 text-white text-xs px-2 py-0.5 rounded-full font-medium">{msg.enquiry_code}</span>
//                     <span className="text-xs text-green-700">{msg.enquiry_topic}</span>
//                   </div>
//                 )}
//                 <p className="text-sm text-gray-800 whitespace-pre-wrap">{msg.content}</p>
//                 {msg.role === 'assistant' && msg.type !== 'error' && (
//                   <button onClick={() => copyToClipboard(msg.content)} className="mt-2 text-xs text-gray-400 hover:text-gray-600">
//                     Copy
//                   </button>
//                 )}
//               </div>
//             </div>
//           ))}

//           {loading && (
//             <div className="flex justify-start">
//               <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-2">
//                 <p className="text-sm text-gray-400">Thinking...</p>
//               </div>
//             </div>
//           )}
//           <div ref={messagesEndRef} />
//         </div>

//         <div className="p-4 border-t border-gray-100">
//           <textarea
//             value={input}
//             onChange={(e) => setInput(e.target.value)}
//             placeholder="Ask a question or describe an issue..."
//             rows={3}
//             className="w-full border text-black border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
//           />
//           <div className="flex gap-2 mt-2">
//             <button
//               onClick={() => sendMessage('question')}
//               disabled={loading || !input.trim()}
//               className="flex-1 bg-gray-800 text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-900 disabled:opacity-50"
//             >
//               Ask Question
//             </button>
//             <button
//               onClick={() => sendMessage('enquiry')}
//               disabled={loading || !input.trim()}
//               className="flex-1 bg-green-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
//             >
//               Raise Enquiry
//             </button>
//           </div>
//         </div>
//       </div>
//     </div>
//   )
// }
'use client'
// app/case/[titleNumber]/page.js
// Case Dashboard — the landing page when you open any case
// Shows case metadata and a grid of available tools (Chatbot, Title Report, Letters etc.)
// Each tool card navigates to its own dedicated page

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '../../../lib/auth'

export default function CaseDashboard() {
  const { titleNumber } = useParams()
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  // Case data fetched from the backend (documents list + case metadata)
  const [caseData, setCaseData] = useState(null)
  const [pageLoading, setPageLoading] = useState(true)

  // Fetch case details on mount so we can show doc count in the header
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

  const handleDeleteDocument = async (docId) => {
    if (!confirm('Are you sure you want to delete this document? This will permanently remove it from the database and AI memory.')) return;
    
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/cases/${titleNumber}/documents/${docId}`,
        {
          method: 'DELETE',
          headers: { 'ngrok-skip-browser-warning': 'true' }
        }
      )
      
      const data = await res.json()
      if (data.success) {
        setCaseData(prev => ({
          ...prev,
          documents: prev.documents.filter(d => d.id !== docId)
        }))
      } else {
        alert(`Failed to delete document: ${data.error || 'Unknown error'}`)
      }
    } catch (err) {
      console.error('Failed to delete document:', err)
      alert('An error occurred while deleting the document.')
    }
  }

  // Tool definitions — add new tools here as they are built
  // Each tool card navigates to its own sub-page under /case/[titleNumber]/
  const tools = [
    {
      id: 'chatbot',
      title: 'AI Assistant',
      description: 'Ask questions about any document in this case. Raise formal enquiries using the format library.',
      icon: '💬',
      path: `/case/${titleNumber}/chatbot`,
      available: true,
      color: 'blue'
    },
    {
      id: 'title-report',
      title: 'Title Report',
      description: 'Select documents and extract dates, rights, covenants and provisions into a structured report.',
      icon: '📋',
      path: `/case/${titleNumber}/title-report`,
      available: true,
      color: 'indigo'
    },
    {
      id: 'title-check',
      title: 'Title Check',
      description: 'Select a TA6, TA10 or TA13 form. AI reads the checkboxes, applies your firm\'s checklist rules, and drafts the required enquiries for your review.',
      icon: '✅',
      path: `/case/${titleNumber}/title-check`,
      available: true,
      color: 'orange'
    },
    {
      id: 'letters',
      title: 'Letter Generator',
      description: 'Generate standard conveyancing letters — Report on Title, Completion Letters, Client Care and more.',
      icon: '✉️',
      path: `/case/${titleNumber}/letters`,
      available: false, // Coming soon
      color: 'green'
    },
    {
      id: 'key-dates',
      title: 'Key Dates',
      description: 'Track completion dates, search expiry, mortgage offer expiry and other critical deadlines.',
      icon: '📅',
      path: `/case/${titleNumber}/key-dates`,
      available: false, // Coming soon
      color: 'amber'
    },
    {
      id: 'completion-statement',
      title: 'Completion Statement',
      description: 'Generate buyer and seller financial breakdowns from case documents.',
      icon: '£',
      path: `/case/${titleNumber}/completion-statement`,
      available: false, // Coming soon
      color: 'emerald'
    }
  ]

  // Colour map for tool card accent colours
  // Tailwind classes must be written in full — no dynamic string construction
  const colorMap = {
    blue: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      icon: 'bg-blue-100',
      hover: 'hover:border-blue-400',
      badge: 'bg-blue-600'
    },
    indigo: {
      bg: 'bg-indigo-50',
      border: 'border-indigo-200',
      icon: 'bg-indigo-100',
      hover: 'hover:border-indigo-400',
      badge: 'bg-indigo-600'
    },
    green: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      icon: 'bg-green-100',
      hover: 'hover:border-green-300',
      badge: 'bg-green-600'
    },
    amber: {
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      icon: 'bg-amber-100',
      hover: 'hover:border-amber-300',
      badge: 'bg-amber-600'
    },
    emerald: {
      bg: 'bg-emerald-50',
      border: 'border-emerald-200',
      icon: 'bg-emerald-100',
      hover: 'hover:border-emerald-300',
      badge: 'bg-emerald-600'
    },
    orange: {
      bg: 'bg-orange-50',
      border: 'border-orange-200',
      icon: 'bg-orange-100',
      hover: 'hover:border-orange-400',
      badge: 'bg-orange-600'
    }
  }

  if (authLoading || pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-400 text-sm">Loading case...</p>
      </div>
    )
  }

  const docCount = caseData?.documents?.length || 0

  return (
    <div className="min-h-screen bg-gray-50">

      {/* ── Top navigation bar ──────────────────────────────────────── */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Back to all cases */}
            <a
              href="/"
              className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
            >
              ← All Cases
            </a>
            <span className="text-gray-200">/</span>
            {/* Case title number */}
            <h1 className="text-lg font-bold text-gray-900">{titleNumber}</h1>
          </div>

          {/* Upload + doc count */}
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">
              {docCount} document{docCount !== 1 ? 's' : ''}
            </span>
            <a
              href={`/case/${titleNumber}/upload`}
              className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              + Upload Document
            </a>
          </div>
        </div>
      </div>

      {/* ── Main content ────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-6 py-8">

        {/* Case summary row */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-1">Case Tools</h2>
          <p className="text-sm text-gray-400">
            Select a tool to work on this case
          </p>
        </div>

        {/* Tool cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tools.map((tool) => {
            const colors = colorMap[tool.color]

            return (
              <div
                key={tool.id}
                onClick={() => tool.available && router.push(tool.path)}
                className={`
                  relative rounded-xl border p-6 transition-all duration-150
                  ${tool.available
                    ? `cursor-pointer ${colors.bg} ${colors.border} ${colors.hover} hover:shadow-md`
                    : 'cursor-default bg-gray-50 border-gray-200 opacity-60'
                  }
                `}
              >
                {/* Coming soon badge */}
                {!tool.available && (
                  <span className="absolute top-3 right-3 text-xs bg-gray-200 text-gray-500 px-2 py-0.5 rounded-full font-medium">
                    Coming soon
                  </span>
                )}

                {/* Tool icon */}
                <div className={`w-10 h-10 rounded-lg ${colors.icon} flex items-center justify-center text-xl mb-4`}>
                  {tool.icon}
                </div>

                {/* Tool name and description */}
                <h3 className="font-semibold text-gray-900 mb-1">{tool.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  {tool.description}
                </p>

                {/* Arrow shown only for available tools */}
                {tool.available && (
                  <div className="mt-4 flex items-center text-sm font-medium text-gray-600">
                    Open
                    <span className="ml-1">→</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Document list preview */}
        {docCount > 0 && (
          <div className="mt-10">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
              Documents in this case
            </h3>
            <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
              {caseData.documents.map((doc) => (
                <div key={doc.id} className="px-4 py-3 flex items-center justify-between group hover:bg-gray-50 transition-colors">
                  <div className="flex items-center gap-3">
                    {/* Doc type badge */}
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-medium">
                      {doc.doc_type}
                    </span>
                    <span className="text-sm text-gray-700 truncate max-w-xs">
                      {doc.filename}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-gray-400">
                      {new Date(doc.uploaded_at).toLocaleDateString('en-GB')}
                    </span>
                    <button
                      onClick={() => handleDeleteDocument(doc.id)}
                      className="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-50"
                      title="Delete document"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state if no documents uploaded yet */}
        {docCount === 0 && (
          <div className="mt-10 text-center py-12 bg-white rounded-xl border border-dashed border-gray-300">
            <p className="text-gray-400 text-sm mb-3">No documents uploaded yet</p>
            <a
              href={`/case/${titleNumber}/upload`}
              className="text-blue-600 text-sm font-medium hover:underline"
            >
              Upload your first document →
            </a>
          </div>
        )}
      </div>
    </div>
  )
}