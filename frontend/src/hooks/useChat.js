import { useState, useCallback, useEffect } from 'react'
import { sendCopilotQuery, createThread, deleteThread } from '../api/client'

let msgIdCounter = 0
const nextId = () => `msg_${Date.now()}_${++msgIdCounter}`

export function useChat(sessionId) {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [threadId, setThreadId] = useState(null)

  // Initialize/recreate thread when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setThreadId(null)
      setMessages([])
      return
    }

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
        console.error("Failed to initialize chat thread:", err)
        if (isMounted) {
          setError("Failed to initialize chat thread.")
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    initThread()

    return () => {
      isMounted = false
    }
  }, [sessionId])

  const sendQuestion = useCallback(async (question, persona = 'general', debugMode = false) => {
    if (!sessionId || !threadId) return
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
      const data = await sendCopilotQuery(sessionId, question, [], persona, debugMode, threadId)

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
      const msg = err.response?.data?.detail || err.message || 'Something went wrong'
      setError(msg)
      const errMsg = {
        id: nextId(),
        role: 'agent',
        success: false,
        answer: `An error occurred: ${msg}`,
        error: msg,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errMsg])
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, threadId])

  const clearHistory = useCallback(async () => {
    if (threadId) {
      try {
        await deleteThread(threadId)
      } catch (err) {
        console.error("Failed to delete thread:", err)
      }
    }
    setMessages([])
    setError(null)
    setThreadId(null)
    
    // Re-initialize a new thread
    if (sessionId) {
      setIsLoading(true)
      try {
        const thread = await createThread(sessionId)
        setThreadId(thread.thread_id)
      } catch (err) {
        console.error("Failed to recreate thread:", err)
        setError("Failed to initialize new chat thread.")
      } finally {
        setIsLoading(false)
      }
    }
  }, [sessionId, threadId])

  return { messages, isLoading, error, sendQuestion, clearHistory, threadId }
}
