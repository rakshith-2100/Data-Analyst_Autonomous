import type { Profile } from '../types'
import ProfileStrip from './ProfileStrip'

export default function ForkScreen({
  profile,
  onChat,
  onReport,
}: {
  profile: Profile
  onChat: () => void
  onReport: () => void
}) {
  return (
    <div className="center-stage fade-in">
      <h1 style={{ fontSize: 30 }}>Ready. What now?</h1>
      <p className="sub">
        <span className="file" style={{ fontFamily: 'var(--mono)', color: 'var(--text-h)' }}>
          {profile.fileName}
        </span>{' '}
        is profiled and loaded.
      </p>
      <ProfileStrip profile={profile} />

      <div className="fork-grid">
        <div className="card fork-card" onClick={onChat}>
          <div className="emoji">💬</div>
          <h3>Chat with the data</h3>
          <p>
            Ask anything in plain language. Get a computed answer plus a chart, and refine
            with follow-ups like “now show it as a pie”.
          </p>
          <div className="go">Start chatting →</div>
        </div>

        <div className="card fork-card" onClick={onReport}>
          <div className="emoji">📊</div>
          <h3>Generate a report</h3>
          <p>
            Pick the charts and stats you want from a checklist and get a written analysis
            you can then refine in chat.
          </p>
          <div className="go">Build a report →</div>
        </div>
      </div>
    </div>
  )
}
