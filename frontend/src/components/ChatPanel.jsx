import { useState } from 'react'
import SourceCitation from './SourceCitation.jsx'

function formatContentWithCitations(content) {
  // Parse [filename:page] citations and convert to styled elements
  const citationRegex = /\[([^\]:]+):([^\]]+)\]/g

  const parts = []
  let lastIndex = 0
  let match

  const regex = new RegExp(citationRegex)
  while ((match = regex.exec(content)) !== null) {
    // Add text before the citation
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index))
    }

    // Add styled citation
    parts.push(
      <span key={match.index} className="inline-citation">
        [{match[1]}:{match[2]}]
      </span>
    )

    lastIndex = match.index + match[0].length
  }

  // Add remaining text
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex))
  }

  return parts
}


function ChatPanel({ documents }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [latency, setLatency] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    setLatency(null)

    try {
      const history = messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content,
      }))

      const response = await fetch(`/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input, history }),
      })

      if (response.ok) {
        const result = await response.json()

        const assistantMessage = {
          role: 'assistant',
          content: result.answer,
          sources: result.sources,
          latency: result.latency_ms,
        }

        setMessages(prev => [...prev, assistantMessage])
        setLatency(result.latency_ms)
      }
    } catch (error) {
      console.error('Chat failed:', error)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Error: Could not get response' },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask questions about your documents</p>
            {documents.length === 0 && (
              <p className="chat-empty-hint">Upload documents first to get started</p>
            )}
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`message message-${msg.role}`}>
            <div className="message-bubble">
              {formatContentWithCitations(msg.content)}
            </div>

            {msg.sources && msg.sources.length > 0 && (
              <div className="message-sources">
                <div className="sources-header">
                  <h4>Sources <span className="sources-count">{msg.sources.length}</span></h4>
                </div>
                <div className="sources-grid">
                  {msg.sources.map((source, sIdx) => (
                    <SourceCitation key={sIdx} source={source} />
                  ))}
                </div>
              </div>
            )}

            {msg.latency && (
              <div className="message-latency">
                Latency: retrieval {msg.latency.retrieval}ms, synthesis {msg.latency.synthesis}ms
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="message message-assistant">
            <div className="message-bubble thinking">
              <span className="thinking-dots">...</span>
              Processing
            </div>
          </div>
        )}
      </div>

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your documents..."
          disabled={isLoading || documents.length === 0}
        />
        <button type="submit" disabled={isLoading || !input.trim() || documents.length === 0}>
          Send
        </button>
      </form>
    </div>
  )
}

export default ChatPanel