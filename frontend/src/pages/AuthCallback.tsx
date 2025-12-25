import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Loader2 } from 'lucide-react';

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [processed, setProcessed] = useState(false);

  // Process the callback parameters
  useEffect(() => {
    if (processed) return;
    
    const token = searchParams.get('token');
    const userStr = searchParams.get('user');

    console.log('AuthCallback: Processing callback', { token: !!token, userStr: !!userStr });

    if (token && userStr) {
      try {
        const user = JSON.parse(decodeURIComponent(userStr));
        console.log('AuthCallback: User parsed successfully', user);
        login(token, user);
        setProcessed(true);
      } catch (e) {
        console.error("AuthCallback: Failed to parse user data", e);
        setError("Failed to process authentication. Please try again.");
        setTimeout(() => navigate('/login'), 3000);
      }
    } else {
      console.error("AuthCallback: Missing token or user in URL");
      setError("Invalid authentication response. Redirecting to login...");
      setTimeout(() => navigate('/login'), 2000);
    }
  }, [searchParams, login, processed]);

  // Navigate after auth state is confirmed
  useEffect(() => {
    if (processed && isAuthenticated) {
      console.log('AuthCallback: Auth confirmed, navigating to dashboard');
      navigate('/dashboard', { replace: true });
    }
  }, [processed, isAuthenticated, navigate]);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      backgroundColor: '#0f172a',
      color: 'white'
    }}>
      <div style={{ textAlign: 'center' }}>
        {error ? (
          <>
            <div style={{ color: '#ef4444', marginBottom: '1rem', fontSize: '1.1rem' }}>{error}</div>
            <p style={{ color: '#94a3b8' }}>Redirecting to login...</p>
          </>
        ) : (
          <>
            <Loader2 
              size={40} 
              style={{ 
                animation: 'spin 1s linear infinite',
                color: '#6366f1',
                marginBottom: '1rem'
              }} 
            />
            <h2 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '0.5rem' }}>
              Completing Sign In...
            </h2>
            <p style={{ color: '#94a3b8' }}>Please wait while we set up your session.</p>
          </>
        )}
      </div>
    </div>
  );
}
