function SourceCitation({ source }) {
  return (
    <div className="source-citation">
      <div className="source-header">
        <span className="source-filename">{source.filename}</span>
        {source.page !== null && (
          <span className="source-page">Page {source.page}</span>
        )}
        <span className="source-score">{source.relevance_score}</span>
      </div>
      <div className="source-excerpt">{source.excerpt}</div>
    </div>
  )
}

export default SourceCitation