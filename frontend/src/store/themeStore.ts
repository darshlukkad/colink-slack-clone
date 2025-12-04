'use client';

import { create } from 'zustand';

type Theme = 'light' | 'dark';

interface ThemeState {
  theme: Theme;
  isHydrated: boolean;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  hydrate: () => void;
}

export const useThemeStore = create<ThemeState>()((set, get) => ({
  theme: 'light',
  isHydrated: false,
  setTheme: (theme: Theme) => {
    set({ theme });
    // Update document class for Tailwind dark mode
    if (typeof window !== 'undefined') {
      localStorage.setItem('colink-theme', theme);
      if (theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
  },
  toggleTheme: () => {
    const newTheme = get().theme === 'light' ? 'dark' : 'light';
    get().setTheme(newTheme);
  },
  hydrate: () => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('colink-theme') as Theme | null;
      const theme = saved || 'light';
      set({ theme, isHydrated: true });
      if (theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
  },
}));
