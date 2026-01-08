import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, Package } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function Login({ isSignup = false }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('email', email);
      formData.append('password', password);

      const endpoint = isSignup ? '/api/auth/signup' : '/api/auth/login';
      const response = await axios.post(`${API_URL}${endpoint}`, formData);

      localStorage.setItem('token', response.data.token);
      localStorage.setItem('user_id', response.data.user_id);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-navy to-slate-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="bg-navy p-3 rounded-full">
              <Package className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-navy" data-testid="app-title">ExportAssist</h1>
          <p className="text-slate mt-2">
            {isSignup ? 'Create your account' : 'Welcome back'}
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4" data-testid="error-message">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} data-testid="auth-form">
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-medium mb-2" htmlFor="email">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 w-5 h-5 text-slate" />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                placeholder="your@email.com"
                required
                data-testid="email-input"
              />
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-gray-700 text-sm font-medium mb-2" htmlFor="password">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 w-5 h-5 text-slate" />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                placeholder="••••••••"
                required
                data-testid="password-input"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-navy text-white py-3 rounded-lg font-medium hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="submit-button"
          >
            {loading ? 'Please wait...' : (isSignup ? 'Sign Up' : 'Sign In')}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-gray-600">
            {isSignup ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button
              onClick={() => navigate(isSignup ? '/login' : '/signup')}
              className="text-navy font-medium hover:underline"
              data-testid="toggle-auth-mode"
            >
              {isSignup ? 'Sign In' : 'Sign Up'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
