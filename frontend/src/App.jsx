import { useState } from 'react'
import ChatPanel from './components/ChatPanel.jsx'
import DocumentPanel from './components/DocumentPanel.jsx'

function App() {
  const [documents, setDocuments] = useState([])
  const [isUploading, setIsUploading] = useState(false)

  const handleUpload = async (file) => {
    setIsUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/ingest', {
        method: 'POST',
        body: formData,
      })

      if (response.ok) {
        const result = await response.json()
        setDocuments(prev => [...prev, result])
      }
    } catch (error) {
      console.error('Upload failed:', error)
    } finally {
      setIsUploading(false)
    }
  }

  const handleDelete = async (docId) => {
    try {
      const response = await fetch(`/documents/${docId}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        setDocuments(prev => prev.filter(d => d.document_id !== docId))
      }
    } catch (error) {
      console.error('Delete failed:', error)
    }
  }

  const handleRefreshDocuments = async () => {
    try {
      const response = await fetch('/documents')
      if (response.ok) {
        const result = await response.json()
        setDocuments(result.documents || [])
      }
    } catch (error) {
      console.error('Refresh failed:', error)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>RAG Swarm</h1>
        <p>AI-powered document Q&A system</p>
      </header>

      <main className="app-main">
        <DocumentPanel
          documents={documents}
          onUpload={handleUpload}
          onDelete={handleDelete}
          isUploading={isUploading}
          onRefresh={handleRefreshDocuments}
        />
        <ChatPanel documents={documents} />
      </main>
    </div>
  )
}

export default App