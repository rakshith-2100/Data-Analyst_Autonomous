import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, Profile } from '../types'
import { SUGGESTED_QUESTIONS, makeAssistantMessage, nextId } from '../mock'
import ProfileStrip from './ProfileStrip'
import Chart from './Chart'

export default function ChatView({ profile }: { profile: Profile }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function ask(question: string) {
    const text = question.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)

    const userMsg: ChatMessage = { id: nextId('msg'), role: 'user', text }
    const pending: ChatMessage = { id: nextId('msg'), role: 'assistant', text: '', pending: true }
    setMessages((m) => [...m, userMsg, pending])

    // Fake the engine's compute-then-narrate latency.
    setTimeout(() => {
      const answer = makeAssistantMessage(text)
      setMessages((m) => m.map((msg) => (msg.id === pending.id ? answer : msg)))
      setBusy(false)
    }, 1100)
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
