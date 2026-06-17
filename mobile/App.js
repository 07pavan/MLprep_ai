import React, { useState, useEffect } from 'react'
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  FlatList,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  StatusBar,
  Alert
} from 'react-native'
import {
  Database,
  Sliders,
  MessageSquare,
  Sparkles,
  AlertTriangle,
  Send,
  Plus,
  Compass,
  ArrowRight,
  LogOut,
  RefreshCw,
  FolderOpen
} from 'lucide-react-native'

import {
  setApiBaseUrl,
  setCustomLlmCredentials,
  clearCredentials,
  importDatasetURL,
  listDatasets,
  activateDataset,
  sendCopilotQuery,
  generateInsights,
  getRateLimits
} from './src/api/client'

// Core Themes matching the polished Web Slate/Indigo theme
const THEME = {
  bgPrimary: '#090B11',
  bgSurface: '#0F1420',
  bgElevated: '#171F30',
  accent: '#6366F1',
  accentSecondary: '#3B82F6',
  border: 'rgba(255, 255, 255, 0.06)',
  textPrimary: '#F3F4F6',
  textSecondary: '#9CA3AF',
  textMuted: '#6B7280',
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  radius: 12,
}

export default function App() {
  const [currentScreen, setCurrentScreen] = useState('auth') // 'auth' | 'dashboard' | 'chat' | 'insights'
  const [apiBase, setApiBase] = useState('http://10.0.2.2:8000/api')
  const [llmProvider, setLlmProvider] = useState('groq') // 'groq' | 'openrouter'
  const [apiKey, setApiKey] = useState('')
  const [modelOverride, setModelOverride] = useState('')
  
  // Data / Session States
  const [sessionId, setSessionId] = useState(null)
  const [activeDataset, setActiveDataset] = useState(null) // { id, name, rows, cols, warning }
  const [datasetsList, setDatasetsList] = useState([])
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(false)
  const [importUrl, setImportUrl] = useState('')
  const [isImporting, setIsImporting] = useState(false)

  // Chat States
  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [isSendingMsg, setIsSendingMsg] = useState(false)

  // Insights States
  const [insights, setInsights] = useState([])
  const [insightCategory, setInsightCategory] = useState('general')
  const [isLoadingInsights, setIsLoadingInsights] = useState(false)

  // Apply API Server Settings on startup
  useEffect(() => {
    setApiBaseUrl(apiBase)
  }, [apiBase])

  const handleLogin = () => {
    setApiBaseUrl(apiBase)
    if (apiKey) {
      setCustomLlmCredentials(llmProvider, apiKey, modelOverride || null)
    } else {
      clearCredentials()
    }
    fetchDatasets()
    setCurrentScreen('dashboard')
  }

  const handleLogout = () => {
    clearCredentials()
    setSessionId(null)
    setActiveDataset(null)
    setMessages([])
    setInsights([])
    setCurrentScreen('auth')
  }

  const fetchDatasets = async () => {
    setIsLoadingDatasets(true)
    try {
      const data = await listDatasets()
      setDatasetsList(data || [])
      // If there's an active dataset on backend, bind it
      const active = data.find(d => d.status === 'active')
      if (active) {
        setSessionId(active.sessionId || 'active-session')
        setActiveDataset({
          id: active.dataset_id,
          name: active.dataset_name,
          rows: active.row_count,
          cols: active.column_count,
          warning: active.row_count > 100000 
            ? "Large dataset detected. Columns profiled via sampling. Downstream AI calculations might experience latency."
            : null
        })
      }
    } catch (err) {
      console.warn("Failed to fetch datasets list:", err.message)
    } finally {
      setIsLoadingDatasets(false)
    }
  }

  const handleImport = async () => {
    if (!importUrl.trim()) return
    setIsImporting(true)
    try {
      const res = await importDatasetURL(importUrl.trim())
      setSessionId(res.sessionId)
      setActiveDataset({
        id: res.datasetId,
        name: res.filename,
        rows: res.shape.rows,
        cols: res.shape.cols,
        warning: res.warning
      })
      setImportUrl('')
      Alert.alert("Success", `Dataset "${res.filename}" imported and analyzed successfully!`)
      fetchDatasets()
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      Alert.alert("Import Failed", detail)
    } finally {
      setIsImporting(false)
    }
  }

  const handleSelectDataset = async (dataset) => {
    setIsLoadingDatasets(true)
    try {
      const res = await activateDataset(dataset.dataset_id)
      setSessionId(res.sessionId)
      setActiveDataset({
        id: dataset.dataset_id,
        name: dataset.dataset_name,
        rows: dataset.row_count,
        cols: dataset.column_count,
        warning: dataset.row_count > 100000 
          ? "Large dataset detected. Columns profiled via sampling. Downstream AI calculations might experience latency."
          : null
      })
      Alert.alert("Dataset Switched", `Switched to active dataset: ${dataset.dataset_name}`)
      // Clear screens state
      setMessages([])
      setInsights([])
      fetchDatasets()
    } catch (err) {
      Alert.alert("Activation Error", err.message)
    } finally {
      setIsLoadingDatasets(false)
    }
  }

  const handleSendChat = async () => {
    if (!chatInput.trim() || !sessionId) return
    const userMsg = { id: Date.now().toString(), sender: 'user', text: chatInput.trim() }
    setMessages(prev => [...prev, userMsg])
    setChatInput('')
    setIsSendingMsg(true)

    // Build chat history contract
    const history = messages.map(m => ({
      role: m.sender === 'user' ? 'user' : 'assistant',
      content: m.text
    }))

    try {
      const res = await sendCopilotQuery(sessionId, userMsg.text, history)
      const agentMsg = {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        text: res.answer || "No response received."
      }
      setMessages(prev => [...prev, agentMsg])
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        text: `Error communicating with Copilot: ${detail}`
      }])
    } finally {
      setIsSendingMsg(false)
    }
  }

  const loadInsights = async (cat = insightCategory) => {
    if (!sessionId) return
    setIsLoadingInsights(true)
    setInsightCategory(cat)
    try {
      const data = await generateInsights(sessionId, cat)
      setInsights(data.insights || [])
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      Alert.alert("Insights Failed", detail)
    } finally {
      setIsLoadingInsights(false)
    }
  }

  // Auto load insights when screen changes
  useEffect(() => {
    if (currentScreen === 'insights' && sessionId) {
      loadInsights()
    }
  }, [currentScreen])

  // Custom chat suggestion helper
  const handleSuggestion = (question) => {
    setChatInput(question)
  }

  return (
    <SafeAreaView style={styles.appContainer}>
      <StatusBar barStyle="light-content" backgroundColor={THEME.bgPrimary} />
      
      {/* ── Screen Header ── */}
      {currentScreen !== 'auth' && (
        <View style={styles.header}>
          <View style={styles.headerBrand}>
            <Database size={18} color={THEME.accent} />
            <Text style={styles.headerBrandText}>MLPrep AI Mobile</Text>
          </View>
          <TouchableOpacity onPress={handleLogout} style={styles.headerLogoutBtn}>
            <LogOut size={16} color={THEME.textMuted} />
          </TouchableOpacity>
        </View>
      )}

      {/* ── Main Workspace Scroll / Keyboard Area ── */}
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        
        {/* 1. AUTH SCREEN */}
        {currentScreen === 'auth' && (
          <ScrollView contentContainerStyle={styles.authContainer} keyboardShouldPersistTaps="handled">
            <View style={styles.authLogoBox}>
              <Database size={40} color={THEME.accent} />
              <Text style={styles.authTitle}>MLPrep AI</Text>
              <Text style={styles.authSubtitle}>Transform raw data into model-ready datasets</Text>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardHeader}>Server Configuration</Text>
              <TextInput
                style={styles.input}
                placeholder="Backend API Base URL"
                placeholderTextColor={THEME.textMuted}
                value={apiBase}
                onChangeText={setApiBase}
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>

            <View style={styles.card}>
              <Text style={styles.cardHeader}>Optional Custom LLM Credentials</Text>
              <View style={styles.tabContainer}>
                <TouchableOpacity
                  style={[styles.tabBtn, llmProvider === 'groq' && styles.tabBtnActive]}
                  onPress={() => setLlmProvider('groq')}
                >
                  <Text style={[styles.tabText, llmProvider === 'groq' && styles.tabTextActive]}>Groq</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.tabBtn, llmProvider === 'openrouter' && styles.tabBtnActive]}
                  onPress={() => setLlmProvider('openrouter')}
                >
                  <Text style={[styles.tabText, llmProvider === 'openrouter' && styles.tabTextActive]}>OpenRouter</Text>
                </TouchableOpacity>
              </View>

              <TextInput
                style={styles.input}
                placeholder="Custom API Key"
                placeholderTextColor={THEME.textMuted}
                value={apiKey}
                onChangeText={setApiKey}
                secureTextEntry
                autoCapitalize="none"
              />
              
              <TextInput
                style={styles.input}
                placeholder="Model Override (optional)"
                placeholderTextColor={THEME.textMuted}
                value={modelOverride}
                onChangeText={setModelOverride}
                autoCapitalize="none"
              />
            </View>

            <TouchableOpacity style={styles.btnPrimary} onPress={handleLogin}>
              <Text style={styles.btnPrimaryText}>Connect Platform</Text>
              <ArrowRight size={18} color="#FFF" />
            </TouchableOpacity>
          </ScrollView>
        )}

        {/* 2. DASHBOARD SCREEN */}
        {currentScreen === 'dashboard' && (
          <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
            
            {/* Active Dataset Section */}
            {activeDataset ? (
              <View style={styles.activeDatasetCard}>
                <View style={styles.activeDatasetHeader}>
                  <FolderOpen size={16} color={THEME.accent} />
                  <Text style={styles.activeDatasetTitle}>{activeDataset.name}</Text>
                </View>
                <Text style={styles.activeDatasetDetails}>
                  {activeDataset.rows.toLocaleString()} rows × {activeDataset.cols} columns
                </Text>

                {/* Amber Warning Card */}
                {activeDataset.warning && (
                  <View style={styles.warningCard}>
                    <AlertTriangle size={14} color={THEME.warning} />
                    <Text style={styles.warningText}>{activeDataset.warning}</Text>
                  </View>
                )}
              </View>
            ) : (
              <View style={styles.activeDatasetCardEmpty}>
                <Text style={styles.activeDatasetEmptyText}>No Active Dataset Ingested</Text>
              </View>
            )}

            {/* Quick Actions Grid */}
            {activeDataset && (
              <View style={styles.actionsGrid}>
                <TouchableOpacity
                  style={styles.actionCard}
                  onPress={() => setCurrentScreen('chat')}
                >
                  <MessageSquare size={20} color={THEME.accent} />
                  <Text style={styles.actionCardTitle}>Data Copilot</Text>
                  <Text style={styles.actionCardDesc}>Ask questions and analyze schema</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.actionCard}
                  onPress={() => setCurrentScreen('insights')}
                >
                  <Sparkles size={20} color={THEME.accentSecondary} />
                  <Text style={styles.actionCardTitle}>Proactive Insights</Text>
                  <Text style={styles.actionCardDesc}>Discover statistical warnings</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Remote URL Import Form */}
            <View style={styles.card}>
              <Text style={styles.cardHeader}>Import Remote Dataset</Text>
              <TextInput
                style={styles.input}
                placeholder="https://example.com/data.csv"
                placeholderTextColor={THEME.textMuted}
                value={importUrl}
                onChangeText={setImportUrl}
                autoCapitalize="none"
              />
              <TouchableOpacity
                style={[styles.btnSecondary, isImporting && { opacity: 0.7 }]}
                onPress={handleImport}
                disabled={isImporting}
              >
                {isImporting ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <>
                    <Plus size={16} color="#fff" />
                    <Text style={styles.btnSecondaryText}>Import URL</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>

            {/* Datasets List */}
            <View style={styles.card}>
              <View style={styles.cardHeaderRow}>
                <Text style={styles.cardHeader}>Available Datasets</Text>
                <TouchableOpacity onPress={fetchDatasets}>
                  <RefreshCw size={14} color={THEME.textSecondary} />
                </TouchableOpacity>
              </View>

              {isLoadingDatasets ? (
                <ActivityIndicator size="small" color={THEME.accent} style={{ padding: 12 }} />
              ) : datasetsList.length === 0 ? (
                <Text style={styles.emptyListText}>No datasets stored on the server yet.</Text>
              ) : (
                datasetsList.map(item => (
                  <TouchableOpacity
                    key={item.dataset_id}
                    style={[
                      styles.datasetItem,
                      activeDataset?.id === item.dataset_id && styles.datasetItemActive
                    ]}
                    onPress={() => handleSelectDataset(item)}
                  >
                    <Text style={styles.datasetItemName}>{item.dataset_name}</Text>
                    <Text style={styles.datasetItemMeta}>
                      {item.row_count.toLocaleString()} rows · {item.column_count} cols
                    </Text>
                  </TouchableOpacity>
                ))
              )}
            </View>

          </ScrollView>
        )}

        {/* 3. CHAT SCREEN */}
        {currentScreen === 'chat' && (
          <View style={{ flex: 1 }}>
            <FlatList
              data={messages}
              keyExtractor={item => item.id}
              contentContainerStyle={[styles.container, { paddingBottom: 100 }]}
              renderItem={({ item }) => (
                <View style={[
                  styles.chatRow,
                  item.sender === 'user' ? styles.chatRowUser : styles.chatRowAgent
                ]}>
                  <View style={[
                    styles.chatBubble,
                    item.sender === 'user' ? styles.chatBubbleUser : styles.chatBubbleAgent
                  ]}>
                    <Text style={styles.chatText}>{item.text}</Text>
                  </View>
                </View>
              )}
              ListEmptyComponent={
                <View style={styles.chatEmptyContainer}>
                  <Compass size={36} color={THEME.textMuted} style={{ marginBottom: 12 }} />
                  <Text style={styles.chatEmptyTitle}>Ask Data Copilot</Text>
                  <Text style={styles.chatEmptySub}>Submit inquiries about columns, data distributions, and profiles.</Text>
                  
                  {/* Suggestion Chips */}
                  <View style={styles.suggestionsContainer}>
                    <TouchableOpacity
                      style={styles.suggestionChip}
                      onPress={() => handleSuggestion("Summarize this dataset")}
                    >
                      <Text style={styles.suggestionChipText}>"Summarize this dataset"</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.suggestionChip}
                      onPress={() => handleSuggestion("Show columns list")}
                    >
                      <Text style={styles.suggestionChipText}>"Show columns list"</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.suggestionChip}
                      onPress={() => handleSuggestion("Are there missing values?")}
                    >
                      <Text style={styles.suggestionChipText}>"Are there missing values?"</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              }
            />

            {/* Chat Input Bar */}
            <View style={styles.chatInputBar}>
              <TextInput
                style={styles.chatInput}
                placeholder="Ask about columns or variables..."
                placeholderTextColor={THEME.textMuted}
                value={chatInput}
                onChangeText={setChatInput}
                multiline
              />
              <TouchableOpacity
                style={styles.chatSendBtn}
                onPress={handleSendChat}
                disabled={isSendingMsg || !chatInput.trim()}
              >
                {isSendingMsg ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Send size={16} color="#fff" />
                )}
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* 4. INSIGHTS SCREEN */}
        {currentScreen === 'insights' && (
          <View style={{ flex: 1 }}>
            
            {/* Category Selector Tabs */}
            <View style={styles.insightsTabRow}>
              {['general', 'statistical', 'quality', 'ml_readiness', 'business'].map(cat => (
                <TouchableOpacity
                  key={cat}
                  style={[styles.categoryTab, insightCategory === cat && styles.categoryTabActive]}
                  onPress={() => loadInsights(cat)}
                >
                  <Text style={[styles.categoryTabText, insightCategory === cat && styles.categoryTabTextActive]}>
                    {cat.replace('_', ' ')}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {isLoadingInsights ? (
              <View style={styles.loaderContainer}>
                <ActivityIndicator size="large" color={THEME.accent} />
                <Text style={styles.loaderText}>Generating proactive insights...</Text>
              </View>
            ) : (
              <FlatList
                data={insights}
                keyExtractor={item => item.insight_id}
                contentContainerStyle={styles.container}
                renderItem={({ item }) => (
                  <View style={styles.insightCard}>
                    <Text style={styles.insightTitle}>{item.title}</Text>
                    <Text style={styles.insightDesc}>{item.description}</Text>
                    <View style={styles.insightFooter}>
                      <Text style={styles.insightSeverity}>Severity: {item.severity}</Text>
                      <Text style={styles.insightConfidence}>
                        Conf: {Math.round(item.confidence_score * 100)}%
                      </Text>
                    </View>
                  </View>
                )}
                ListEmptyComponent={
                  <Text style={styles.emptyInsightsText}>No proactive insights found for this category.</Text>
                }
              />
            )}
          </View>
        )}

      </KeyboardAvoidingView>

      {/* ── Mobile Navigation Tabs ── */}
      {currentScreen !== 'auth' && (
        <View style={styles.navBar}>
          <TouchableOpacity
            style={[styles.navItem, currentScreen === 'dashboard' && styles.navItemActive]}
            onPress={() => setCurrentScreen('dashboard')}
          >
            <Compass size={18} color={currentScreen === 'dashboard' ? THEME.accent : THEME.textMuted} />
            <Text style={[styles.navText, currentScreen === 'dashboard' && styles.navTextActive]}>Home</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[styles.navItem, currentScreen === 'chat' && styles.navItemActive]}
            onPress={() => setCurrentScreen('chat')}
            disabled={!sessionId}
          >
            <MessageSquare size={18} color={currentScreen === 'chat' ? THEME.accent : THEME.textMuted} style={{ opacity: sessionId ? 1 : 0.4 }} />
            <Text style={[styles.navText, currentScreen === 'chat' && styles.navTextActive, !sessionId && { opacity: 0.4 }]}>Copilot</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.navItem, currentScreen === 'insights' && styles.navItemActive]}
            onPress={() => setCurrentScreen('insights')}
            disabled={!sessionId}
          >
            <Sparkles size={18} color={currentScreen === 'insights' ? THEME.accent : THEME.textMuted} style={{ opacity: sessionId ? 1 : 0.4 }} />
            <Text style={[styles.navText, currentScreen === 'insights' && styles.navTextActive, !sessionId && { opacity: 0.4 }]}>Insights</Text>
          </TouchableOpacity>
        </View>
      )}

    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  appContainer: {
    flex: 1,
    backgroundColor: THEME.bgPrimary,
  },
  header: {
    height: 52,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    backgroundColor: THEME.bgSurface,
  },
  headerBrand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerBrandText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: THEME.textPrimary,
  },
  headerLogoutBtn: {
    padding: 6,
  },
  authContainer: {
    padding: 24,
    paddingTop: 64,
    flexGrow: 1,
    justifyContent: 'center',
  },
  authLogoBox: {
    alignItems: 'center',
    marginBottom: 36,
  },
  authTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: THEME.textPrimary,
    marginTop: 12,
  },
  authSubtitle: {
    fontSize: 13,
    color: THEME.textMuted,
    marginTop: 4,
  },
  container: {
    padding: 16,
  },
  card: {
    backgroundColor: THEME.bgSurface,
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: THEME.radius,
    padding: 16,
    marginBottom: 16,
  },
  cardHeader: {
    fontSize: 13,
    fontWeight: '700',
    color: THEME.textSecondary,
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  input: {
    height: 44,
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    fontSize: 14,
    color: THEME.textPrimary,
    backgroundColor: THEME.bgElevated,
    marginBottom: 12,
  },
  tabContainer: {
    flexDirection: 'row',
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: 8,
    marginBottom: 12,
    overflow: 'hidden',
  },
  tabBtn: {
    flex: 1,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: THEME.bgSurface,
  },
  tabBtnActive: {
    backgroundColor: THEME.bgElevated,
  },
  tabText: {
    fontSize: 13,
    color: THEME.textMuted,
    fontWeight: '500',
  },
  tabTextActive: {
    color: THEME.accent,
    fontWeight: '700',
  },
  btnPrimary: {
    height: 48,
    backgroundColor: THEME.accent,
    borderRadius: THEME.radius,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    shadowColor: THEME.accent,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 10,
    elevation: 3,
  },
  btnPrimaryText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: '700',
  },
  btnSecondary: {
    height: 44,
    backgroundColor: THEME.accent,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  btnSecondaryText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  activeDatasetCard: {
    backgroundColor: 'rgba(99, 102, 241, 0.04)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.15)',
    borderRadius: THEME.radius,
    padding: 16,
    marginBottom: 16,
  },
  activeDatasetCardEmpty: {
    backgroundColor: THEME.bgSurface,
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: THEME.radius,
    padding: 20,
    alignItems: 'center',
    marginBottom: 16,
  },
  activeDatasetEmptyText: {
    fontSize: 13,
    color: THEME.textMuted,
  },
  activeDatasetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  activeDatasetTitle: {
    fontSize: 15,
    fontWeight: 'bold',
    color: THEME.textPrimary,
  },
  activeDatasetDetails: {
    fontSize: 12,
    color: THEME.textSecondary,
    marginTop: 6,
    paddingLeft: 24,
  },
  warningCard: {
    backgroundColor: 'rgba(245, 158, 11, 0.04)',
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.2)',
    borderRadius: 8,
    padding: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
  },
  warningText: {
    fontSize: 11,
    color: THEME.warning,
    flex: 1,
    lineHeight: 15,
  },
  actionsGrid: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  actionCard: {
    flex: 1,
    backgroundColor: THEME.bgSurface,
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: THEME.radius,
    padding: 14,
    gap: 6,
  },
  actionCardTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: THEME.textPrimary,
  },
  actionCardDesc: {
    fontSize: 10,
    color: THEME.textMuted,
    lineHeight: 13,
  },
  emptyListText: {
    fontSize: 13,
    color: THEME.textMuted,
    textAlign: 'center',
    padding: 12,
  },
  datasetItem: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
  },
  datasetItemActive: {
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
  },
  datasetItemName: {
    fontSize: 14,
    fontWeight: '600',
    color: THEME.textPrimary,
  },
  datasetItemMeta: {
    fontSize: 11,
    color: THEME.textMuted,
    marginTop: 3,
  },
  navBar: {
    height: 56,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    backgroundColor: THEME.bgSurface,
    paddingBottom: Platform.OS === 'ios' ? 8 : 0,
  },
  navItem: {
    alignItems: 'center',
    gap: 3,
    paddingVertical: 6,
    paddingHorizontal: 16,
  },
  navItemActive: {
    // optional styling for active tab
  },
  navText: {
    fontSize: 10,
    fontWeight: '500',
    color: THEME.textMuted,
  },
  navTextActive: {
    color: THEME.accent,
    fontWeight: 'bold',
  },
  chatRow: {
    flexDirection: 'row',
    marginBottom: 16,
    width: '100%',
  },
  chatRowUser: {
    justifyContent: 'flex-end',
  },
  chatRowAgent: {
    justifyContent: 'flex-start',
  },
  chatBubble: {
    maxWidth: '82%',
    padding: 12,
    borderRadius: THEME.radius,
  },
  chatBubbleUser: {
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.18)',
    borderBottomRightRadius: 4,
  },
  chatBubbleAgent: {
    backgroundColor: THEME.bgSurface,
    borderWidth: 1,
    borderColor: THEME.border,
    borderBottomLeftRadius: 4,
  },
  chatText: {
    fontSize: 14,
    color: THEME.textPrimary,
    lineHeight: 20,
  },
  chatEmptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 64,
  },
  chatEmptyTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: THEME.textPrimary,
  },
  chatEmptySub: {
    fontSize: 13,
    color: THEME.textMuted,
    textAlign: 'center',
    marginTop: 6,
    paddingHorizontal: 32,
    lineHeight: 18,
  },
  suggestionsContainer: {
    marginTop: 24,
    width: '100%',
    paddingHorizontal: 16,
    gap: 8,
  },
  suggestionChip: {
    backgroundColor: THEME.bgSurface,
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: 8,
    padding: 10,
  },
  suggestionChipText: {
    fontSize: 12,
    color: THEME.textSecondary,
    textAlign: 'center',
  },
  chatInputBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 64,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    backgroundColor: THEME.bgPrimary,
    gap: 8,
  },
  chatInput: {
    flex: 1,
    height: 40,
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    fontSize: 13,
    color: THEME.textPrimary,
    backgroundColor: THEME.bgElevated,
  },
  chatSendBtn: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: THEME.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  insightsTabRow: {
    flexDirection: 'row',
    backgroundColor: THEME.bgSurface,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
    paddingVertical: 8,
    paddingHorizontal: 12,
    gap: 6,
  },
  categoryTab: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    backgroundColor: THEME.bgElevated,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  categoryTabActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    borderColor: THEME.accent,
  },
  categoryTabText: {
    fontSize: 11,
    color: THEME.textMuted,
    textTransform: 'capitalize',
  },
  categoryTabTextActive: {
    color: THEME.accent,
    fontWeight: 'bold',
  },
  loaderContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 48,
    gap: 12,
  },
  loaderText: {
    fontSize: 13,
    color: THEME.textSecondary,
  },
  insightCard: {
    backgroundColor: THEME.bgSurface,
    borderWidth: 1,
    borderColor: THEME.border,
    borderLeftWidth: 3,
    borderLeftColor: THEME.accentSecondary,
    borderRadius: 8,
    padding: 14,
    marginBottom: 12,
  },
  insightTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: THEME.textPrimary,
  },
  insightDesc: {
    fontSize: 12,
    color: THEME.textSecondary,
    lineHeight: 18,
    marginTop: 6,
  },
  insightFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.03)',
    paddingTop: 8,
  },
  insightSeverity: {
    fontSize: 10,
    color: THEME.textMuted,
    fontWeight: '700',
  },
  insightConfidence: {
    fontSize: 10,
    color: THEME.textMuted,
  },
  emptyInsightsText: {
    fontSize: 13,
    color: THEME.textMuted,
    textAlign: 'center',
    padding: 32,
  },
})
