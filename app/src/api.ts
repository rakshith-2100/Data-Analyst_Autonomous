// Real backend client (FastAPI in data_analyst/src/api.py). Replaces mock.ts for chat.
import type { Profile } from './types'

const API =
  ((import.meta as unknown as { env?: { VITE_API?: string } }).env?.VITE_API) ||
  'http://127.0.0.1:8000'

export interface ChatResponse {
  state: string
  answer: string
  artifacts: string[]
}

async function openSession(path: string, init?: RequestInit) {
  const r = await fetch(`${API}${path}`, init)
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!r.ok) throw new Error(`Request failed (${r.status})`)
  return r.json()
}

export function artifactUrl(sessionId: string, name: string): string {
  return `${API}/sessions/${sessionId}/artifacts/${name}`
}
