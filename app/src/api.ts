// Real backend client (FastAPI in data_analyst/src/api.py). Replaces mock.ts for chat.
import type { Profile, TableData } from './types'

const API =
  ((import.meta as unknown as { env?: { VITE_API?: string } }).env?.VITE_API) ||
  'http://127.0.0.1:8000'

// Stable per-browser id so "previous chats" are scoped to this person.
function userId(): string {
  let id = localStorage.getItem('userId')
  if (!id) {
    id = crypto.randomUUID?.() ?? `u-${Date.now()}-${Math.random().toString(36).slice(2)}`
    localStorage.setItem('userId', id)
  }
  return id
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  return { 'X-User-Id': userId(), ...extra }
}

export interface ChatResponse {
  state: string
  answer: string
  images: string[]
  tables: TableData[]
}

export interface SessionSummary {
  id: string
  filename: string
  created_at: string
  message_count: number
  last_user_message: string | null
}

export interface StoredMessage {
  role: 'user' | 'assistant'
  text: string
  images: string[]
  tables: TableData[]
  code: string
  created_at: string
}

async function openSession(path: string, init?: RequestInit) {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: headers(init?.headers as Record<string, string> | undefined),
  })
  if (!r.ok) throw new Error(`Request failed (${r.status})`)
  const j = await r.json()
  return { sessionId: j.session_id as string, profile: j.profile as Profile }
}

export function createSession(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return openSession('/sessions', { method: 'POST', body: fd })
}

export function createSampleSession() {
  return openSession('/sessions/sample', { method: 'POST' })
}

export async function sendChat(sessionId: string, message: string): Promise<ChatResponse> {
  const r = await fetch(`${API}/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ message }),
  })
  if (!r.ok) throw new Error(`Request failed (${r.status})`)
  return r.json()
}

export async function listSessions(): Promise<SessionSummary[]> {
  const r = await fetch(`${API}/sessions`, { headers: headers() })
  if (!r.ok) throw new Error(`Request failed (${r.status})`)
  return r.json()
}

export async function getSessionInfo(
  sid: string,
): Promise<{ profile: Profile; filename: string; created_at: string }> {
  const r = await fetch(`${API}/sessions/${sid}`, { headers: headers() })
  if (!r.ok) throw new Error(`Request failed (${r.status})`)
  const j = await r.json()
  return { profile: j.profile, filename: j.filename, created_at: j.created_at }
}

export async function loadMessages(sid: string): Promise<StoredMessage[]> {
  const r = await fetch(`${API}/sessions/${sid}/messages`, { headers: headers() })
  if (!r.ok) throw new Error(`Request failed (${r.status})`)
  return r.json()
}

export function artifactUrl(sessionId: string, name: string): string {
  return `${API}/sessions/${sessionId}/artifacts/${name}`
}
