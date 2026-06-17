import React, { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { Database, Mail, Lock, Sparkles, AlertCircle, ArrowRight } from 'lucide-react'

export default function AuthPage() {
  const { logIn, signUp, logInWithGoogle, isMock } = useAuth()
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    // Validations
    if (!email || !password) {
      setError('Please fill in all fields.')
      setLoading(false)
      return
    }

    if (isSignUp && password !== confirmPassword) {
      setError('Passwords do not match.')
      setLoading(false)
      return
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      setLoading(false)
      return
    }

    try {
      if (isSignUp) {
        await signUp(email, password)
      } else {
        await logIn(email, password)
      }
    } catch (err) {
      console.error(err)
      const msg = err.message || 'Authentication failed. Please check your credentials.'
      setError(msg.replace('Firebase:', '').trim())
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSignIn = async () => {
    setError('')
    setLoading(true)
    try {
      await logInWithGoogle()
    } catch (err) {
      console.error(err)
      setError(err.message || 'Google Sign-In failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="upload-page" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="upload-card glass-card" style={{ maxWidth: 460, width: '100%', padding: '40px 32px' }}>
        
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div className="upload-icon" style={{ marginBottom: 16 }}>
            <Database size={32} />
          </div>
          <h1 className="upload-title" style={{ fontSize: '1.75rem', fontWeight: 800 }}>
            <span className="gradient-text">MLPrep AI</span>
          </h1>
          <p className="upload-subtitle" style={{ fontSize: '0.85rem', marginBottom: 0 }}>
            Transform raw data into model-ready datasets
          </p>
        </div>

        {/* Development Mock Mode Banner */}
        {isMock && (
          <div className="memory-banner" style={{ marginBottom: 20, justifyContent: 'center', background: 'rgba(59,130,246,0.08)', borderColor: 'rgba(59,130,246,0.2)' }}>
            <Sparkles size={14} style={{ color: 'var(--info)' }} />
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Offline Dev Mode (Any credentials will work)
            </span>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="error-card" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 10 }}>
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <div style={{ fontSize: '0.8rem', lineHeight: 1.4 }}>{error}</div>
          </div>
        )}

        {/* Tab Toggle */}
        <div style={{
          display: 'flex',
          background: 'var(--bg-elevated)',
          padding: 4,
          borderRadius: 'var(--radius-md)',
          marginBottom: 24,
          border: '1px solid var(--border-subtle)'
        }}>
          <button
            onClick={() => { setIsSignUp(false); setError(''); }}
            style={{
              flex: 1,
              padding: '8px 12px',
              fontSize: '0.85rem',
              fontWeight: 600,
              borderRadius: '8px',
              color: !isSignUp ? 'var(--text-primary)' : 'var(--text-secondary)',
              background: !isSignUp ? 'var(--bg-glass-hover)' : 'transparent',
              transition: 'var(--transition)'
            }}
          >
            Sign In
          </button>
          <button
            onClick={() => { setIsSignUp(true); setError(''); }}
            style={{
              flex: 1,
              padding: '8px 12px',
              fontSize: '0.85rem',
              fontWeight: 600,
              borderRadius: '8px',
              color: isSignUp ? 'var(--text-primary)' : 'var(--text-secondary)',
              background: isSignUp ? 'var(--bg-glass-hover)' : 'transparent',
              transition: 'var(--transition)'
            }}
          >
            Register
          </button>
        </div>

        {/* Auth Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          
          {/* Email Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Email Address</label>
            <div style={{ position: 'relative' }}>
              <Mail size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="input-field"
                style={{ paddingLeft: 40 }}
                disabled={loading}
              />
            </div>
          </div>

          {/* Password Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Password</label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-field"
                style={{ paddingLeft: 40 }}
                disabled={loading}
              />
            </div>
          </div>

          {/* Confirm Password (only for Sign Up) */}
          {isSignUp && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Confirm Password</label>
              <div style={{ position: 'relative' }}>
                <Lock size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="password"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  className="input-field"
                  style={{ paddingLeft: 40 }}
                  disabled={loading}
                />
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            className="btn-primary"
            style={{ padding: '12px', marginTop: 8 }}
            disabled={loading}
          >
            {loading ? (
              <span className="spinner-inline" />
            ) : (
              <>
                {isSignUp ? 'Create Account' : 'Sign In'} <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Divider */}
        <div style={{ display: 'flex', alignItems: 'center', margin: '24px 0 16px' }}>
          <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', padding: '0 12px', textTransform: 'uppercase', letterSpacing: 1 }}>or continue with</span>
          <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
        </div>

        {/* Google Sign In */}
        <button
          onClick={handleGoogleSignIn}
          className="btn-secondary"
          style={{ width: '100%', padding: '11px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, fontSize: '0.85rem' }}
          disabled={loading}
        >
          <svg width="18" height="18" viewBox="0 0 24 24">
            <path fill="#EA4335" d="M12 5.04c1.67 0 3.17.58 4.35 1.71l3.25-3.25C17.65 1.58 15 0 12 0 7.35 0 3.37 2.67 1.46 6.55l3.88 3.01C6.27 6.8 8.91 5.04 12 5.04z"/>
            <path fill="#4285F4" d="M23.49 12.27c0-.81-.07-1.59-.2-2.36H12v4.51h6.46c-.29 1.48-1.14 2.73-2.4 3.57l3.73 2.89c2.18-2 3.7-4.96 3.7-8.61z"/>
            <path fill="#FBBC05" d="M5.34 9.56c-.24-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29L1.46 6.55C.53 8.19 0 10.04 0 12s.53 3.81 1.46 5.45l3.88-3.01c-.24-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29z"/>
            <path fill="#34A853" d="M12 18.96c-3.09 0-5.73-1.76-6.66-4.52L1.46 17.45C3.37 21.33 7.35 24 12 24c3.05 0 5.89-.99 7.97-2.69l-3.73-2.89c-1.12.75-2.54 1.27-4.24 1.27z"/>
          </svg>
          Google Workspace
        </button>

      </div>
    </div>
  )
}
