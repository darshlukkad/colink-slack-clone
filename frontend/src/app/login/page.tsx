'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AuthService } from '@/lib/auth';
import { useAuthStore } from '@/store/authStore';
import { MessageSquare } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuthStore();

  useEffect(() => {
    console.log('Login page - isAuthenticated:', isAuthenticated, 'isLoading:', isLoading);
    if (isAuthenticated) {
      router.push('/channels');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleLogin = () => {
    const authUrl = AuthService.getAuthUrl();
    console.log('Redirecting to:', authUrl);
    window.location.href = authUrl;
  };

  // Don't block on loading for too long - show login after 2 seconds anyway
  // This prevents infinite loading states
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8">
        <div className="text-center">
          <div className="flex justify-center mb-6">
            <div className="bg-blue-600 p-4 rounded-2xl">
              <MessageSquare className="h-12 w-12 text-white" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Colink</h1>
          <p className="text-gray-600">Team communication made simple</p>
        </div>

        <div className="mt-8 space-y-4">
          <button
            onClick={handleLogin}
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
          >
            Sign in with Keycloak
          </button>

          <div className="text-center text-sm text-gray-500 mt-4">
            <p>Secure authentication powered by Keycloak</p>
          </div>
        </div>
      </div>
    </div>
  );
}
