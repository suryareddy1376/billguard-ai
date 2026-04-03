import React, { useState, useContext } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { Shield, ArrowRight, Loader } from 'lucide-react';

export default function Login() {
  const { user, login, signup } = useContext(AuthContext);
  const navigate = useNavigate();
  
  const [isLoginPath, setIsLoginPath] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  if (user) {
    return <Navigate to="/history" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    
    if (!email.trim() || !email.includes('@')) {
      setError('Please enter a valid email address.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    
    setLoading(true);
    try {
      if (isLoginPath) {
        await login(email, password);
        // Supabase context will dynamically update our user, triggering Navigate to dashboard
      } else {
        await signup(email, password);
        setMessage('Sign up successful! You may now sign in.');
        setIsLoginPath(true);
      }
    } catch (err) {
      // Catch native Supabase errors
      setError(err.message || 'Authentication failed. Please verify your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 80px)' }}>
      <div className="card animate-in" style={{ maxWidth: 400, width: '100%', padding: '2.5rem 2rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <Shield size={42} style={{ color: 'var(--teal-400)', marginBottom: '1rem' }} />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
            {isLoginPath ? "Welcome Back" : "Create Account"}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            {isLoginPath ? "Sign in to manage your medical bills." : "Join BillGuard to audit your bills securely."}
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label className="form-label">Email Address</label>
            <input
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="patient@example.com"
              required
            />
          </div>
          
          <div>
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          {error && <div className="text-danger" style={{ fontSize: '0.85rem', background: 'rgba(239, 68, 68, 0.1)', padding: '0.5rem', borderRadius: '4px' }}>{error}</div>}
          {message && <div style={{ fontSize: '0.85rem', color: 'var(--green-400)', background: 'rgba(52, 211, 153, 0.1)', padding: '0.5rem', borderRadius: '4px' }}>{message}</div>}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }} disabled={loading}>
            {loading ? <Loader size={16} className="spin" /> : (isLoginPath ? "Sign In" : "Sign Up")}
            {!loading && <ArrowRight size={16} />}
          </button>
        </form>

        <div style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          {isLoginPath ? "Don't have an account? " : "Already have an account? "}
          <button 
            type="button" 
            onClick={() => { setIsLoginPath(!isLoginPath); setError(''); setMessage(''); }}
            style={{ background: 'none', border: 'none', color: 'var(--teal-400)', cursor: 'pointer', padding: 0, fontWeight: 500 }}
          >
            {isLoginPath ? "Sign Up" : "Sign In"}
          </button>
        </div>
      </div>
    </div>
  );
}
