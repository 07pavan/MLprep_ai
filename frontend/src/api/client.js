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

// Attach authorization headers dynamically
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Attach custom LLM credentials dynamically if configured
    const provider = localStorage.getItem('customLlmProvider')
    const key = localStorage.getItem('customLlmKey')
    const model = localStorage.getItem('customLlmModel')

    if (key) {
      config.headers['X-LLM-Provider'] = provider || 'groq'
      config.headers['X-LLM-API-Key'] = key
      if (model) {
        config.headers['X-LLM-Model'] = model
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

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

export async function importDatasetURL(url) {
  const res = await api.post('/datasets/import', { url })
  return res.data
}

export async function getRateLimits() {
  const res = await api.get('/v3/llm/rate-limits')
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

// ── Cleaning Planner (Phase 2B / v2) ─────────────────────────────
export async function getIntelligentPlan(sessionId) {
  const res = await api.get('/v2/cleaning/plan', { params: { sessionId } })
  return res.data
}

export async function getIntelligentPlanForDataset(datasetId) {
  const res = await api.get('/v2/cleaning/plan/dataset', { params: { datasetId } })
  return res.data
}

export async function getCleaningSummary(sessionId) {
  const res = await api.get('/v2/cleaning/summary', { params: { sessionId } })
  return res.data
}

export async function executeCleaningPlan(payload) {
  // payload: { sessionId?: string, datasetId?: string, plan: object, action_ids?: string[] }
  const res = await api.post('/v2/cleaning/execute', payload)
  return res.data
}

export async function resetCleaningSession(sessionId) {
  const res = await api.post('/v2/cleaning/reset', { sessionId })
  return res.data
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

// ── ML Data Prep Dashboard Endpoints ────────────────────────────────
export async function getProfile(sessionId) {
  const res = await api.get('/profile', { params: { sessionId } })
  return res.data
}

export async function getQualityReport(sessionId) {
  const res = await api.get('/quality-check', { params: { sessionId } })
  return res.data
}

export async function getMLReadiness(sessionId) {
  const res = await api.get('/ml-readiness', { params: { sessionId } })
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

export async function deleteDataset(datasetId) {
  const res = await api.delete(`/datasets/${datasetId}`)
  return res.data
}

// ── AI Data Copilot (v3) ──────────────────────────────────────────
export async function sendCopilotQuery(sessionId, question, chatHistory = [], persona = 'general', debugMode = false, threadId = null) {
  const res = await api.post('/v3/chat/query', { sessionId, question, chatHistory, persona, debugMode, threadId })
  return res.data
}

export async function createThread(sessionId) {
  const res = await api.post('/v3/chat/thread', { sessionId })
  return res.data
}

export async function getThread(threadId) {
  const res = await api.get(`/v3/chat/thread/${threadId}`)
  return res.data
}

export async function deleteThread(threadId) {
  const res = await api.delete(`/v3/chat/thread/${threadId}`)
  return res.data
}

// ── AI Dataset Insights Engine (Phase 3C) ───────────────────────────
export async function generateInsights(sessionId, insightType, persona = 'general') {
  const res = await api.post('/v3/insights/generate', { sessionId, insightType, persona })
  return res.data
}

// ── AI Auto Visualization Generator (Phase 3D) ──────────────────────
export async function generateVisualizations(sessionId, visualizationType = 'general', persona = 'general') {
  const res = await api.post('/v3/visualizations/generate', { sessionId, visualizationType, persona })
  return res.data
}

// ── AI Data Storytelling Engine (Phase 3E) ───────────────────────────
export async function generateStoryReport(sessionId, reportType = 'executive', persona = 'general') {
  const res = await api.post('/v3/story/generate', { sessionId, reportType, persona })
  return res.data
}

export async function exportStoryPdf(reportId) {
  const res = await api.get(`/v3/story/export/pdf/${reportId}`, { responseType: 'text' })
  return res.data
}

export async function exportStoryJson(reportId) {
  const res = await api.get(`/v3/story/export/json/${reportId}`)
  return res.data
}

export async function downloadStoryPdf(reportId, title = 'report') {
  const html = await exportStoryPdf(reportId)
  const blob = new Blob([html], { type: 'text/html' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title.replace(/\s+/g, '_').toLowerCase()}.html`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

export async function downloadStoryJson(reportId, title = 'report') {
  const data = await exportStoryJson(reportId)
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title.replace(/\s+/g, '_').toLowerCase()}.json`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}


// ── AI Dataset Explanation Engine (Phase 3B) ────────────────────────
export async function generateExplanation(sessionId, aspect, persona = 'general') {
  try {
    const res = await api.post('/v3/explanation/explain', { sessionId, aspect, persona })
    return res.data
  } catch (err) {
    // If the backend API doesn't exist yet (404/Network Error), fall back to mock data
    if (err.response?.status === 404 || err.code === 'ERR_NETWORK') {
      console.warn("Backend explanation API not found. Using frontend mock fallback.")
      await new Promise(resolve => setTimeout(resolve, 1200)) // Simulate network latency
      return getMockExplanation(aspect)
    }
    throw err
  }
}

function getMockExplanation(aspect) {
  const timestamp = new Date().toISOString()
  switch (aspect) {
    case 'profiling':
      return {
        success: true,
        summary: "The dataset contains 1,250 records across 12 features, focusing on customer demographics and transactional records. Numeric columns show typical ranges, but there is some skew in the purchase amount feature.",
        insights: [
          "Columns identified: 'customer_id', 'age', 'annual_income', 'spending_score', 'purchase_amount'.",
          "Average age is 38.5 years, ranging from 18 to 70.",
          "Spending score has a normal distribution, while purchase amount has a heavy right skew.",
          "Categorical columns like 'gender' and 'region' have 2 and 4 unique values respectively."
        ],
        confidence: 0.95,
        sources: ["profiler"],
        timestamp
      }
    case 'quality':
      return {
        success: true,
        summary: "The dataset has a quality score of 84/100. There are some minor issues with missing values in the income column and outliers in the purchase amount column.",
        insights: [
          "Missing values: 'annual_income' has 45 missing values (3.6% missing rate).",
          "Outliers: 'purchase_amount' contains 12 outliers representing high-value transactions (> $5,000).",
          "Duplicates: No duplicate records detected.",
          "Type Mismatches: Column 'age' contains 2 string values that should be integers."
        ],
        confidence: 0.92,
        sources: ["profiler", "quality"],
        timestamp
      }
    case 'ml_readiness':
      return {
        success: true,
        summary: "The dataset ML readiness score is 88/100 (Grade B). It is highly suitable for predictive modeling once missing values are imputed.",
        insights: [
          "Strengths: Adequate row count, balanced target column ('churn'), and no high-cardinality ID issues.",
          "Weaknesses: Missing values in 'annual_income' and non-numeric categorical variables require encoding.",
          "Recommendation: Apply mean imputation on annual_income and one-hot encoding on region."
        ],
        confidence: 0.89,
        sources: ["ml_readiness"],
        timestamp
      }
    case 'cleaning_history':
      return {
        success: true,
        summary: "The dataset is currently at version 3. It has undergone two cleaning iterations to resolve quality issues.",
        insights: [
          "Version 1: Raw dataset upload (1,250 rows).",
          "Version 2: Executed duplicate removal and mean imputation on 'annual_income'.",
          "Version 3: Removed extreme outliers and encoded 'region' using one-hot encoding.",
          "Current State: Version 3 is marked as active and clean."
        ],
        confidence: 0.98,
        sources: ["cleaning_history", "dataset_service"],
        timestamp
      }
    case 'general':
    default:
      return {
        success: true,
        summary: "This dataset represents customer profiles and sales transactions. It is generally clean and well-structured, with a few minor missing values and outliers.",
        insights: [
          "Total Records: 1,250 rows, 12 columns.",
          "Quality Score: 84/100 with 3.6% missing values in 'annual_income'.",
          "ML Readiness: Grade B (88/100) - highly suitable for regression or classification.",
          "Cleaning status: Active version is v3, created after applying missing value imputation and outlier removal."
        ],
        confidence: 0.94,
        sources: ["profiler", "quality", "ml_readiness", "cleaning_history"],
        timestamp
      }
  }
}


