import React, { useEffect, useRef, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'react-hot-toast';
import toast from 'react-hot-toast';
import AppLayout from '@/layouts/AppLayout';
import Dashboard from '@/pages/Dashboard';
import DatasetExplorer from '@/pages/DatasetExplorer';
import AIChat from '@/pages/AIChat';
import VisualizationStudio from '@/pages/VisualizationStudio';
import DatasetsPage from '@/pages/DatasetsPage';
import VisualizationsPage from '@/pages/VisualizationsPage';
import AIInsightsPage from '@/pages/AIInsightsPage';
import AIChatPage from '@/pages/AIChatPage';
import JobsPage from '@/pages/JobsPage';
import { useAuthStore } from '@/store/auth';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

// ── Google Identity Services loader ───────────────────────────────────────────
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              type?: 'standard' | 'icon';
              theme?: 'outline' | 'filled_blue' | 'filled_black';
              size?: 'large' | 'medium' | 'small';
              text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
              shape?: 'rectangular' | 'pill' | 'circle' | 'square';
              width?: number;
              logo_alignment?: 'left' | 'center';
            }
          ) => void;
          prompt: () => void;
        };
      };
    };
  }
}

function useGoogleIdentity(onCredential: (idToken: string) => void) {
  const buttonRef = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    const init = () => {
      if (!window.google || !buttonRef.current) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: ({ credential }) => onCredential(credential),
      });
      window.google.accounts.id.renderButton(buttonRef.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'rectangular',
        width: 400,
      });
      setReady(true);
    };

    if (window.google) {
      init();
      return;
    }

    const existing = document.getElementById('google-gis-script');
    if (existing) {
      existing.addEventListener('load', init);
      return;
    }

    const script = document.createElement('script');
    script.id = 'google-gis-script';
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = init;
    document.head.appendChild(script);
  }, [onCredential]);

  return { buttonRef, ready };
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function LoginPage() {
  const navigate = useNavigate();
  const { login, register, googleLogin, isLoading } = useAuthStore();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleGoogleCredential = async (idToken: string) => {
    setError('');
    try {
      await googleLogin(idToken);
      toast.success('Signed in with Google');
      navigate('/', { replace: true });
    } catch {
      setError('Google sign-in failed. Please try again.');
    }
  };

  const { buttonRef } = useGoogleIdentity(handleGoogleCredential);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register({
          email,
          username,
          password,
          full_name: fullName || undefined,
        });
      }
      toast.success(mode === 'login' ? 'Welcome back!' : 'Account created');
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (mode === 'login'
          ? 'Invalid email or password'
          : 'Could not create account. Email or username may already be in use.');
      setError(detail);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">CSV Stats API</h1>
          <p className="text-gray-400 mt-2">Enterprise Dataset Intelligence Platform</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-4"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </h2>
            <button
              type="button"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login');
                setError('');
              }}
              className="text-sm text-indigo-400 hover:text-indigo-300"
            >
              {mode === 'login' ? "Don't have an account? Sign up" : 'Have an account? Sign in'}
            </button>
          </div>

          {error && (
            <div className="p-3 bg-red-900/30 border border-red-800 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {mode === 'register' && (
            <>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Full name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                  placeholder="Jane Doe"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  minLength={3}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                  placeholder="janedoe"
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-sm text-gray-400 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-xl transition-colors"
          >
            {isLoading
              ? mode === 'login'
                ? 'Signing in...'
                : 'Creating account...'
              : mode === 'login'
                ? 'Sign in'
                : 'Create account'}
          </button>

          {GOOGLE_CLIENT_ID && (
            <>
              <div className="flex items-center gap-3 my-2">
                <div className="flex-1 h-px bg-gray-800" />
                <span className="text-xs text-gray-500 uppercase tracking-wider">or</span>
                <div className="flex-1 h-px bg-gray-800" />
              </div>

              <div ref={buttonRef} className="flex justify-center" />
            </>
          )}
        </form>
      </div>
    </div>
  );
}

export default function App() {
  const { loadUser } = useAuthStore();

  useEffect(() => {
    loadUser();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="datasets" element={<DatasetsPage />} />
            <Route path="datasets/:id" element={<DatasetExplorer />} />
            <Route path="datasets/:id/chat" element={<AIChat />} />
            <Route path="visualizations/:id" element={<VisualizationStudio />} />
            <Route path="visualizations" element={<VisualizationsPage />} />
            <Route path="ai-insights" element={<AIInsightsPage />} />
            <Route path="chat" element={<AIChatPage />} />
            <Route path="jobs" element={<JobsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#1f2937',
            color: '#f9fafb',
            border: '1px solid #374151',
          },
        }}
      />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}