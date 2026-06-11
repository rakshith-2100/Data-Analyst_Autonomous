import { useEffect, useState } from 'react'

const STEPS = [
  'Reading CSV…',
  'Inferring column types…',
  'Profiling 21 columns…',
  'Flagging messy columns (TotalCharges)…',
  'Building data profile…',
]

// Fakes the profiling pass with a stepped animation, then calls onDone.
// In the real app this screen waits on profiler.py / the backend.
export default function ProcessingScreen({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (step >= STEPS.length) {
      const t = setTimeout(onDone, 450)
      return () => clearTimeout(t)
    }
    const t = setTimeout(() => setStep((s) => s + 1), 600)
    return () => clearTimeout(t)
  }, [step, onDone])

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
