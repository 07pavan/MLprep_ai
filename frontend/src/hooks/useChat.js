import { useState, useCallback } from 'react'
import { sendMessage } from '../api/client'

let msgIdCounter = 0
const nextId = () => `msg_${Date.now()}_${++msgIdCounter}`

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendQuestion = useCallback(async (sessionId, question) => {
    setIsLoading(true)
    setError(null)

    // Add user message immediately
    const userMsg = {
      id: nextId(),
      role: 'user',
      question,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])

    // Build chat history from existing messages for context
    const chatHistory = messages
      .filter((m) => m.role === 'user' || m.role === 'agent')
      .slice(-8) // last 4 exchanges = 8 messages
      .map((m) =>
        m.role === 'user'
          ? { question: m.question }
          : { question: m.question || '', answer: JSON.stringify(m.analysis?.resultData || '').slice(0, 300) }
      )

    try {
      const data = await sendMessage(sessionId, question, chatHistory)

      const agentMsg = {
        id: nextId(),
        role: 'agent',
        question,
        analysis: data.analysis,
        visualization: data.visualization,
        insights: data.insights,
        intent: data.intent,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, agentMsg])
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Something went wrong'
      setError(msg)
      // Add error message
      const errMsg = {
        id: nextId(),
        role: 'agent',
        question,
        analysis: { success: false, error: msg },
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errMsg])
    } finally {
      setIsLoading(false)
    }
  }, [messages])

  const clearHistory = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  return { messages, isLoading, error, sendQuestion, clearHistory }
}
