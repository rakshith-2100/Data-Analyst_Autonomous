import { useState } from 'react'
import type { Profile, ReportSection, Screen } from './types'
import { TELCO_PROFILE, buildReport } from './mock'
import UploadScreen from './components/UploadScreen'
import ProcessingScreen from './components/ProcessingScreen'
import ForkScreen from './components/ForkScreen'
import ChatView from './components/ChatView'
import ReportBuilder from './components/ReportBuilder'
import ReportView from './components/ReportView'

// The whole prototype is a screen state machine — mirroring the backend's own
// state-machine design. Each screen renders for one `Screen` value and calls a
// handler to transition to the next.
export default function App() {
  const [screen, setScreen] = useState<Screen>('upload')
  const [profile, setProfile] = useState<Profile | null>(null)
  const [sections, setSections] = useState<ReportSection[]>([])

  function reset() {
    setProfile(null)
    setSections([])
    setScreen('upload')
  }

  function loadFile(fileName: string) {
    // Prototype always loads the Telco profile, but keeps the dropped file's name.
    setProfile({ ...TELCO_PROFILE, fileName })
    setScreen('processing')
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

      {screen === 'upload' && <UploadScreen onLoad={loadFile} />}

      {screen === 'processing' && <ProcessingScreen onDone={() => setScreen('fork')} />}

      {screen === 'fork' && profile && (
        <ForkScreen
          profile={profile}
          onChat={() => setScreen('chat')}
          onReport={() => setScreen('report-builder')}
        />
      )}

      {screen === 'chat' && profile && <ChatView profile={profile} />}

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
