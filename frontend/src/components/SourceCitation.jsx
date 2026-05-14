import './SourceCitation.css'

function SourceCitation({ source }) {
  const scorePct = Math.round((source.relevance_score || 0) * 100)
  const isVerified = source.verified !== false

  return (
    <div className="source-card">
      <div className="source-card-header">
        <div className="source-meta">
          <span className="source-filename">{source.filename}</span>
          {source.page !== null && source.page !== undefined && (
            <span className="source-page">p.{source.page}</span>
          )}
          <span className={`source-badge ${isVerified ? 'verified' : 'unverified'}`}>
            {isVerified ? '✓' : '⚠'}
          </span>
        </div>
        <span className="source-score">{scorePct}%</span>
      </div>
      <div className="source-excerpt">{source.excerpt}</div>
    </div>
  )
}

export default SourceCitation