import { useState } from 'react'
import type { Profile, ReportItem } from '../types'
import { REPORT_CHECKLIST } from '../mock'
import ProfileStrip from './ProfileStrip'

export default function ReportBuilder({
  profile,
  onGenerate,
}: {
  profile: Profile
  onGenerate: (items: ReportItem[]) => void
}) {
  const [items, setItems] = useState<ReportItem[]>(REPORT_CHECKLIST)
  const selectedCount = items.filter((i) => i.selected).length

  const toggle = (id: string) =>
    setItems((arr) => arr.map((i) => (i.id === id ? { ...i, selected: !i.selected } : i)))

  return (
    <div className="builder fade-in">
      <ProfileStrip profile={profile} />
      <h2>Build your report</h2>
      <p className="sub">Pick the charts and stats to include. Refine the prose afterwards in chat.</p>

      {items.map((it) => (
        <div className={`check ${it.selected ? 'on' : ''}`} key={it.id} onClick={() => toggle(it.id)}>
          <span className="box">{it.selected ? '✓' : ''}</span>
          <span className="label">{it.label}</span>
          <span className="kind">{it.kind}</span>
        </div>
      ))}

      <button
        className="btn"
        style={{ marginTop: 14, width: '100%' }}
        disabled={selectedCount === 0}
        onClick={() => onGenerate(items)}
      >
        Generate report ({selectedCount} {selectedCount === 1 ? 'item' : 'items'})
      </button>
    </div>
  )
}
