import { useState, useRef } from 'react'

function DocumentPanel({ documents, onUpload, onDelete, isUploading, onRefresh }) {
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)

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
      onUpload(files[0])
    }
  }

  const handleFileSelect = (e) => {
    const files = e.target.files
    if (files.length > 0) {
      onUpload(files[0])
    }
  }

  return (
    <div className="document-panel">
      <h2>Documents</h2>

      <div
        className={`upload-zone ${isDragging ? 'dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        {isUploading ? (
          <p>Uploading...</p>
        ) : (
          <>
            <p>Drop files here or click to upload</p>
            <p className="upload-hint">PDF, DOCX, TXT, HTML, MD</p>
          </>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.html,.htm,.md"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

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
              <li key={doc.document_id} className="document-item">
                <div className="doc-info">
                  <span className="doc-filename">{doc.filename}</span>
                  <span className="doc-chunks">{doc.chunks_count} chunks</span>
                </div>
                <button
                  className="doc-delete"
                  onClick={() => onDelete(doc.document_id)}
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