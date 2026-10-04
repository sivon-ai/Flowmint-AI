import { useState } from 'react';
import { api } from '../lib/api';
import type { User } from '../types';
import { Zap } from 'lucide-react';

interface Props {
  onLogin: (user: User, accessToken: string, refreshToken: string) => void;
}

export default function LoginPage({ onLogin }: Props) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('admin@techmart.in');
  const [password, setPassword] = useState('admin123');
  const [merchantName, setMerchantName] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let tokenRes;
      if (isRegister) {
        tokenRes = await api.post<{ access_token: string; refresh_token: string }>(
          '/auth/register',
          { merchant_name: merchantName, email, password, full_name: fullName }
        );
      } else {
        tokenRes = await api.post<{ access_token: string; refresh_token: string }>(
          '/auth/login',
          { email, password }
        );
      }

      if (tokenRes.data) {
        api.setToken(tokenRes.data.access_token);
        api.setRefreshToken(tokenRes.data.refresh_token);

        const userRes = await api.get<User>('/auth/me');
        if (userRes.data) {
          onLogin(userRes.data, tokenRes.data.access_token, tokenRes.data.refresh_token);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-surface-950 via-surface-900 to-brand-950/30" />
      <div className="fixed top-1/4 left-1/4 w-96 h-96 bg-brand-600/5 rounded-full blur-3xl" />
      <div className="fixed bottom-1/4 right-1/4 w-80 h-80 bg-brand-500/5 rounded-full blur-3xl" />

      <div className="relative card p-8 w-full max-w-md animate-fade-in">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="p-2.5 bg-brand-600/20 rounded-xl">
            <Zap className="w-7 h-7 text-brand-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Flowmint AI</h1>
            <p className="text-xs text-surface-300 font-medium">Revenue Operating System</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <>
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">
                  Business Name
                </label>
                <input
                  type="text"
                  className="input-field w-full"
                  value={merchantName}
                  onChange={e => setMerchantName(e.target.value)}
                  placeholder="Your business name"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">
                  Full Name
                </label>
                <input
                  type="text"
                  className="input-field w-full"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  placeholder="Your full name"
                  required
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1.5">Email</label>
            <input
              type="email"
              className="input-field w-full"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1.5">Password</label>
            <input
              type="password"
              className="input-field w-full"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={8}
            />
          </div>

          {error && (
            <div className="bg-danger-500/10 border border-danger-500/20 text-danger-500 text-sm px-4 py-2.5 rounded-lg">
              {error}
            </div>
          )}

          <button type="submit" className="btn-primary w-full py-2.5" disabled={loading}>
            {loading ? 'Please wait...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            className="text-sm text-surface-300 hover:text-brand-400 transition-colors"
            onClick={() => { setIsRegister(!isRegister); setError(''); }}
          >
            {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
          </button>
        </div>

        {!isRegister && (
          <div className="mt-4 text-center text-xs text-surface-300/60">
            Demo: admin@techmart.in / admin123
          </div>
        )}
      </div>
    </div>
  );
}
