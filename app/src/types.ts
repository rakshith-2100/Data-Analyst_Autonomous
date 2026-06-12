// Shared types for the prototype UI. These intentionally mirror the backend
// schemas in ../../README.md (Profile, ColumnProfile, Task) so that wiring the
// real engine later is a swap, not a rewrite.

export type Screen =
  | 'upload'
  | 'processing'
  | 'fork'
  | 'chat'
  | 'report-builder'
  | 'report'

export interface ColumnProfile {
  name: string
  dtype: string
  nNull: number
  nUnique: number
  samples: (string | number)[]
  issue?: string // e.g. "numeric-looking but contains blank strings"
}

export interface Profile {
  fileName: string
  nRows: number
  nCols: number
  columns: ColumnProfile[]
}

export interface ChartSpec {
  kind: 'bar' | 'pie' | 'line'
  title: string
  data: { label: string; value: number }[]
  unit?: string
}

// A structured table parsed from a generated CSV (backend).
export interface TableData {
  name: string
  columns: string[]
  rows: (string | number | null)[][]
  totalRows: number
  truncated: boolean
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  chart?: ChartSpec // structured chart (mock/report path)
  images?: { name: string; url: string }[] // server-rendered chart PNGs (backend)
  tables?: TableData[] // structured tables from generated CSVs (backend)
  pending?: boolean // assistant message still "thinking"
}

// One row in the report builder checklist.
export interface ReportItem {
  id: string
  label: string
  kind: 'chart' | 'stat'
  selected: boolean
}

// One rendered section of a generated report.
export interface ReportSection {
  id: string
  title: string
  prose: string
  chart?: ChartSpec
  stat?: { value: string; caption: string }
}
