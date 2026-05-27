import { useState, useEffect } from 'react'
import { uploadFile } from '../api/client'

const STORAGE_KEY = 'dataai_session'

export function useSession() {
  const [sessionId, setSessionId] = useState(null)
  const [datasetMeta, setDatasetMeta] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadError, setUploadError] = useState(null)

  // Restore session from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.sessionId && parsed.datasetMeta) {
          setSessionId(parsed.sessionId)
          setDatasetMeta(parsed.datasetMeta)
        }
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [])

  const uploadDataset = async (file) => {
    setIsUploading(true)
    setUploadProgress(0)
    setUploadError(null)
    try {
      const data = await uploadFile(file, (pct) => setUploadProgress(pct))
      const meta = {
        filename: data.filename,
        format: data.format,
        shape: data.shape,
        columns: data.columns,
        memoryMb: data.memoryMb,
      }
      setSessionId(data.sessionId)
      setDatasetMeta(meta)
      setUploadProgress(100)
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ sessionId: data.sessionId, datasetMeta: meta })
      )
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Upload failed — check that the backend is running on port 8000.'
      setUploadError(msg)
    } finally {
      setIsUploading(false)
    }
  }

  const clearSession = () => {
    setSessionId(null)
    setDatasetMeta(null)
    setUploadError(null)
    setUploadProgress(0)
    localStorage.removeItem(STORAGE_KEY)
  }

  return {
    sessionId,
    datasetMeta,
    isUploading,
    uploadProgress,
    uploadError,
    uploadDataset,
    clearSession,
  }
}
