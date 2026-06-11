// Compact summary of the loaded dataset profile, shown above chat/report.
import type { Profile } from '../types'

export default function ProfileStrip({ profile }: { profile: Profile }) {
  const flagged = profile.columns.filter((c) => c.issue)
  return (
    <div className="profile-strip">
      <span className="chip">
        <b>{profile.nRows.toLocaleString()}</b> rows
      </span>
      <span className="chip">
        <b>{profile.nCols}</b> cols
      </span>
      {flagged.map((c) => (
        <span className="chip warn" key={c.name} title={c.issue}>
          ⚠ {c.name}
        </span>
      ))}
    </div>
  )
}
