import { useRef, useState } from 'react'

export default function UploadScreen({
  onUpload,
  onSample,
}: {
  onUpload: (file: File) => void
  onSample: () => void
}) {
  const [drag, setDrag] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="center-stage fade-in">
      <h1>Talk to your data.</h1>
      <p className="sub">
        Upload a CSV, then chat with it — answers and charts come from real computation,
        not guesswork.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onUpload(f)
        }}
      />

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
          if (f) onUpload(f)
        }}
        onClick={() => inputRef.current?.click()}
      >
        <div className="icon">📄</div>
        <div className="big">Drop a CSV here, or click to browse</div>
        <div className="hint">first row treated as headers</div>
      </div>

      <div className="or">— or —</div>
      <button className="btn" onClick={onSample}>
        Try the Telco Churn sample
      </button>
    </div>
  )
}
