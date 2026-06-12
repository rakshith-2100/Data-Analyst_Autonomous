import { useEffect, useState } from 'react'
import type { ChatMessage, Profile, ReportSection, Screen } from './types'
import { buildReport } from './mock'
import type { SessionSummary } from './api'
import {
  artifactUrl,
  createSampleSession,
  createSession,
  getSessionInfo,
  listSessions,
  loadMessages,
} from './api'
import UploadScreen from './components/UploadScreen'
import ProcessingScreen from './components/ProcessingScreen'
import ForkScreen from './components/ForkScreen'
import ChatView from './components/ChatView'
import ReportBuilder from './components/ReportBuilder'
import ReportView from './components/ReportView'

// Screen state machine. Chat (incl. history) is wired to the real backend; the report
// fork is still the local mock (the backend report path isn't built yet).
export default function App() {
  const [screen, setScreen] = useState<Screen>('upload')
  const [profile, setProfile] = useState<Profile | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sections, setSections] = useState<ReportSection[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [initialMessages, setInitialMessages] = useState<ChatMessage[]>([])

  // Refresh the recent-chats list whenever we land on the upload screen.
  useEffect(() => {
    if (screen === 'upload') listSessions().then(setSessions).catch(() => setSessions([]))
  }, [screen])

  function reset() {
    setProfile(null)
    setSessionId(null)
    setSections([])
    setInitialMessages([])
    setScreen('upload')
  }

  // New session (upload / sample): profile, then fork.
  async function openSession(loader: Promise<{ sessionId: string; profile: Profile }>) {
    setScreen('processing')
    try {
      const res = await loader
      setSessionId(res.sessionId)
      setProfile(res.profile)
      setInitialMessages([])
      setScreen('fork')
    } catch (e) {
      alert(`${(e as Error).message}\n\nIs the backend running?  (uvicorn src.api:app)`)
      setScreen('upload')
    }
  }

  // Reopen a previous chat: load its profile + messages, jump straight into chat.
  async function openPast(sid: string) {
    setScreen('processing')
    try {
      const info = await getSessionInfo(sid)
      const stored = await loadMessages(sid)
      const msgs: ChatMessage[] = stored.map((m, i) => ({
        id: `${sid}-${i}`,
        role: m.role,
        text: m.text,
        images: m.images.map((n) => ({ name: n, url: artifactUrl(sid, n) })),
        tables: m.tables,
      }))
      setProfile(info.profile)
      setSessionId(sid)
      setInitialMessages(msgs)
      setScreen('chat')
    } catch (e) {
      alert(`${(e as Error).message}`)
      setScreen('upload')
    }
  }

  const showBack = screen !== 'upload' && screen !== 'processing'

  return (
    <div className="app">
      <div className="topbar">
        <div className="brand">
          <span className="dot" />
          CSV Data Analyst <small>· prototype</small>
        </div>
        <div className="spacer" />
        {profile && screen !== 'upload' && screen !== 'processing' && (
          <span className="pill">
            <span className="file">{profile.fileName}</span> loaded
          </span>
        )}
        {showBack && (
          <button className="btn-ghost" onClick={() => setScreen('fork')}>
            ← Menu
          </button>
        )}
        {screen !== 'upload' && (
          <button className="btn-ghost" onClick={reset}>
            New file
          </button>
        )}
      </div>

      {screen === 'upload' && (
        <UploadScreen
          onUpload={(file) => openSession(createSession(file))}
          onSample={() => openSession(createSampleSession())}
          sessions={sessions}
          onOpen={openPast}
        />
      )}

      {screen === 'processing' && <ProcessingScreen />}

      {screen === 'fork' && profile && (
        <ForkScreen
          profile={profile}
          onChat={() => setScreen('chat')}
          onReport={() => setScreen('report-builder')}
        />
      )}

      {screen === 'chat' && profile && sessionId && (
        <ChatView
          key={sessionId}
          profile={profile}
          sessionId={sessionId}
          initialMessages={initialMessages}
        />
      )}

      {screen === 'report-builder' && profile && (
        <ReportBuilder
          profile={profile}
          onGenerate={(items) => {
            setSections(buildReport(items))
            setScreen('report')
          }}
        />
      )}

      {screen === 'report' && profile && <ReportView profile={profile} sections={sections} />}
    </div>
  )
}
