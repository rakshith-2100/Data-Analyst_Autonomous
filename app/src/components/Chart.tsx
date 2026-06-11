// Dependency-free chart renderer. Bar = CSS bars, pie = SVG arcs,
// line = SVG polyline. Good enough for a prototype; swap for a real chart
// lib (or server-rendered matplotlib PNGs) when wiring the backend.
import type { ChartSpec } from '../types'

const PIE_COLORS = ['#7c6cff', '#34d399', '#fbbf24', '#fb7185', '#38bdf8']

function fmt(v: number, unit?: string) {
  const n = Number.isInteger(v) ? v.toString() : v.toFixed(1)
  if (unit === '$') return `$${n}`
  if (unit === '%') return `${n}%`
  return n
}

export default function Chart({ spec }: { spec: ChartSpec }) {
  return (
    <div className="chart fade-in">
      <div className="title">{spec.title}</div>
      {spec.kind === 'bar' && <BarChart spec={spec} />}
      {spec.kind === 'pie' && <PieChart spec={spec} />}
      {spec.kind === 'line' && <LineChart spec={spec} />}
    </div>
  )
}

function BarChart({ spec }: { spec: ChartSpec }) {
  const max = Math.max(...spec.data.map((d) => d.value), 1)
  return (
    <div>
      {spec.data.map((d) => (
        <div className="barrow" key={d.label}>
          <span className="lab">{d.label}</span>
          <span className="track">
            <span className="fill" style={{ width: `${(d.value / max) * 100}%` }} />
          </span>
          <span className="val">{fmt(d.value, spec.unit)}</span>
        </div>
      ))}
    </div>
  )
}

function PieChart({ spec }: { spec: ChartSpec }) {
  const total = spec.data.reduce((s, d) => s + d.value, 0) || 1
  let acc = 0
  const r = 52
  const c = 60
  const segs = spec.data.map((d, i) => {
    const start = (acc / total) * 2 * Math.PI
    acc += d.value
    const end = (acc / total) * 2 * Math.PI
    const large = end - start > Math.PI ? 1 : 0
    const x1 = c + r * Math.sin(start)
    const y1 = c - r * Math.cos(start)
    const x2 = c + r * Math.sin(end)
    const y2 = c - r * Math.cos(end)
    return {
      d: `M${c},${c} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z`,
      color: PIE_COLORS[i % PIE_COLORS.length],
      label: d.label,
      value: d.value,
    }
  })
  return (
    <div className="chart-flex">
      <svg width="120" height="120" viewBox="0 0 120 120">
        {segs.map((s) => (
          <path key={s.label} d={s.d} fill={s.color} stroke="var(--bg)" strokeWidth="1.5" />
        ))}
      </svg>
      <div className="legend">
        {segs.map((s) => (
          <div className="row" key={s.label}>
            <span className="sw" style={{ background: s.color }} />
            <span>{s.label}</span>
            <span className="lv">{fmt(s.value, spec.unit)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function LineChart({ spec }: { spec: ChartSpec }) {
  const w = 360
  const h = 120
  const pad = 10
  const max = Math.max(...spec.data.map((d) => d.value), 1)
  const step = (w - pad * 2) / Math.max(spec.data.length - 1, 1)
  const pts = spec.data.map((d, i) => {
    const x = pad + i * step
    const y = h - pad - (d.value / max) * (h - pad * 2)
    return `${x},${y}`
  })
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <polyline points={pts.join(' ')} fill="none" stroke="var(--accent-2)" strokeWidth="2.5" />
      {spec.data.map((d, i) => {
        const x = pad + i * step
        const y = h - pad - (d.value / max) * (h - pad * 2)
        return <circle key={d.label} cx={x} cy={y} r="3.5" fill="var(--accent)" />
      })}
    </svg>
  )
}
