import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, Profile } from '../types'
import { SUGGESTED_QUESTIONS, nextId } from '../mock'
import { artifactUrl, sendChat } from '../api'
import ProfileStrip from './ProfileStrip'
import Chart from './Chart'

export default function ChatView({
  profile,
  sessionId,
}: {
  profile: Profile
  sessionId: string
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
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
        imageUrl: res.artifacts[0] ? artifactUrl(sessionId, res.artifacts[0]) : undefined,
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
                  {m.text}
                  {m.imageUrl && (
                    <img
                      src={m.imageUrl}
                      alt="chart"
                      style={{ maxWidth: '100%', borderRadius: 8, marginTop: 10, display: 'block' }}
                    />
                  )}
                  {m.chart && <Chart spec={m.chart} />}
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
          placeholder="Ask about your data…  e.g. does contract type affect churn?"
        />
        <button className="btn" disabled={busy || !input.trim()} onClick={() => ask(input)}>
          Send
        </button>
      </div>
    </div>
  )
}
