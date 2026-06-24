import React, { createContext, useContext, useState, useEffect } from 'react'
import { initializeApp, getApps } from 'firebase/app'
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as fbSignOut,
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithPopup
} from 'firebase/auth'

const AuthContext = createContext(null)

// Load Firebase configuration from environment
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

// Check if Firebase configuration is complete
const isFirebaseConfigured = !!(firebaseConfig.apiKey && firebaseConfig.projectId)

let auth = null
if (isFirebaseConfigured) {
  try {
    if (getApps().length === 0) {
      initializeApp(firebaseConfig)
    }
    auth = getAuth()
  } catch (err) {
    console.error('Firebase initialization failed:', err)
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState(null)

  useEffect(() => {
    if (auth) {
      // Real Firebase auth listener
      const unsubscribe = onAuthStateChanged(auth, async (fbUser) => {
        if (fbUser) {
          try {
            const idToken = await fbUser.getIdToken(true)
            localStorage.setItem('authToken', idToken)
            setToken(idToken)
            setUser({
              uid: fbUser.uid,
              email: fbUser.email,
              displayName: fbUser.displayName || fbUser.email.split('@')[0],
              photoURL: fbUser.photoURL,
              isMock: false
            })
          } catch (err) {
            console.error('Error getting auth token:', err)
            localStorage.removeItem('authToken')
            setToken(null)
            setUser(null)
          }
        } else {
          localStorage.removeItem('authToken')
          setToken(null)
          setUser(null)
        }
        setLoading(false)
      })
      return unsubscribe
    } else {
      // Mock auth listener for development
      const storedUser = localStorage.getItem('mockUser')
      const storedToken = localStorage.getItem('authToken')
      if (storedUser && storedToken) {
        setUser(JSON.parse(storedUser))
        setToken(storedToken)
      }
      setLoading(false)
    }
  }, [])

  const logIn = async (email, password) => {
    if (auth) {
      const cred = await signInWithEmailAndPassword(auth, email, password)
      const idToken = await cred.user.getIdToken()
      localStorage.setItem('authToken', idToken)
      setToken(idToken)
      return cred.user
    } else {
      // Mock log in
      const mockUser = {
        uid: 'dev_user_123',
        email: email,
        displayName: email.split('@')[0],
        photoURL: null,
        isMock: true
      }
      localStorage.setItem('mockUser', JSON.stringify(mockUser))
      localStorage.setItem('authToken', 'mock_token_dev')
      setToken('mock_token_dev')
      setUser(mockUser)
      return mockUser
    }
  }

  const signUp = async (email, password) => {
    if (auth) {
      const cred = await createUserWithEmailAndPassword(auth, email, password)
      const idToken = await cred.user.getIdToken()
      localStorage.setItem('authToken', idToken)
      setToken(idToken)
      return cred.user
    } else {
      // Mock sign up
      return logIn(email, password)
    }
  }

  const logInWithGoogle = async () => {
    if (auth) {
      const provider = new GoogleAuthProvider()
      const cred = await signInWithPopup(auth, provider)
      const idToken = await cred.user.getIdToken()
      localStorage.setItem('authToken', idToken)
      setToken(idToken)
      return cred.user
    } else {
      return logIn('google-dev@example.com', 'password')
    }
  }

  const logOut = async () => {
    if (auth) {
      await fbSignOut(auth)
    }
    localStorage.removeItem('authToken')
    localStorage.removeItem('mockUser')
    // Clean up legacy global session key (pre-fix) so it never bleeds into another user
    localStorage.removeItem('dataai_session')
    setUser(null)
    setToken(null)
  }

  const value = {
    user,
    token,
    loading,
    isMock: !auth,
    logIn,
    signUp,
    logInWithGoogle,
    logOut
  }

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
