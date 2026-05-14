import { useState, useRef } from 'react'

const STEPS = ['Parsing', 'Chunking', 'Embedding', 'Storing', 'Finalizing']

function DocumentPanel({ documents, onUpload, onDelete, uploadProgress, uploadError, onRefresh, isUploading, onUploadStart, onUploadEnd }) {
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)

  const clearError = () => {
    onUploadEnd()
    onRefresh()
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      onUploadStart()
      onUpload(files[0])
    }
  }

  const handleFileSelect = (e) => {
    const files = e.target.files
    if (files.length > 0) {
      onUploadStart()
      onUpload(files[0])
    }
  }

  const getStepStatus = (stepName) => {
    if (!uploadProgress) return 'idle'
    const currentStep = uploadProgress.step?.toLowerCase()
    const stepIndex = STEPS.findIndex(s => s.toLowerCase() === currentStep)
    const thisIndex = STEPS.findIndex(s => s.toLowerCase() === stepName.toLowerCase())

    if (uploadProgress.error) return 'error'
    if (thisIndex < stepIndex) return 'done'
    if (thisIndex === stepIndex) return 'active'
    return 'pending'
  }

  return (
    <div className="document-panel">
      <h2>Documents</h2>

      {uploadError ? (
        <div className="upload-error">
          <span className="error-icon">!</span>
          <span className="error-text">{uploadError}</span>
          <button className="error-dismiss" onClick={clearError}>Retry</button>
        </div>
      ) : isUploading && !uploadProgress ? (
        <div className="upload-progress depositing">
          <div className="deposit-spinner" />
          <p className="deposit-text">Depositing file...</p>
        </div>
      ) : uploadProgress ? (
        <div className="upload-progress">
          <div className="progress-header">
            <span className="progress-step">{uploadProgress.step}</span>
            <span className="progress-pct">{uploadProgress.progress}%</span>
          </div>

          <div className="progress-steps">
            {STEPS.map((step, idx) => (
              <div key={step} className={`step step-${getStepStatus(step)}`}>
                <div className="step-icon">
                  {getStepStatus(step) === 'done' ? '✓' :
                   getStepStatus(step) === 'active' ? <span className="pulse-dot" /> :
                   getStepStatus(step) === 'error' ? '!' : idx + 1}
                </div>
                <span className="step-label">{step}</span>
              </div>
            ))}
          </div>

          <div className="progress-bar">
            <div
              className={`progress-fill ${uploadProgress.error ? 'error' : ''}`}
              style={{ width: `${uploadProgress.progress}%` }}
            />
          </div>

          <p className="progress-message">
            {uploadProgress.error ? uploadProgress.message : uploadProgress.message}
          </p>
        </div>
      ) : (
        <div
          className={`upload-zone ${isDragging ? 'dragging' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <p>Drop files here or click to upload</p>
          <p className="upload-hint">PDF, DOCX, TXT, HTML, MD</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.html,.htm,.md"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </div>
      )}

      <button className="refresh-btn" onClick={onRefresh}>
        Refresh
      </button>

      <div className="document-list">
        <h3>Indexed Files ({documents.length})</h3>
        {documents.length === 0 ? (
          <p className="no-docs">No documents indexed yet</p>
        ) : (
          <ul>
            {documents.map((doc) => (
              <li key={doc.id} className="document-item">
                <div className="doc-info">
                  <span className="doc-filename">{doc.filename}</span>
                  <span className="doc-chunks">{doc.chunks_count} chunks</span>
                </div>
                <button
                  className="doc-delete"
                  onClick={() => onDelete(doc.id)}
                  title="Delete"
                >
                  X
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default DocumentPanel