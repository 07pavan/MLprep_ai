import { useState, useCallback, useEffect, useRef } from 'react'
import { sendCopilotQuery, createThread, deleteThread } from '../api/client'

let msgIdCounter = 0
const nextId = () => `msg_${Date.now()}_${++msgIdCounter}`

export function useChat(sessionId) {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [threadId, setThreadId] = useState(null)
  // Track if we attempted thread init to avoid blocking chat
  const threadInitAttempted = useRef(false)

  // Initialize/recreate thread when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setThreadId(null)
      setMessages([])
      threadInitAttempted.current = false
      return
    }

    // Reset for new session
    threadInitAttempted.current = false
    let isMounted = true

    async function initThread() {
      setIsLoading(true)
      try {
        const thread = await createThread(sessionId)
        if (isMounted) {
          setThreadId(thread.thread_id)
          setMessages([])
        }
      } catch (err) {
        console.warn(
          'Failed to initialize chat thread (threadless mode active):',
          err?.response?.data?.detail || err.message
        )
        // Don't block chat — proceed without a thread (threadless mode)
        // Chat will still work, just without server-side history persistence
        if (isMounted) {
          setThreadId(null)
        }
      } finally {
        if (isMounted) {
          threadInitAttempted.current = true
          setIsLoading(false)
        }
      }
    }

    initThread()

    return () => {
      isMounted = false
    }
  }, [sessionId])

  const sendQuestion = useCallback(
    async (question, persona = 'general', debugMode = false) => {
      // Require a valid session but NOT a threadId — threadless mode is supported
      if (!sessionId) return

      // If thread init hasn't completed yet, wait a brief moment then proceed threadlessly
      setIsLoading(true)
      setError(null)

      // Optimistically add user message
      const userMsg = {
        id: nextId(),
        role: 'user',
        content: question,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMsg])

      try {
        // Pass threadId if we have one, otherwise null (threadless mode)
        const data = await sendCopilotQuery(
          sessionId,
          question,
          [],
          persona,
          debugMode,
          threadId || null
        )

        const agentMsg = {
          id: nextId(),
          role: 'agent',
          success: data.success,
          answer: data.answer,
          data: data.data,
          truncation_meta: data.truncation_meta,
          execution_type: data.execution_type,
          execution_time_ms: data.execution_time_ms,
          code: data.code,
          error: data.error,
          timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, agentMsg])
      } catch (err) {
        const detail = err.response?.data?.detail || err.message || 'Something went wrong'
        setError(detail)
        const errMsg = {
          id: nextId(),
          role: 'agent',
          success: false,
          answer: `⚠️ ${detail}`,
          error: detail,
          timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, errMsg])
      } finally {
        setIsLoading(false)
      }
    },
    [sessionId, threadId]
  )

  const clearHistory = useCallback(async () => {
    if (threadId) {
      try {
        await deleteThread(threadId)
      } catch (err) {
        console.warn('Failed to delete thread:', err)
      }
    }
    setMessages([])
    setError(null)
    setThreadId(null)
    threadInitAttempted.current = false

    // Re-initialize a new thread
    if (sessionId) {
      setIsLoading(true)
      try {
        const thread = await createThread(sessionId)
        setThreadId(thread.thread_id)
      } catch (err) {
        console.warn('Failed to recreate thread (threadless mode):', err)
        setThreadId(null)
      } finally {
        threadInitAttempted.current = true
        setIsLoading(false)
      }
    }
  }, [sessionId, threadId])

  return { messages, isLoading, error, sendQuestion, clearHistory, threadId }
}
