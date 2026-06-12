import { useState } from 'react'
import type { Profile, ReportSection, Screen } from './types'
import { buildReport } from './mock'
import { createSampleSession, createSession } from './api'
import UploadScreen from './components/UploadScreen'
import ProcessingScreen from './components/ProcessingScreen'
import ForkScreen from './components/ForkScreen'
import ChatView from './components/ChatView'
import ReportBuilder from './components/ReportBuilder'
import ReportView from './components/ReportView'

// The whole prototype is a screen state machine — mirroring the backend's own
// state-machine design. Chat is wired to the real backend; the report fork is
// still the local mock (the backend report path isn't built yet).
export default function App() {
  const [screen, setScreen] = useState<Screen>('upload')
  const [profile, setProfile] = useState<Profile | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sections, setSections] = useState<ReportSection[]>([])

  function reset() {
    setProfile(null)
    setSessionId(null)
    setSections([])
    setScreen('upload')
  }

  // Drive the real upload: show processing, await the backend, then fork.
  async function openSession(loader: Promise<{ sessionId: string; profile: Profile }>) {
    setScreen('processing')
    try {
      const res = await loader
      setSessionId(res.sessionId)
      setProfile(res.profile)
      setScreen('fork')
    } catch (e) {
      alert(`${(e as Error).message}\n\nIs the backend running?  (uvicorn src.api:app)`)
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
        <ChatView profile={profile} sessionId={sessionId} />
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
