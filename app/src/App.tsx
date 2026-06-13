import { useEffect, useState } from 'react'
import type { ChatMessage, Profile } from './types'
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
import ChatView from './components/ChatView'
import Sidebar from './components/Sidebar'

type Loaded = { sid: string; profile: Profile; messages: ChatMessage[] }

// Hash routing: "#/" is the landing/upload, "#/c/<sid>" is a conversation.
// This gives every chat its own URL, so the browser back button works and a
// conversation can be deep-linked or reopened from the sidebar.
function useHashRoute(): string {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || '/')
  useEffect(() => {
    const on = () => setRoute(window.location.hash.slice(1) || '/')
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}
const navigate = (to: string) => {
  window.location.hash = to
}

export default function App() {
  const route = useHashRoute()
  const sid = route.startsWith('/c/') ? decodeURIComponent(route.slice(3)) : null

  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [error, setError] = useState('')

  const refreshSessions = () => listSessions().then(setSessions).catch(() => {})

  useEffect(() => {
    refreshSessions()
  }, [])

  // Whenever the URL points at a session we don't already hold, fetch its
  // profile + messages. Newly created sessions are pre-loaded, so this skips.
  useEffect(() => {
    if (!sid || loaded?.sid === sid) {
      if (!sid) setStatus('idle')
      return
    }
    let cancelled = false
    setStatus('loading')
    ;(async () => {
      try {
        const [info, stored] = await Promise.all([getSessionInfo(sid), loadMessages(sid)])
        if (cancelled) return
        const messages: ChatMessage[] = stored.map((m, i) => ({
          id: `${sid}-${i}`,
          role: m.role,
          text: m.text,
          images: m.images.map((n) => ({ name: n, url: artifactUrl(sid, n) })),
          tables: m.tables,
        }))
        setLoaded({ sid, profile: info.profile, messages })
        setStatus('idle')
      } catch (e) {
        if (cancelled) return
        setError((e as Error).message)
        setStatus('error')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [sid, loaded?.sid])

  // Create a session (upload or sample), then route into its conversation.
  async function start(loader: Promise<{ sessionId: string; profile: Profile }>) {
    setStatus('loading')
    try {
      const res = await loader
      setLoaded({ sid: res.sessionId, profile: res.profile, messages: [] })
      setStatus('idle')
      await refreshSessions()
      navigate(`/c/${res.sessionId}`)
    } catch (e) {
      setError((e as Error).message)
      setStatus('error')
    }
  }

  const showChat = !!sid && loaded?.sid === sid

  return (
    <div className="shell">
      <Sidebar
        sessions={sessions}
        activeSid={sid}
        onNew={() => navigate('/')}
        onOpen={(s) => navigate(`/c/${s}`)}
        onBrand={() => navigate('/')}
      />

      <main className="main">
        <div className="main-head">
          {showChat && loaded && (
            <span className="pill">
              <span className="file">{loaded.profile.fileName}</span> loaded
            </span>
          )}
        </div>

        <div className="main-body">
          {status === 'loading' && (
            <div className="center-stage">
              <div className="loader">Analyzing…</div>
            </div>
          )}

          {status === 'error' && (
            <div className="center-stage fade-in">
              <h1 style={{ fontSize: 26 }}>Something went wrong</h1>
              <p className="sub">⚠ {error}</p>
              <p className="sub" style={{ fontSize: 13, marginTop: -8 }}>
                Is the backend running? (uvicorn src.api:app)
              </p>
              <button className="btn" onClick={() => navigate('/')}>
                Back to start
              </button>
            </div>
          )}

          {status === 'idle' && !sid && (
            <UploadScreen
              onUpload={(file) => start(createSession(file))}
              onSample={() => start(createSampleSession())}
            />
          )}

          {status === 'idle' && showChat && loaded && (
            <ChatView
              key={loaded.sid}
              profile={loaded.profile}
              sessionId={loaded.sid}
              initialMessages={loaded.messages}
              onSent={refreshSessions}
            />
          )}
        </div>
      </main>
    </div>
  )
}
