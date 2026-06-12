import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, Profile } from '../types'
import { SUGGESTED_QUESTIONS, nextId } from '../mock'
import { artifactUrl, sendChat } from '../api'
import ProfileStrip from './ProfileStrip'
import { ChartImage, DataTable } from './Artifacts'

export default function ChatView({
  profile,
  sessionId,
  initialMessages = [],
}: {
  profile: Profile
  sessionId: string
  initialMessages?: ChatMessage[]
}) {
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
    }
  }

  return (
    <div className="chat-wrap fade-in">
      <ProfileStrip profile={profile} />

      <div className="messages">
        {messages.length === 0 && (
          <div className="starter-row">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button key={q} className="starter" onClick={() => ask(q)}>
                {q}
              </button>
            ))}
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
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask(input)}
          placeholder="Ask about your data…  e.g. a table of churn rate by contract type"
        />
        <button className="btn" disabled={busy || !input.trim()} onClick={() => ask(input)}>
          Send
        </button>
      </div>
    </div>
  )
}
