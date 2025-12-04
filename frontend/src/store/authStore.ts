import { create } from 'zustand';
import type { User, AuthTokens } from '@/types';
import { AuthService } from '@/lib/auth';

interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  // Actions
  setAuth: (user: User, tokens: AuthTokens) => void;
  setUser: (user: User) => void;
  clearAuth: () => void;
  initializeAuth: () => Promise<void>;
  refreshTokens: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  tokens: null,
  isAuthenticated: false,
  isLoading: true,

  setAuth: (user, tokens) => {
    AuthService.saveUser(user);
    AuthService.saveTokens(tokens);
    set({ user, tokens, isAuthenticated: true, isLoading: false });
  },

  setUser: (user) => {
    AuthService.saveUser(user);
    set({ user });
  },

  clearAuth: () => {
    AuthService.clearAuth();
    set({ user: null, tokens: null, isAuthenticated: false, isLoading: false });
  },

  initializeAuth: async () => {
    try {
      const tokens = AuthService.getTokens();
      const user = AuthService.getUser();

      console.log('initializeAuth - tokens:', tokens ? 'present' : 'missing', 'user:', user?.username || 'missing');

      if (!tokens || !user) {
        set({ isLoading: false });
        return;
      }

      // Check if token is expired
      if (AuthService.isTokenExpired(tokens.access_token)) {
        console.log('Token expired, attempting refresh...');
        // Try to refresh
        try {
          await get().refreshTokens();
        } catch (error) {
          console.error('Token refresh failed:', error);
          get().clearAuth();
        }
      } else {
        console.log('Token valid, setting authenticated state');
        set({ user, tokens, isAuthenticated: true, isLoading: false });
      }
    } catch (error) {
      console.error('Failed to initialize auth:', error);
      get().clearAuth();
    }
  },

  refreshTokens: async () => {
    const { tokens } = get();
    if (!tokens?.refresh_token) {
      throw new Error('No refresh token available');
    }

    const newTokens = await AuthService.refreshToken(tokens.refresh_token);
    const user = await AuthService.getCurrentUser(newTokens.access_token);

    get().setAuth(user, newTokens);
  },

  logout: async () => {
    const { tokens } = get();

    if (tokens?.refresh_token) {
      try {
        await AuthService.logout(tokens.refresh_token);
      } catch (error) {
        console.error('Logout error:', error);
      }
    }

    get().clearAuth();
  },
}));
