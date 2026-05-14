import { useState, useEffect, useRef } from 'react'
import ChatPanel from './components/ChatPanel.jsx'
import DocumentPanel from './components/DocumentPanel.jsx'

function App() {
  const [documents, setDocuments] = useState([])
  const [uploadProgress, setUploadProgress] = useState(null)
  const [error, setError] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const eventSourceRef = useRef(null)

  const handleUpload = async (file) => {
    setError(null)
    setIsUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/ingest', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) throw new Error('Upload failed')

      const { job_id } = await response.json()

      setUploadProgress({
        step: 'Starting',
        progress: 5,
        message: 'Document uploaded, processing...',
      })

      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/ingest/${job_id}/status`)
          if (!statusRes.ok) {
            clearInterval(pollInterval)
            setError('Connection lost to server')
            setUploadProgress(null)
            setIsUploading(false)
            return
          }
          const status = await statusRes.json()
          setUploadProgress({
            step: status.step || 'Processing',
            progress: status.progress || 0,
            message: status.message || 'Processing...',
          })

          if (status.status === 'completed') {
            clearInterval(pollInterval)
            setUploadProgress({ step: 'Complete', progress: 100, message: 'Document indexed!' })
            setTimeout(() => {
              setUploadProgress(null)
              setIsUploading(false)
            }, 2000)
            handleRefreshDocuments()
          } else if (status.status === 'failed') {
            clearInterval(pollInterval)
            setError(status.error || 'Upload failed')
            setUploadProgress(null)
            setIsUploading(false)
          }
        } catch {
          clearInterval(pollInterval)
          setError('Connection lost to server')
          setUploadProgress(null)
          setIsUploading(false)
        }
      }, 1000)

    } catch (error) {
      console.error('Upload failed:', error)
      setError(error.message)
      setIsUploading(false)
    }
  }

  const handleDelete = async (docId) => {
    try {
      const response = await fetch(`/api/documents/${docId}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        setDocuments(prev => prev.filter(d => d.id !== docId))
      }
    } catch (error) {
      console.error('Delete failed:', error)
    }
  }

  const handleRefreshDocuments = async () => {
    try {
      const response = await fetch('/api/documents')
      if (response.ok) {
        const result = await response.json()
        setDocuments(result.documents || [])
      }
    } catch (error) {
      console.error('Refresh failed:', error)
    }
  }

  useEffect(() => {
    handleRefreshDocuments()
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  return (
    <div className="app">
      {error && (
        <div className="error-banner">
          <span>Error: {error}</span>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}
      <header className="app-header">
        <h1>RAG Swarm</h1>
        <p>AI-powered document Q&A system</p>
      </header>

      <main className="app-main">
        <DocumentPanel
          documents={documents}
          onUpload={handleUpload}
          onDelete={handleDelete}
          uploadProgress={uploadProgress}
          uploadError={error}
          onRefresh={handleRefreshDocuments}
          isUploading={isUploading}
          onUploadStart={() => setIsUploading(true)}
          onUploadEnd={() => setIsUploading(false)}
        />
        <ChatPanel documents={documents} />
      </main>
    </div>
  )
}

export default App