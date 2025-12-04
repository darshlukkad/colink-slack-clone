'use client';

import { useEffect } from 'react';
import { useThemeStore } from '@/store/themeStore';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { hydrate } = useThemeStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return <>{children}</>;
}
