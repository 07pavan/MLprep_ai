import React, { useState, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import { Mail, Lock, Eye, EyeOff, ArrowRight, Sparkles, AlertCircle } from 'lucide-react'

/* ── Feature pill ───────────────────────────────────────────────── */
function FeaturePill({ icon, label }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '6px 14px',
      borderRadius: 'var(--radius-sm)',
      background: 'var(--color-slate)',
      border: '1px solid var(--color-iron)',
      fontSize: '0.74rem',
      color: 'var(--color-bone)',
      fontWeight: 500,
      whiteSpace: 'nowrap',
      boxShadow: 'none',
    }}>
      <span>{icon}</span>
      <span>{label}</span>
    </div>
  )
}

export default function AuthPage() {
  const { logIn, signUp, logInWithGoogle, isMock } = useAuth()
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

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
      const msg = err.message || 'Authentication failed.'
      setError(msg.replace('Firebase:', '').replace('auth/', '').trim())
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
      setError(err.message || 'Google Sign-In failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* CSS overrides */}
      <style>{`
        @keyframes fadeSlideUp { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
        .auth-card-enter { animation: fadeSlideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        .auth-input { transition: border-color 0.15s ease-in-out; }
        .auth-input:focus { outline: none; border-color: var(--color-ember-gold) !important; }
        .tab-pill { transition: all 0.15s ease-in-out; }
        .tab-pill:hover { color: var(--color-paper) !important; }
      `}</style>

      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px 16px',
        background: 'var(--bg-primary)',
        fontFamily: 'var(--font-sans)',
      }}>
        <div
          className="auth-card-enter"
          style={{
            width: '100%',
            maxWidth: 440,
            opacity: mounted ? 1 : 0,
          }}
        >
          {/* Logo + Brand */}
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <div style={{
              width: 56, height: 56,
              borderRadius: 'var(--radius-sm)',
              background: 'var(--color-vermillion-signal)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 26,
              margin: '0 auto 16px',
              boxShadow: 'none',
            }}>
              🧠
            </div>
            <h1 style={{
              fontSize: '2rem', fontWeight: 600, letterSpacing: '-0.025em',
              color: 'var(--color-paper)',
              marginBottom: 8,
            }}>
              MLPrep AI<span style={{ color: 'var(--color-vermillion-signal)' }}>*</span>
            </h1>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Your AI-powered data analyst & ML preparation suite
            </p>

            {/* Feature pills */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginTop: 16 }}>
              <FeaturePill icon="📊" label="Smart Analysis" />
              <FeaturePill icon="🤖" label="AI Copilot" />
              <FeaturePill icon="⚡" label="Instant Insights" />
            </div>
          </div>

          {/* Card */}
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '36px 32px',
            boxShadow: 'none',
          }}>

            {/* Dev mode banner */}
            {isMock && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '10px 14px',
                background: 'var(--color-slate)',
                border: '1px solid var(--color-iron)',
                borderRadius: 'var(--radius-md)',
                marginBottom: 20,
                fontSize: '0.76rem',
                color: 'var(--color-bone)',
                fontWeight: 500,
              }}>
                <Sparkles size={13} style={{ color: 'var(--color-vermillion-signal)' }} />
                <span>Dev mode — any credentials will work</span>
              </div>
            )}

            {/* Tab switcher */}
            <div style={{
              display: 'flex',
              background: 'var(--color-inkwell)',
              border: '1px solid var(--color-iron)',
              borderRadius: 'var(--radius-md)',
              padding: 4,
              marginBottom: 24,
            }}>
              {[
                { key: false, label: 'Sign In' },
                { key: true, label: 'Create Account' },
              ].map(({ key, label }) => (
                <button
                  key={String(key)}
                  className="tab-pill"
                  onClick={() => { setIsSignUp(key); setError('') }}
                  style={{
                    flex: 1, padding: '9px 12px',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.83rem', fontWeight: 600,
                    color: isSignUp === key ? '#ffffff' : 'var(--text-muted)',
                    background: isSignUp === key
                      ? 'var(--color-vermillion-signal)'
                      : 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Error */}
            {error && (
              <div style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: '12px 14px',
                background: 'rgba(204, 145, 102, 0.05)',
                border: '1px solid rgba(204, 145, 102, 0.2)',
                borderRadius: 'var(--radius-md)', marginBottom: 20,
                fontSize: '0.8rem', color: 'var(--color-vermillion-signal)', lineHeight: 1.4,
              }}>
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>{error}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Email */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--color-silver)', letterSpacing: '0.025em', textTransform: 'uppercase' }}>
                  Email Address
                </label>
                <div style={{ position: 'relative' }}>
                  <Mail size={15} style={{
                    position: 'absolute', left: 14, top: '50%',
                    transform: 'translateY(-50%)', color: 'var(--color-mist)',
                    pointerEvents: 'none',
                  }} />
                  <input
                    className="auth-input input-field"
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    disabled={loading}
                    style={{
                      paddingLeft: 40,
                    }}
                  />
                </div>
              </div>

              {/* Password */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--color-silver)', letterSpacing: '0.025em', textTransform: 'uppercase' }}>
                  Password
                </label>
                <div style={{ position: 'relative' }}>
                  <Lock size={15} style={{
                    position: 'absolute', left: 14, top: '50%',
                    transform: 'translateY(-50%)', color: 'var(--color-mist)',
                    pointerEvents: 'none',
                  }} />
                  <input
                    className="auth-input input-field"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    disabled={loading}
                    style={{
                      paddingLeft: 40,
                      paddingRight: 40,
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    style={{
                      position: 'absolute', right: 12, top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--color-mist)', background: 'none', border: 'none',
                      cursor: 'pointer', padding: 4,
                    }}
                  >
                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              {/* Confirm Password */}
              {isSignUp && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--color-silver)', letterSpacing: '0.025em', textTransform: 'uppercase' }}>
                    Confirm Password
                  </label>
                  <div style={{ position: 'relative' }}>
                    <Lock size={15} style={{
                      position: 'absolute', left: 14, top: '50%',
                      transform: 'translateY(-50%)', color: 'var(--color-mist)',
                      pointerEvents: 'none',
                    }} />
                    <input
                      className="auth-input input-field"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={e => setConfirmPassword(e.target.value)}
                      disabled={loading}
                      style={{
                        paddingLeft: 40,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                className="btn-primary"
                disabled={loading}
                style={{
                  marginTop: 4,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                }}
              >
                {loading ? (
                  <div style={{
                    width: 18, height: 18, borderRadius: '50%',
                    border: '2px solid rgba(255,255,255,0.3)',
                    borderTopColor: 'var(--color-inkwell)',
                    animation: 'spin 0.7s linear infinite',
                  }} />
                ) : (
                  <>
                    {isSignUp ? 'Create Account' : 'Sign In'}
                    <ArrowRight size={17} />
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            <div style={{ display: 'flex', alignItems: 'center', margin: '24px 0' }}>
              <div style={{ flex: 1, height: 1, background: 'var(--color-iron)' }} />
              <span style={{ padding: '0 14px', fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                or
              </span>
              <div style={{ flex: 1, height: 1, background: 'var(--color-iron)' }} />
            </div>

            {/* Google Sign In */}
            <button
              onClick={handleGoogleSignIn}
              className="btn-secondary"
              disabled={loading}
              style={{
                width: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1,
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#EA4335" d="M12 5.04c1.67 0 3.17.58 4.35 1.71l3.25-3.25C17.65 1.58 15 0 12 0 7.35 0 3.37 2.67 1.46 6.55l3.88 3.01C6.27 6.8 8.91 5.04 12 5.04z"/>
                <path fill="#4285F4" d="M23.49 12.27c0-.81-.07-1.59-.2-2.36H12v4.51h6.46c-.29 1.48-1.14 2.73-2.4 3.57l3.73 2.89c2.18-2 3.7-4.96 3.7-8.61z"/>
                <path fill="#FBBC05" d="M5.34 9.56c-.24-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29L1.46 6.55C.53 8.19 0 10.04 0 12s.53 3.81 1.46 5.45l3.88-3.01c-.24-.72-.38-1.49-.38-2.29z"/>
                <path fill="#34A853" d="M12 18.96c-3.09 0-5.73-1.76-6.66-4.52L1.46 17.45C3.37 21.33 7.35 24 12 24c3.05 0 5.89-.99 7.97-2.69l-3.73-2.89c-1.12.75-2.54 1.27-4.24 1.27z"/>
              </svg>
              Continue with Google
            </button>

            {/* Footer note */}
            <p style={{
              textAlign: 'center', marginTop: 24,
              fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.5,
            }}>
              By continuing, you agree to our{' '}
              <span style={{ color: 'var(--color-vermillion-signal)', cursor: 'pointer', fontWeight: 500 }}>Terms</span>
              {' & '}
              <span style={{ color: 'var(--color-vermillion-signal)', cursor: 'pointer', fontWeight: 500 }}>Privacy Policy</span>
            </p>
          </div>

          {/* Bottom tagline */}
          <div style={{ textAlign: 'center', marginTop: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
            {['No data stored externally', 'Free Groq AI included', 'Open source'].map((t, i) => (
              <span key={i} style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: 'var(--color-vermillion-signal)', fontWeight: 'bold' }}>✓</span> {t}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
