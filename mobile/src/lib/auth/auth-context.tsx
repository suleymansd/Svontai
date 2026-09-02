import { useQueryClient } from '@tanstack/react-query';
import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { getMe, login as loginRequest, logout as logoutRequest } from '@/lib/api/endpoints';
import { clearMobileSession, restoreMobileSession, setSessionExpiredHandler } from '@/lib/api/client';
import type { MeContext } from '@/lib/api/types';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

type AuthContextValue = {
  status: AuthStatus;
  me: MeContext | null;
  signIn: (email: string, password: string, twoFactorCode?: string) => Promise<void>;
  signOut: () => Promise<void>;
  reloadProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [me, setMe] = useState<MeContext | null>(null);

  const expireSession = useCallback(() => {
    setMe(null);
    setStatus('unauthenticated');
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setSessionExpiredHandler(expireSession);
    return () => setSessionExpiredHandler(null);
  }, [expireSession]);

  const reloadProfile = useCallback(async () => {
    const profile = await getMe();
    setMe(profile);
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const restored = await restoreMobileSession();
        if (!restored) {
          if (active) setStatus('unauthenticated');
          return;
        }
        const profile = await getMe();
        if (active) {
          setMe(profile);
          setStatus('authenticated');
        }
      } catch {
        await clearMobileSession();
        if (active) setStatus('unauthenticated');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string, twoFactorCode?: string) => {
    await loginRequest(email, password, twoFactorCode);
    const profile = await getMe();
    setMe(profile);
    setStatus('authenticated');
  }, []);

  const signOut = useCallback(async () => {
    await logoutRequest();
    expireSession();
  }, [expireSession]);

  const value = useMemo(
    () => ({ status, me, signIn, signOut, reloadProfile }),
    [status, me, signIn, signOut, reloadProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
