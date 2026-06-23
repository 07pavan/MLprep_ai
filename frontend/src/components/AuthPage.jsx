import React, { useState, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import { Mail, Lock, Eye, EyeOff, ArrowRight, Sparkles, AlertCircle, ChevronRight } from 'lucide-react'

/* ── Animated floating orbs background ─────────────────────────── */
function FloatingOrbs() {
  return (
    <div style={{ position: 'fixed', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 0 }}>
      {/* Large amber orb top-right */}
      <div style={{
        position: 'absolute', top: '-120px', right: '-80px',
        width: 500, height: 500,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(217,119,6,0.12) 0%, rgba(217,119,6,0.04) 50%, transparent 70%)',
        animation: 'orbFloat1 8s ease-in-out infinite',
      }} />
      {/* Medium orb bottom-left */}
      <div style={{
        position: 'absolute', bottom: '-80px', left: '-60px',
        width: 380, height: 380,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(245,158,11,0.08) 0%, rgba(245,158,11,0.02) 50%, transparent 70%)',
        animation: 'orbFloat2 10s ease-in-out infinite',
      }} />
      {/* Small orb center */}
      <div style={{
        position: 'absolute', top: '40%', left: '15%',
        width: 200, height: 200,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(180,83,9,0.07) 0%, transparent 70%)',
        animation: 'orbFloat3 6s ease-in-out infinite',
      }} />
      {/* Grid overlay */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `
          linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)
        `,
        backgroundSize: '48px 48px',
        maskImage: 'radial-gradient(ellipse at center, black 20%, transparent 80%)',
      }} />
    </div>
  )
}

