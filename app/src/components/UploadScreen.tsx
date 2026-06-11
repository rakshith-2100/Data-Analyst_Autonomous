import { useState } from 'react'

export default function UploadScreen({ onLoad }: { onLoad: (fileName: string) => void }) {
  const [drag, setDrag] = useState(false)

  return (
    <div className="center-stage fade-in">
      <h1>Talk to your data.</h1>
      <p className="sub">
        Upload a CSV, then chat with it or generate a report — answers and charts come
        from real computation, not guesswork.
      </p>

      <div
        className={`dropzone ${drag ? 'drag' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDrag(false)
          const f = e.dataTransfer.files[0]
          onLoad(f ? f.name : 'uploaded.csv')
        }}
        onClick={() => onLoad('uploaded.csv')}
      >
        <div className="icon">📄</div>
        <div className="big">Drop a CSV here, or click to browse</div>
        <div className="hint">Max 200 MB · first row treated as headers</div>
      </div>

      <div className="or">— or —</div>
      <button className="btn" onClick={() => onLoad('telco_churn.csv')}>
        Try the Telco Churn sample
      </button>
    </div>
  )
}
