import { useState, useRef, useEffect } from 'react';
import { 
  Lock, 
  Mail, 
  User as UserIcon,
  ArrowRight, 
  ArrowLeft,
  CheckCircle,
  Loader2,
  Cpu,
  Shield,
  Zap
} from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { authService } from '../api/services';
import { useAppDispatch } from '../store/hooks';
import { setCredentials } from '../features/auth/authSlice';
import './Signup.css';
import './Login.css'; // Reuse some Login styles

type Step = 'signup' | 'verify' | 'success';

export default function Signup() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  
  // Form state
  const [step, setStep] = useState<Step>('signup');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);
  
  // OTP input refs
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Resend cooldown timer
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  // Password strength check
  const getPasswordStrength = (pwd: string) => {
    if (pwd.length < 8) return 'weak';
    const hasUpper = /[A-Z]/.test(pwd);
    const hasLower = /[a-z]/.test(pwd);
    const hasNumber = /[0-9]/.test(pwd);
    const hasSpecial = /[!@#$%^&*]/.test(pwd);
    const score = [hasUpper, hasLower, hasNumber, hasSpecial].filter(Boolean).length;
    if (score >= 3 && pwd.length >= 10) return 'strong';
    if (score >= 2) return 'medium';
    return 'weak';
  };

  // Handle signup form submission
  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      await authService.signup(name, email, password);
      setStep('verify');
      setResendCooldown(60); // 60 second cooldown for resend
    } catch (err: any) {
      console.error('Signup failed:', err);
      setError(err.response?.data?.detail || 'Signup failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle OTP input
  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) {
      // Handle paste
      const chars = value.slice(0, 6).split('');
      const newOtp = [...otp];
      chars.forEach((char, i) => {
        if (index + i < 6) newOtp[index + i] = char;
      });
      setOtp(newOtp);
      // Focus last filled or next empty
      const nextIndex = Math.min(index + chars.length, 5);
      otpRefs.current[nextIndex]?.focus();
    } else {
      const newOtp = [...otp];
      newOtp[index] = value;
      setOtp(newOtp);
      
      // Auto-focus next input
      if (value && index < 5) {
        otpRefs.current[index + 1]?.focus();
      }
    }
  };

  // Handle OTP backspace
  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  // Verify OTP
  const handleVerifyOtp = async () => {
    const otpCode = otp.join('');
    if (otpCode.length !== 6) {
      setError('Please enter the complete 6-digit code');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await authService.verifyOtp(email, otpCode);
      // Save auth data
      dispatch(setCredentials({ token: response.access_token, user: response.user }));
      setStep('success');
      
      // Auto redirect after 2 seconds
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    } catch (err: any) {
      console.error('OTP verification failed:', err);
      setError(err.response?.data?.detail || 'Invalid OTP. Please try again.');
      setOtp(['', '', '', '', '', '']);
      otpRefs.current[0]?.focus();
    } finally {
      setIsLoading(false);
    }
  };

  // Resend OTP
  const handleResendOtp = async () => {
    if (resendCooldown > 0) return;
    
    setIsLoading(true);
    setError(null);

    try {
      await authService.resendOtp(email);
      setResendCooldown(60);
      setOtp(['', '', '', '', '', '']);
    } catch (err: any) {
      console.error('Resend OTP failed:', err);
      setError(err.response?.data?.detail || 'Failed to resend OTP.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="signup-container">
      {/* LEFT: Visual Panel */}
      <div className="signup-visual-panel">
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
            Join the Future of <br/>
            <span className="gradient-text-hero">
              Knowledge Discovery.
            </span>
          </h2>
          
          <p className="hero-desc">
            Create your account to access AI-powered document intelligence 
            with full traceability and enterprise-grade security.
          </p>

          <div className="feature-grid">
            <div className="feature-card">
              <Shield size={24} color="#34d399" style={{ marginBottom: '0.75rem' }} />
              <h3 style={{ fontWeight: '600', color: '#e2e8f0', marginBottom: '0.25rem' }}>Secure by Design</h3>
              <p style={{ fontSize: '0.875rem', color: '#64748b' }}>Your data stays private and encrypted</p>
            </div>
            <div className="feature-card">
              <Zap size={24} color="#818cf8" style={{ marginBottom: '0.75rem' }} />
              <h3 style={{ fontWeight: '600', color: '#e2e8f0', marginBottom: '0.25rem' }}>Instant Setup</h3>
              <p style={{ fontSize: '0.875rem', color: '#64748b' }}>Get started in under 2 minutes</p>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT: Form Panel */}
      <div className="signup-form-panel">
        <div className="signup-card">
          
          {/* Step Indicator */}
          <div className="step-indicator">
            <div className={`step-dot ${step === 'signup' ? 'active' : ''} ${step !== 'signup' ? 'completed' : ''}`} />
            <div className={`step-dot ${step === 'verify' ? 'active' : ''} ${step === 'success' ? 'completed' : ''}`} />
            <div className={`step-dot ${step === 'success' ? 'active completed' : ''}`} />
          </div>

          {/* STEP 1: Signup Form */}
          {step === 'signup' && (
            <>
              <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'white', marginBottom: '0.5rem' }}>
                  Create Account
                </h2>
                <p style={{ color: '#94a3b8' }}>Enter your details to get started</p>
              </div>

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

              <form onSubmit={handleSignup}>
                {/* Name */}
                <div className="form-group">
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                    Full Name
                  </label>
                  <div className="input-wrapper">
                    <UserIcon className="input-icon" size={20} />
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="input-field input-with-icon"
                      placeholder="John Doe"
                      required
                      minLength={2}
                      disabled={isLoading}
                    />
                  </div>
                </div>

                {/* Email */}
                <div className="form-group">
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                    Email Address
                  </label>
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

                {/* Password */}
                <div className="form-group">
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                    Password
                  </label>
                  <div className="input-wrapper">
                    <Lock className="input-icon" size={20} />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="input-field input-with-icon"
                      placeholder="••••••••"
                      required
                      minLength={8}
                      disabled={isLoading}
                    />
                  </div>
                  {password && (
                    <>
                      <div className="password-strength">
                        <div className={`password-strength-bar ${getPasswordStrength(password)}`} />
                      </div>
                      <p className="password-hint">
                        {getPasswordStrength(password) === 'weak' && 'Add uppercase, numbers, or symbols for stronger password'}
                        {getPasswordStrength(password) === 'medium' && 'Good password! Add more variety for extra security'}
                        {getPasswordStrength(password) === 'strong' && '✓ Strong password'}
                      </p>
                    </>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={isLoading || password.length < 8}
                  className="btn-primary"
                  style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '1.5rem' }}
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
                      <span>Creating Account...</span>
                    </>
                  ) : (
                    <>
                      <span>Create Account</span>
                      <ArrowRight size={20} />
                    </>
                  )}
                </button>
              </form>

              <p style={{ textAlign: 'center', marginTop: '1.5rem', color: '#94a3b8', fontSize: '0.875rem' }}>
                Already have an account?{' '}
                <Link to="/login" style={{ color: '#818cf8', textDecoration: 'none', fontWeight: 500 }}>
                  Sign in
                </Link>
              </p>
            </>
          )}

          {/* STEP 2: OTP Verification */}
          {step === 'verify' && (
            <>
              <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                <div style={{ 
                  width: 60, 
                  height: 60, 
                  margin: '0 auto 1rem',
                  background: 'rgba(99, 102, 241, 0.1)',
                  border: '1px solid rgba(99, 102, 241, 0.2)',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Mail size={28} color="#818cf8" />
                </div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'white', marginBottom: '0.5rem' }}>
                  Verify Your Email
                </h2>
                <p style={{ color: '#94a3b8' }}>
                  We sent a 6-digit code to<br />
                  <span style={{ color: '#818cf8', fontWeight: 500 }}>{email}</span>
                </p>
              </div>

              {error && (
                <div style={{
                  padding: '0.75rem 1rem',
                  marginBottom: '1rem',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: '0.5rem',
                  color: '#fca5a5',
                  fontSize: '0.875rem',
                  textAlign: 'center'
                }}>
                  {error}
                </div>
              )}

              {/* OTP Inputs */}
              <div className="otp-input-group">
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => { otpRefs.current[index] = el; }}
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={digit}
                    onChange={(e) => handleOtpChange(index, e.target.value.replace(/\D/g, ''))}
                    onKeyDown={(e) => handleOtpKeyDown(index, e)}
                    className={`otp-input ${digit ? 'filled' : ''}`}
                    disabled={isLoading}
                    autoFocus={index === 0}
                  />
                ))}
              </div>

              <button
                onClick={handleVerifyOtp}
                disabled={isLoading || otp.join('').length !== 6}
                className="btn-primary"
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
              >
                {isLoading ? (
                  <>
                    <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
                    <span>Verifying...</span>
                  </>
                ) : (
                  <>
                    <span>Verify & Continue</span>
                    <ArrowRight size={20} />
                  </>
                )}
              </button>

              <div className="resend-link">
                Didn't receive the code?{' '}
                <button onClick={handleResendOtp} disabled={resendCooldown > 0 || isLoading}>
                  {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend OTP'}
                </button>
              </div>

              <button
                onClick={() => setStep('signup')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  width: '100%',
                  marginTop: '1rem',
                  padding: '0.75rem',
                  background: 'transparent',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '0.5rem',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                <ArrowLeft size={18} />
                <span>Back to Signup</span>
              </button>
            </>
          )}

          {/* STEP 3: Success */}
          {step === 'success' && (
            <div style={{ textAlign: 'center' }}>
              <div className="success-icon">
                <CheckCircle size={40} color="#10b981" />
              </div>
              <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'white', marginBottom: '0.5rem' }}>
                Welcome Aboard!
              </h2>
              <p style={{ color: '#94a3b8', marginBottom: '2rem' }}>
                Your account has been verified successfully.<br />
                Redirecting to dashboard...
              </p>
              <Loader2 size={24} color="#6366f1" style={{ animation: 'spin 1s linear infinite' }} />
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