/* ── Feature pill ───────────────────────────────────────────────── */
function FeaturePill({ icon, label }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '5px 12px',
      borderRadius: 999,
      background: 'rgba(217,119,6,0.08)',
      border: '1px solid rgba(217,119,6,0.18)',
      fontSize: '0.72rem',
      color: 'var(--accent-2)',
      fontWeight: 500,
      whiteSpace: 'nowrap',
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
      {/* CSS animations */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
        @keyframes orbFloat1 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(-20px,30px) scale(1.05)} }
        @keyframes orbFloat2 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(30px,-20px) scale(1.08)} }
        @keyframes orbFloat3 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(20px,15px)} }
        @keyframes fadeSlideUp { from{opacity:0;transform:translateY(24px)} to{opacity:1;transform:translateY(0)} }
        @keyframes shimmer { 0%{background-position:200% center} 100%{background-position:-200% center} }
        .auth-card-enter { animation: fadeSlideUp 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
        .auth-input:focus { outline: none; border-color: rgba(217,119,6,0.5) !important; box-shadow: 0 0 0 3px rgba(217,119,6,0.08) !important; }
        .auth-input { transition: all 0.2s ease; }
        .auth-btn-primary { transition: all 0.2s ease; }
        .auth-btn-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(217,119,6,0.3) !important; }
        .auth-btn-primary:active:not(:disabled) { transform: translateY(0px); }
        .auth-google-btn:hover:not(:disabled) { background: rgba(255,255,255,0.06) !important; border-color: rgba(255,255,255,0.12) !important; }
        .tab-pill { transition: all 0.2s ease; }
        .tab-pill:hover { color: var(--text-primary) !important; }
      `}</style>

      <FloatingOrbs />

      <div style={{
        position: 'relative', zIndex: 1,
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px 16px',
        background: 'var(--bg-primary)',
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
              width: 64, height: 64,
              borderRadius: 20,
              background: 'linear-gradient(135deg, #D97706, #F59E0B)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 28,
              margin: '0 auto 16px',
              boxShadow: '0 8px 32px rgba(217,119,6,0.35), 0 0 0 1px rgba(217,119,6,0.2)',
            }}>
              🧠
            </div>
            <h1 style={{
              fontSize: '2rem', fontWeight: 800, letterSpacing: '-0.02em',
              background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 50%, #F59E0B 100%)',
              backgroundSize: '200% auto',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              animation: 'shimmer 3s linear infinite',
              marginBottom: 8,
            }}>
              MLPrep AI
            </h1>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Your AI-powered data analyst & ML preparation suite
            </p>

            {/* Feature pills */}
            <div style={{ display: 'flex', gap: 6, justifyContent: 'center', flexWrap: 'wrap', marginTop: 14 }}>
              <FeaturePill icon="📊" label="Smart Analysis" />
              <FeaturePill icon="🤖" label="AI Copilot" />
              <FeaturePill icon="⚡" label="Instant Insights" />
            </div>
          </div>

          {/* Card */}
          <div style={{
            background: 'rgba(20,19,16,0.8)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 20,
            padding: '32px 28px',
            boxShadow: '0 32px 64px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.03)',
          }}>

            {/* Dev mode banner */}
            {isMock && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 14px',
                background: 'rgba(59,130,246,0.08)',
                border: '1px solid rgba(59,130,246,0.2)',
                borderRadius: 10,
                marginBottom: 20,
                fontSize: '0.74rem',
                color: '#60a5fa',
              }}>
                <Sparkles size={13} />
                <span>Dev mode — any credentials will work</span>
              </div>
            )}

            {/* Tab switcher */}
            <div style={{
              display: 'flex',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12,
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
                    borderRadius: 9,
                    fontSize: '0.83rem', fontWeight: 600,
                    color: isSignUp === key ? 'var(--text-primary)' : 'var(--text-muted)',
                    background: isSignUp === key
                      ? 'linear-gradient(135deg, rgba(217,119,6,0.2), rgba(245,158,11,0.12))'
                      : 'transparent',
                    border: isSignUp === key ? '1px solid rgba(217,119,6,0.25)' : '1px solid transparent',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
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
                background: 'rgba(239,68,68,0.08)',
                border: '1px solid rgba(239,68,68,0.25)',
                borderRadius: 10, marginBottom: 20,
                fontSize: '0.8rem', color: '#fca5a5', lineHeight: 1.4,
              }}>
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>{error}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Email */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  Email Address
                </label>
                <div style={{ position: 'relative' }}>
                  <Mail size={15} style={{
                    position: 'absolute', left: 14, top: '50%',
                    transform: 'translateY(-50%)', color: 'var(--text-muted)',
                    pointerEvents: 'none',
                  }} />
                  <input
                    className="auth-input"
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    disabled={loading}
                    style={{
                      width: '100%', padding: '11px 14px 11px 40px',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 10, color: 'var(--text-primary)',
                      fontSize: '0.88rem',
                    }}
                  />
                </div>
              </div>

              {/* Password */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  Password
                </label>
                <div style={{ position: 'relative' }}>
                  <Lock size={15} style={{
                    position: 'absolute', left: 14, top: '50%',
                    transform: 'translateY(-50%)', color: 'var(--text-muted)',
                    pointerEvents: 'none',
                  }} />
                  <input
                    className="auth-input"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    disabled={loading}
                    style={{
                      width: '100%', padding: '11px 42px 11px 40px',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 10, color: 'var(--text-primary)',
                      fontSize: '0.88rem',
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    style={{
                      position: 'absolute', right: 12, top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted)', background: 'none', border: 'none',
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
                  <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                    Confirm Password
                  </label>
                  <div style={{ position: 'relative' }}>
                    <Lock size={15} style={{
                      position: 'absolute', left: 14, top: '50%',
                      transform: 'translateY(-50%)', color: 'var(--text-muted)',
                      pointerEvents: 'none',
                    }} />
                    <input
                      className="auth-input"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={e => setConfirmPassword(e.target.value)}
                      disabled={loading}
                      style={{
                        width: '100%', padding: '11px 14px 11px 40px',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: 10, color: 'var(--text-primary)',
                        fontSize: '0.88rem',
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                className="auth-btn-primary"
                disabled={loading}
                style={{
                  marginTop: 4,
                  padding: '13px',
                  borderRadius: 12,
                  background: 'linear-gradient(135deg, #D97706, #F59E0B)',
                  color: '#fff',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  border: 'none',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  boxShadow: '0 4px 16px rgba(217,119,6,0.2)',
                }}
              >
                {loading ? (
                  <div style={{
                    width: 18, height: 18, borderRadius: '50%',
                    border: '2px solid rgba(255,255,255,0.3)',
                    borderTopColor: '#fff',
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
            <div style={{ display: 'flex', alignItems: 'center', margin: '20px 0' }}>
              <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)' }} />
              <span style={{ padding: '0 14px', fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                or
              </span>
              <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)' }} />
            </div>

            {/* Google Sign In */}
            <button
              onClick={handleGoogleSignIn}
              className="auth-google-btn"
              disabled={loading}
              style={{
                width: '100%', padding: '12px',
                borderRadius: 12,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'var(--text-primary)',
                fontSize: '0.88rem', fontWeight: 600,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1,
                transition: 'all 0.2s ease',
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
              textAlign: 'center', marginTop: 20,
              fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.5,
            }}>
              By continuing, you agree to our{' '}
              <span style={{ color: 'var(--accent-2)', cursor: 'pointer' }}>Terms</span>
              {' & '}
              <span style={{ color: 'var(--accent-2)', cursor: 'pointer' }}>Privacy Policy</span>
            </p>
          </div>

          {/* Bottom tagline */}
          <div style={{ textAlign: 'center', marginTop: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
            {['No data stored externally', 'Free Groq AI included', 'Open source'].map((t, i) => (
              <span key={i} style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: 'var(--accent-1)' }}>✓</span> {t}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
