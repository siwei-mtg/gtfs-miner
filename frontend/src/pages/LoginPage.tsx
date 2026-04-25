import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  Card,
  CardContent,
} from '@/components/ui/card';
import { Button } from '@/components/atoms/button';
import { Input } from '@/components/atoms/input';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface LoginPageProps {
  onSuccess?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onSuccess }) => {
  const { login, token } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (token) return <Navigate to="/" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      if (onSuccess) {
        onSuccess();
      } else {
        navigate('/', { replace: true });
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-[100svh] items-center justify-center bg-paper px-4 py-10">
      <div className="w-full max-w-sm">
        {/* Hero éditorial */}
        <div className="mb-8 text-center">
          <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-ink-muted">
            GTFS Miner
          </span>
          <h1 className="mt-2 font-display text-[44px] font-medium leading-[0.95] text-ink">
            Login
          </h1>
          <p className="mt-3 text-sm text-ink-muted">
            L'outil d'analyse GTFS qui se lit comme un atlas.
          </p>
        </div>

        <Card>
          <CardContent className="pt-6">
            {error && (
              <Alert variant="destructive" role="alert" className="mb-4">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="email"
                  className="text-[10px] font-medium uppercase tracking-[0.15em] text-ink-muted"
                >
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@example.com"
                />
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="password"
                  className="text-[10px] font-medium uppercase tracking-[0.15em] text-ink-muted"
                >
                  Mot de passe
                </label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                />
              </div>
              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? 'Connexion…' : 'Se connecter'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-sm text-ink-muted">
          Pas encore de compte&nbsp;?{' '}
          <a
            href="/register"
            className="font-medium text-ink underline decoration-signal decoration-2 underline-offset-4 hover:text-signal"
          >
            Créer un compte
          </a>
        </p>
      </div>
    </div>
  );
};
