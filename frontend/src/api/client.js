import axios from 'axios'

// In production (Cloudflare Pages), VITE_API_URL points to the Koyeb backend
// e.g. "https://your-app-xxxx.koyeb.app/api"
// In local dev, Vite's proxy handles /api → localhost:8000, so we just use "/api"
const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 180000, // 3 minutes for long LLM calls
})

// ── Upload ────────────────────────────────────────────────────────
export async function uploadFile(file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  const res = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000, // 5 min for very large files
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) {
        onProgress(Math.round((evt.loaded * 100) / evt.total))
      }
    },
  })
  return res.data
}

// ── Chat ──────────────────────────────────────────────────────────
export async function sendMessage(sessionId, question, chatHistory = [], persona = 'general') {
  const res = await api.post('/chat', { sessionId, question, chatHistory, persona })
  return res.data
}

// ── Insights (dedicated — always runs insights_generator node) ────
export async function getInsights(sessionId, question, persona = 'general') {
  const res = await api.post('/insights', { sessionId, question, persona })
  return res.data
}

// ── Cleaning ──────────────────────────────────────────────────────
export async function getCleanReport(sessionId) {
  const res = await api.get('/clean/report', { params: { sessionId } })
  return res.data
}

export async function applyClean(sessionId, options) {
  const res = await api.post('/clean', { sessionId, options })
  return res.data
}

export async function downloadCleaned(sessionId) {
  const res = await api.get('/clean/download', {
    params: { sessionId },
    responseType: 'blob',
  })
  // Trigger browser download
  const url = window.URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = 'cleaned_data.csv'
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

// ── Health ────────────────────────────────────────────────────────
export async function checkHealth() {
  const res = await api.get('/health')
  return res.data
}

// ── Traces (Observability) ────────────────────────────────────────
export async function getTraces(limit = 50) {
  const res = await api.get('/traces', { params: { limit } })
  return res.data
}

export async function getTraceDetail(traceId) {
  const res = await api.get(`/traces/${traceId}`)
  return res.data
}

export async function clearTraces() {
  const res = await api.delete('/traces')
  return res.data
}
