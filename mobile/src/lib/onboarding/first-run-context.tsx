import * as SecureStore from 'expo-secure-store';
import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Platform } from 'react-native';

const ONBOARDING_KEY = 'svontai.mobile.onboarding.v1';

type FirstRunStatus = 'loading' | 'ready';

type FirstRunContextValue = {
  status: FirstRunStatus;
  hasCompletedOnboarding: boolean;
  completeOnboarding: () => Promise<void>;
};

const FirstRunContext = createContext<FirstRunContextValue | null>(null);

async function readCompletion(): Promise<boolean> {
  if (Platform.OS === 'web') {
    try {
      return globalThis.localStorage?.getItem(ONBOARDING_KEY) === 'completed';
    } catch {
      return false;
    }
  }

  return (await SecureStore.getItemAsync(ONBOARDING_KEY)) === 'completed';
}

async function persistCompletion(): Promise<void> {
  if (Platform.OS === 'web') {
    try {
      globalThis.localStorage?.setItem(ONBOARDING_KEY, 'completed');
    } catch {
      // Keep the current session usable when browser storage is unavailable.
    }
    return;
  }

  await SecureStore.setItemAsync(ONBOARDING_KEY, 'completed', {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

export function FirstRunProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<FirstRunStatus>('loading');
  const [hasCompletedOnboarding, setHasCompletedOnboarding] = useState(false);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const completed = await readCompletion();
        if (active) setHasCompletedOnboarding(completed);
      } catch {
        if (active) setHasCompletedOnboarding(false);
      } finally {
        if (active) setStatus('ready');
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const completeOnboarding = useCallback(async () => {
    await persistCompletion();
    setHasCompletedOnboarding(true);
  }, []);

  const value = useMemo(
    () => ({ status, hasCompletedOnboarding, completeOnboarding }),
    [status, hasCompletedOnboarding, completeOnboarding],
  );

  return <FirstRunContext.Provider value={value}>{children}</FirstRunContext.Provider>;
}

export function useFirstRun(): FirstRunContextValue {
  const context = useContext(FirstRunContext);
  if (!context) throw new Error('useFirstRun must be used inside FirstRunProvider');
  return context;
}
