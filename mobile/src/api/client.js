import axios from 'axios'

// Default dev IP addresses for local server connection (10.0.2.2 for Android Emulator, localhost for iOS/Web)
let currentApiBase = 'http://10.0.2.2:8000/api'

// Simple in-memory credential storage for mobile (can be wired to AsyncStorage if needed)
const credentials = {
  authToken: null,
  customLlmProvider: null,
  customLlmKey: null,
  customLlmModel: null,
}

export const setApiBaseUrl = (url) => {
  if (url) {
    currentApiBase = url.endsWith('/api') ? url : `${url}/api`
    api.defaults.baseURL = currentApiBase
  }
}

export const setAuthToken = (token) => {
  credentials.authToken = token
}

export const setCustomLlmCredentials = (provider, key, model) => {
  credentials.customLlmProvider = provider
  credentials.customLlmKey = key
  credentials.customLlmModel = model
}

export const clearCredentials = () => {
  credentials.authToken = null
  credentials.customLlmProvider = null
  credentials.customLlmKey = null
  credentials.customLlmModel = null
}

const api = axios.create({
  baseURL: currentApiBase,
  timeout: 60000, // 1 minute timeout for mobile
})

api.interceptors.request.use(
  (config) => {
    if (credentials.authToken) {
      config.headers.Authorization = `Bearer ${credentials.authToken}`
    }
    if (credentials.customLlmKey) {
      config.headers['X-LLM-Provider'] = credentials.customLlmProvider || 'groq'
      config.headers['X-LLM-API-Key'] = credentials.customLlmKey
      if (credentials.customLlmModel) {
        config.headers['X-LLM-Model'] = credentials.customLlmModel
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── Ingestion Endpoints ──────────────────────────────────────────
export async function uploadFileMobile(uri, name, type) {
  const form = new FormData()
  form.append('file', {
    uri,
    name: name || 'dataset.csv',
    type: type || 'text/csv',
  })
  const res = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function importDatasetURL(url) {
  const res = await api.post('/datasets/import', { url })
  return res.data
}

export async function getRateLimits() {
  const res = await api.get('/v3/llm/rate-limits')
  return res.data
}

export async function listDatasets() {
  const res = await api.get('/datasets')
  return res.data
}

export async function activateDataset(datasetId) {
  const res = await api.post(`/datasets/${datasetId}/activate`)
  return res.data
}

// ── AI Data Copilot Endpoints ─────────────────────────────────────
export async function sendCopilotQuery(sessionId, question, chatHistory = [], persona = 'general', debugMode = false) {
  const res = await api.post('/v3/chat/query', {
    sessionId,
    question,
    chatHistory,
    persona,
    debugMode,
  })
  return res.data
}

// ── AI Insights & Explainer Endpoints ─────────────────────────────
export async function generateInsights(sessionId, insightType = 'general', persona = 'general') {
  const res = await api.post('/v3/insights/generate', { sessionId, insightType, persona })
  return res.data
}

export async function generateExplanation(sessionId, aspect = 'general', persona = 'general') {
  const res = await api.post('/v3/explanation/explain', { sessionId, aspect, persona })
  return res.data
}
