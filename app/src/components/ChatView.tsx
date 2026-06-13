import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, Profile } from '../types'
import { nextId, suggestQuestions } from '../suggest'
import { artifactUrl, sendChat } from '../api'
import ProfileStrip from './ProfileStrip'
import { ChartImage, DataTable } from './Artifacts'

export default function ChatView({
  profile,
  sessionId,
  initialMessages = [],
  onSent,
}: {
  profile: Profile
  sessionId: string
  initialMessages?: ChatMessage[]
  onSent?: () => void
}) {
  const suggestions = suggestQuestions(profile)
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function ask(question: string) {
    const text = question.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)

    const userMsg: ChatMessage = { id: nextId('msg'), role: 'user', text }
    const pending: ChatMessage = { id: nextId('msg'), role: 'assistant', text: '', pending: true }
    setMessages((m) => [...m, userMsg, pending])

    try {
      const res = await sendChat(sessionId, text)
      const reply: ChatMessage = {
        id: pending.id,
        role: 'assistant',
        text: res.answer,
        images: res.images.map((n) => ({ name: n, url: artifactUrl(sessionId, n) })),
        tables: res.tables,
      }
      setMessages((m) => m.map((msg) => (msg.id === pending.id ? reply : msg)))
    } catch (e) {
      const err: ChatMessage = {
        id: pending.id,
        role: 'assistant',
        text: `⚠ ${(e as Error).message}. Is the backend running? (uvicorn src.api:app)`,
      }
      setMessages((m) => m.map((msg) => (msg.id === pending.id ? err : msg)))
    } finally {
      setBusy(false)
      onSent?.()
    }
  }

  return (
    <div className="chat-wrap fade-in">
      <ProfileStrip profile={profile} />

      <div className="messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <h2>What do you want to know about {profile.fileName}?</h2>
            <p>Ask in plain language — pick a starter or type your own.</p>
            <div className="starter-row">
              {suggestions.map((q) => (
                <button key={q} className="starter" onClick={() => ask(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div className={`msg ${m.role}`} key={m.id}>
            <div className="avatar">{m.role === 'user' ? '🧑' : '◆'}</div>
            <div className="bubble">
              {m.pending ? (
                <span className="typing">
                  <span /> <span /> <span />
                </span>
              ) : (
                <>
                  {m.text && <div className="answer-text">{m.text}</div>}
                  {m.images?.map((img) => (
                    <ChartImage key={img.name} name={img.name} url={img.url} />
                  ))}
                  {m.tables?.map((t) => (
                    <DataTable key={t.name} table={t} downloadUrl={artifactUrl(sessionId, t.name)} />
                  ))}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div className="composer">
        <div className="composer-field">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && ask(input)}
            placeholder="Ask about your data…  e.g. an average by category, or a bar chart"
          />
          <button
            className="send-btn"
            disabled={busy || !input.trim()}
            onClick={() => ask(input)}
            aria-label="Send"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M12 19V5M12 5l-6 6M12 5l6 6"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        <div className="composer-hint">
          Answers are computed from your data with Python — charts and tables included.
        </div>
      </div>
    </div>
  )
}
