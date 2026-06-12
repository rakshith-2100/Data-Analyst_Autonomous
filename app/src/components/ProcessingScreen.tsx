import { useEffect, useState } from 'react'

const STEPS = [
  'Uploading CSV…',
  'Inferring column types…',
  'Profiling columns…',
  'Flagging messy columns…',
  'Building data profile…',
]

// Visual-only: animates the profiling steps while App awaits the backend.
// App switches screens when the real upload + profile resolves.
export default function ProcessingScreen() {
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (step >= STEPS.length) return
    const t = setTimeout(() => setStep((s) => s + 1), 500)
    return () => clearTimeout(t)
  }, [step])

  const pct = Math.min((step / STEPS.length) * 100, 100)

  return (
    <div className="center-stage fade-in">
      <h1 style={{ fontSize: 28 }}>Profiling your data…</h1>
      <div className="proc card" style={{ padding: '10px 6px', marginTop: 18 }}>
        {STEPS.map((label, i) => {
          const state = i < step ? 'done' : i === step ? 'active' : ''
          return (
            <div className={`proc-row ${state}`} key={label}>
              <span className={`tick ${i === step ? 'spin' : ''}`}>
                {i < step ? '✓' : i === step ? '◠' : '○'}
              </span>
              {label}
            </div>
          )
        })}
        <div style={{ padding: '0 16px 14px' }}>
          <div className="bar">
            <div style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
    </div>
  )
}
