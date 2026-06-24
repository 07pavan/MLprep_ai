import { useState, useEffect, useRef } from 'react'
import { uploadFile, importDatasetURL } from '../api/client'

// Storage key is scoped per Firebase UID so different users
// never see each other's sessions in the same browser.
const sessionKey = (uid) => `dataai_session_${uid}`

export function useSession(userId) {
  const [sessionId,       setSessionId]       = useState(null)
  const [datasetMeta,     setDatasetMeta]     = useState(null)
  const [currentDatasetId,setCurrentDatasetId]= useState(null)
  const [isUploading,     setIsUploading]     = useState(false)
  const [uploadProgress,  setUploadProgress]  = useState(0)
  const [uploadError,     setUploadError]     = useState(null)
  const [isSuccess,       setIsSuccess]       = useState(false)

  // Track previous userId so we can reset when user changes
  const prevUserIdRef = useRef(userId)

  // Restore session from localStorage whenever userId changes
  useEffect(() => {
    // If the user changed (logout → login as someone else), wipe state first
    if (prevUserIdRef.current !== userId) {
      setSessionId(null)
      setDatasetMeta(null)
      setCurrentDatasetId(null)
      setUploadError(null)
      setUploadProgress(0)
      setIsSuccess(false)
      prevUserIdRef.current = userId
    }

    // No user → nothing to restore
    if (!userId) return

    try {
      const saved = localStorage.getItem(sessionKey(userId))
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.sessionId && parsed.datasetMeta) {
          setSessionId(parsed.sessionId)
          setDatasetMeta(parsed.datasetMeta)
          setCurrentDatasetId(parsed.datasetId || null)
        }
      }
    } catch {
      localStorage.removeItem(sessionKey(userId))
    }
  }, [userId])

  // ── Upload ────────────────────────────────────────────────────────
  const uploadDataset = async (file) => {
    setIsUploading(true)
    setUploadProgress(0)
    setUploadError(null)
    setIsSuccess(false)
    try {
      const data = await uploadFile(file, (pct) => setUploadProgress(pct))
      const meta = {
        filename: data.filename,
        format:   data.format,
        shape:    data.shape,
        columns:  data.columns,
        memoryMb: data.memoryMb,
        warning:  data.warning,
      }
      setUploadProgress(100)
      setIsSuccess(true)
      await new Promise((resolve) => setTimeout(resolve, 1500))
      setSessionId(data.sessionId)
      setDatasetMeta(meta)
      setCurrentDatasetId(data.datasetId)
      if (userId) {
        localStorage.setItem(
          sessionKey(userId),
          JSON.stringify({ sessionId: data.sessionId, datasetMeta: meta, datasetId: data.datasetId })
        )
      }
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Upload failed — check that the backend is running on port 8000.'
      setUploadError(msg)
      setIsSuccess(false)
    } finally {
      setIsUploading(false)
    }
  }

  // ── Activate existing dataset ────────────────────────────────────
  const activateSession = (sessId, meta, destId) => {
    setSessionId(sessId)
    setDatasetMeta(meta)
    setCurrentDatasetId(destId)
    if (userId) {
      localStorage.setItem(
        sessionKey(userId),
        JSON.stringify({ sessionId: sessId, datasetMeta: meta, datasetId: destId })
      )
    }
  }

  // ── Clear ────────────────────────────────────────────────────────
  const clearSession = () => {
    setSessionId(null)
    setDatasetMeta(null)
    setCurrentDatasetId(null)
    setUploadError(null)
    setUploadProgress(0)
    setIsSuccess(false)
    if (userId) localStorage.removeItem(sessionKey(userId))
  }

  // ── Import by URL ────────────────────────────────────────────────
  const importDataset = async (url) => {
    setIsUploading(true)
    setUploadProgress(25)
    setUploadError(null)
    setIsSuccess(false)
    try {
      const data = await importDatasetURL(url)
      const meta = {
        filename: data.filename,
        format:   data.format,
        shape:    data.shape,
        columns:  data.columns,
        memoryMb: data.memoryMb,
        warning:  data.warning,
      }
      setUploadProgress(100)
      setIsSuccess(true)
      await new Promise((resolve) => setTimeout(resolve, 1500))
      setSessionId(data.sessionId)
      setDatasetMeta(meta)
      setCurrentDatasetId(data.datasetId)
      if (userId) {
        localStorage.setItem(
          sessionKey(userId),
          JSON.stringify({ sessionId: data.sessionId, datasetMeta: meta, datasetId: data.datasetId })
        )
      }
      return true
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Import failed — check that the backend is running and the URL is reachable.'
      setUploadError(msg)
      setIsSuccess(false)
      return false
    } finally {
      setIsUploading(false)
    }
  }

  return {
    sessionId,
    datasetMeta,
    currentDatasetId,
    isUploading,
    uploadProgress,
    uploadError,
    isSuccess,
    uploadDataset,
    importDataset,
    activateSession,
    clearSession,
  }
}
