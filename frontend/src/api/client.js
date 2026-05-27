import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
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
export async function sendMessage(sessionId, question, chatHistory = []) {
  const res = await api.post('/chat', { sessionId, question, chatHistory })
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
