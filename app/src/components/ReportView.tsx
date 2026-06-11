import { useState } from 'react'
import type { Profile, ReportSection } from '../types'
import Chart from './Chart'
import ProfileStrip from './ProfileStrip'

export default function ReportView({
  profile,
  sections,
}: {
  profile: Profile
  sections: ReportSection[]
}) {
  const [refine, setRefine] = useState('')
  const [note, setNote] = useState<string | null>(null)

  function submitRefine() {
    const t = refine.trim()
    if (!t) return
    // Prototype: a refine request just acknowledges. The real app re-enters the
    // chat engine (CLASSIFY → refine → PLAN_REPORT) and updates sections in place.
    setNote(`Refinement queued: “${t}”. (In the live app this updates the report in place.)`)
    setRefine('')
  }

  return (
    <div className="report fade-in">
      <ProfileStrip profile={profile} />

      <div className="report-head">
        <h1>Churn analysis report</h1>
        <div className="meta">
          Generated from <span style={{ fontFamily: 'var(--mono)' }}>{profile.fileName}</span> ·{' '}
          {sections.length} sections
        </div>
      </div>

      <div className="exec">
        <strong style={{ color: 'var(--text-h)' }}>Executive summary.</strong> About a
        quarter of customers churn, and contract type is the dominant driver — month-to-month
        plans churn an order of magnitude more than two-year ones. Higher monthly charges and
        electronic-check payment are secondary risk signals.
      </div>

      {sections.map((s) => (
        <div className="section" key={s.id}>
          <h3>{s.title}</h3>
          <p>{s.prose}</p>
          {s.stat && (
            <div className="statbox">
              <span className="v">{s.stat.value}</span>
              <span className="c">{s.stat.caption}</span>
            </div>
          )}
          {s.chart && <Chart spec={s.chart} />}
        </div>
      ))}

      {note && <div className="refine-hint" style={{ color: 'var(--accent-2)' }}>{note}</div>}

      <div className="refine-bar">
        <input
          value={refine}
          onChange={(e) => setRefine(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submitRefine()}
          placeholder="Refine the report…  e.g. drop the pie, add a tenure forecast"
        />
        <button className="btn" onClick={submitRefine} disabled={!refine.trim()}>
          Refine
        </button>
      </div>
      <div className="refine-hint">Refinements loop back through the chat engine.</div>
    </div>
  )
}
