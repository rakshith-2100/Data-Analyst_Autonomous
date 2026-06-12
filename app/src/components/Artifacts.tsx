import { useState } from 'react'
import type { TableData } from '../types'

async function downloadBlob(url: string, filename: string) {
  const blob = await (await fetch(url)).blob()
  const obj = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = obj
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(obj)
}

function useFlash(): [string, (m: string) => void] {
  const [msg, setMsg] = useState('')
  return [msg, (m: string) => {
    setMsg(m)
    window.setTimeout(() => setMsg(''), 1200)
  }]
}

export function ChartImage({ name, url }: { name: string; url: string }) {
  const [flash, doFlash] = useFlash()
  async function copy() {
    try {
      const blob = await (await fetch(url)).blob()
      await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
      doFlash('Copied')
    } catch {
      doFlash('Copy failed')
    }
  }
  return (
    <div className="artifact">
      <div className="artifact-bar">
        <span className="artifact-name">📊 {name}</span>
        <div className="artifact-actions">
          {flash && <span className="flash">{flash}</span>}
          <button className="ibtn" onClick={copy}>Copy</button>
          <button className="ibtn" onClick={() => downloadBlob(url, name)}>Download</button>
        </div>
      </div>
      <img className="artifact-img" src={url} alt={name} />
    </div>
  )
}

function toTSV(t: TableData): string {
  const head = t.columns.join('\t')
  const body = t.rows.map((r) => r.map((c) => (c == null ? '' : String(c))).join('\t')).join('\n')
  return `${head}\n${body}`
}

export function DataTable({ table, downloadUrl }: { table: TableData; downloadUrl: string }) {
  const [flash, doFlash] = useFlash()
  async function copy() {
    try {
      await navigator.clipboard.writeText(toTSV(table))
      doFlash('Copied')
    } catch {
      doFlash('Copy failed')
    }
  }
  const sub = table.truncated ? ` · first ${table.rows.length} of ${table.totalRows}` : ''
  return (
    <div className="artifact">
      <div className="artifact-bar">
        <span className="artifact-name">▦ {table.name}{sub}</span>
        <div className="artifact-actions">
          {flash && <span className="flash">{flash}</span>}
          <button className="ibtn" onClick={copy}>Copy</button>
          <button className="ibtn" onClick={() => downloadBlob(downloadUrl, table.name)}>CSV</button>
        </div>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>{table.columns.map((c, i) => <th key={i}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {table.rows.map((r, ri) => (
              <tr key={ri}>
                {r.map((c, ci) => <td key={ci}>{c == null ? '' : String(c)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
