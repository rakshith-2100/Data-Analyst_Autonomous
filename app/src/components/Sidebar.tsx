// Persistent left rail (ChatGPT-style): brand, "new analysis", recent chats.
import type { SessionSummary } from '../api'

export default function Sidebar({
  sessions,
  activeSid,
  onNew,
  onOpen,
  onBrand,
}: {
  sessions: SessionSummary[]
  activeSid: string | null
  onNew: () => void
  onOpen: (sid: string) => void
  onBrand: () => void
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand" onClick={onBrand} title="Home">
        <span className="logo-dot" />
        <span>Data Analyst</span>
      </div>

      <button className="new-chat" onClick={onNew}>
        <span>＋</span>
        <span>New analysis</span>
      </button>

      <div className="side-list">
        <div className="side-section-title">Recent</div>
        {sessions.length === 0 && <div className="side-empty">No chats yet</div>}
        {sessions.map((s) => (
          <button
            key={s.id}
            className={`side-item ${s.id === activeSid ? 'active' : ''}`}
            onClick={() => onOpen(s.id)}
            title={s.filename}
          >
            <span className="si-file">{s.filename}</span>
            <span className="si-msg">{s.last_user_message ?? 'New chat'}</span>
          </button>
        ))}
      </div>
    </aside>
  )
}
