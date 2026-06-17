import { useState, useEffect } from 'react'
import { uploadFile, importDatasetURL } from '../api/client'

const STORAGE_KEY = 'dataai_session'

export function useSession() {
  const [sessionId, setSessionId] = useState(null)
  const [datasetMeta, setDatasetMeta] = useState(null)
  const [currentDatasetId, setCurrentDatasetId] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadError, setUploadError] = useState(null)
  const [isSuccess, setIsSuccess] = useState(false)

  // Restore session from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.sessionId && parsed.datasetMeta) {
          setSessionId(parsed.sessionId)
          setDatasetMeta(parsed.datasetMeta)
          setCurrentDatasetId(parsed.datasetId || null)
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
    setIsSuccess(false)
    try {
      const data = await uploadFile(file, (pct) => setUploadProgress(pct))
      const meta = {
        filename: data.filename,
        format: data.format,
        shape: data.shape,
        columns: data.columns,
        memoryMb: data.memoryMb,
        warning: data.warning,
      }
      setUploadProgress(100)
      setIsSuccess(true)
      await new Promise((resolve) => setTimeout(resolve, 1500))
      setSessionId(data.sessionId)
      setDatasetMeta(meta)
      setCurrentDatasetId(data.datasetId)
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ sessionId: data.sessionId, datasetMeta: meta, datasetId: data.datasetId })
      )
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

  const activateSession = (sessId, meta, destId) => {
    setSessionId(sessId)
    setDatasetMeta(meta)
    setCurrentDatasetId(destId)
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ sessionId: sessId, datasetMeta: meta, datasetId: destId })
    )
  }

  const clearSession = () => {
    setSessionId(null)
    setDatasetMeta(null)
    setCurrentDatasetId(null)
    setUploadError(null)
    setUploadProgress(0)
    setIsSuccess(false)
    localStorage.removeItem(STORAGE_KEY)
  }

  const importDataset = async (url) => {
    setIsUploading(true)
    setUploadProgress(25)
    setUploadError(null)
    setIsSuccess(false)
    try {
      const data = await importDatasetURL(url)
      const meta = {
        filename: data.filename,
        format: data.format,
        shape: data.shape,
        columns: data.columns,
        memoryMb: data.memoryMb,
        warning: data.warning,
      }
      setUploadProgress(100)
      setIsSuccess(true)
      await new Promise((resolve) => setTimeout(resolve, 1500))
      setSessionId(data.sessionId)
      setDatasetMeta(meta)
      setCurrentDatasetId(data.datasetId)
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ sessionId: data.sessionId, datasetMeta: meta, datasetId: data.datasetId })
      )
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
