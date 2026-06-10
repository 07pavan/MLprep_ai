import { useState, useCallback } from 'react'
import { sendMessage } from '../api/client'

let msgIdCounter = 0
const nextId = () => `msg_${Date.now()}_${++msgIdCounter}`

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  /**
   * sendQuestion(sessionId, question, persona?)
   *   persona — one of: 'general' | 'finance' | 'marketing' | 'engineering'
   */
  const sendQuestion = useCallback(async (sessionId, question, persona = 'general') => {
    setIsLoading(true)
    setError(null)

    // Optimistically add the user message
    const userMsg = {
      id: nextId(),
      role: 'user',
      question,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])

    // Build chat history from existing messages for context (last 4 exchanges)
    const chatHistory = messages
      .filter((m) => m.role === 'user' || m.role === 'agent')
      .slice(-8)
      .map((m) =>
        m.role === 'user'
          ? { question: m.question }
          : { question: m.question || '', answer: JSON.stringify(m.analysis?.resultData || '').slice(0, 300) }
      )

    try {
      const data = await sendMessage(sessionId, question, chatHistory, persona)

      const agentMsg = {
        id: nextId(),
        role: 'agent',
        question,
        intent: data.intent,
        analysis: data.analysis,
        visualization: data.visualization,
        insights: data.insights,
        suggestedQuestions: data.suggestedQuestions || [],       // NEW
        clarificationNeeded: data.clarificationNeeded || false,  // NEW
        clarificationQuestion: data.clarificationQuestion || '', // NEW
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, agentMsg])
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Something went wrong'
      setError(msg)
      const errMsg = {
        id: nextId(),
        role: 'agent',
        question,
        analysis: { success: false, error: msg },
        suggestedQuestions: [],
        clarificationNeeded: false,
        clarificationQuestion: '',
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
