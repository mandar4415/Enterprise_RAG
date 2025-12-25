import React, { useState } from 'react';
import { 
  Lock, 
  Mail, 
  ArrowRight, 
  ShieldCheck, 
  Cpu, 
  Globe,
  Loader2
} from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { authService } from '../api/services';
import { useAuth } from '../hooks/useAuth';
import './Login.css';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await authService.login(email, password);
      login(response.access_token, response.user);
      navigate('/dashboard');
    } catch (err: any) {
      console.error("Login failed:", err);
      setError(err.response?.data?.detail || "Login failed. Please check your credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setIsGoogleLoading(true);
    setError(null);
    try {
      const url = await authService.getGoogleLoginUrl();
      window.location.href = url;
    } catch (err: any) {
      console.error("Google login init failed:", err);
      setError("Failed to connect to Google. Please try again.");
      setIsGoogleLoading(false);
    }
  };

  return (
    <div className="login-container">
      
      {/* LEFT: Visualization Panel */}
      <div className="visual-panel">
        <div className="glow-effect">
          <div className="glow-blob glow-indigo" style={{ top: '-20%', left: '-20%' }} />
          <div className="glow-blob glow-emerald" style={{ bottom: '-20%', right: '-20%' }} />
        </div>
        
        <div className="content-wrapper">
          <div className="brand-header">
            <div className="icon-box">
              <Cpu size={32} color="#818cf8" />
            </div>
            <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: 'white' }}>
              Enterprise <span style={{ color: '#818cf8' }}>RAG</span>
            </h1>
          </div>
          
          <h2 className="hero-title">
            Knowledge Access, <br/>
            <span className="gradient-text-hero">
              Reimagined.
            </span>
          </h2>
          
          <p className="hero-desc">
            Securely query your organization's entire document repository with 
            AI-powered precision, full traceability, and enterprise-grade security.
          </p>

          <div className="feature-grid">
            <div className="feature-card">
              <ShieldCheck size={24} color="#34d399" style={{ marginBottom: '0.75rem' }} />
              <h3 style={{ fontWeight: '600', color: '#e2e8f0', marginBottom: '0.25rem' }}>Secure Access</h3>
              <p style={{ fontSize: '0.875rem', color: '#64748b' }}>End-to-end encryption & Role-based control</p>
            </div>
            <div className="feature-card">
              <Globe size={24} color="#818cf8" style={{ marginBottom: '0.75rem' }} />
              <h3 style={{ fontWeight: '600', color: '#e2e8f0', marginBottom: '0.25rem' }}>Global Search</h3>
              <p style={{ fontSize: '0.875rem', color: '#64748b' }}>Retrieve from any ingested document</p>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT: Login Form */}
      <div className="login-form-panel">
        <div className="mobile-bg" />

        <div className="login-card">
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'white', marginBottom: '0.5rem' }}>Welcome Back</h2>
            <p style={{ color: '#94a3b8' }}>Sign in to access your workspace</p>
          </div>

          {/* Error Message */}
          {error && (
            <div style={{
              padding: '0.75rem 1rem',
              marginBottom: '1rem',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '0.5rem',
              color: '#fca5a5',
              fontSize: '0.875rem'
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#cbd5e1', marginBottom: '0.5rem' }}>Email Address</label>
              <div className="input-wrapper">
                <Mail className="input-icon" size={20} />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field input-with-icon"
                  placeholder="name@company.com"
                  required
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <label style={{ fontSize: '0.875rem', fontWeight: '500', color: '#cbd5e1' }}>Password</label>
                <a href="#" style={{ fontSize: '0.75rem', color: '#818cf8', textDecoration: 'none' }}>Forgot password?</a>
              </div>
              <div className="input-wrapper">
                <Lock className="input-icon" size={20} />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field input-with-icon"
                  placeholder="••••••••"
                  required
                  disabled={isLoading}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary"
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '1.5rem' }}
            >
              {isLoading ? (
                <>
                  <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={20} />
                </>
              )}
            </button>
          </form>

          <div className="divider">
            <span className="divider-text">Or continue with</span>
          </div>

          <button 
            type="button"
            className="google-btn"
            onClick={handleGoogleLogin}
            disabled={isGoogleLoading}
          >
            {isGoogleLoading ? (
              <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            )}
            <span>Sign in with Google</span>
          </button>

          <div style={{ textAlign: 'center', marginTop: '1.5rem', color: '#94a3b8', fontSize: '0.875rem' }}>
            Don't have an account?{' '}
            <Link to="/signup" style={{ color: '#818cf8', textDecoration: 'none', fontWeight: 500 }}>
              Sign up
            </Link>
          </div>

        </div>
      </div>
    </div>
  );
}
