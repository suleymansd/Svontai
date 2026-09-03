import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack, useRouter, useSegments } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useCallback, useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';

import { AnimatedLaunchScreen } from '@/components/launch/animated-launch-screen';
import { palette } from '@/constants/theme';
import { AuthProvider, useAuth } from '@/lib/auth/auth-context';
import { FirstRunProvider, useFirstRun } from '@/lib/onboarding/first-run-context';

void SplashScreen.preventAutoHideAsync();
SplashScreen.setOptions({ duration: 300, fade: true });

function Navigation() {
  const router = useRouter();
  const segments = useSegments();
  const { status: authStatus } = useAuth();
  const { status: firstRunStatus, hasCompletedOnboarding } = useFirstRun();
  const [launchVisible, setLaunchVisible] = useState(true);
  const appReady = authStatus !== 'loading' && firstRunStatus === 'ready';

  useEffect(() => {
    const frame = requestAnimationFrame(() => void SplashScreen.hideAsync());
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (launchVisible || !appReady) return;

    const isOnboarding = segments[0] === 'onboarding';
    if (!hasCompletedOnboarding && !isOnboarding) {
      router.replace('/onboarding');
      return;
    }
    if (hasCompletedOnboarding && isOnboarding) {
      if (authStatus === 'authenticated') router.replace('/(tabs)');
      else router.replace('/(auth)/login');
    }
  }, [appReady, authStatus, hasCompletedOnboarding, launchVisible, router, segments]);

  const finishLaunch = useCallback(() => setLaunchVisible(false), []);

  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: palette.canvas } }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="onboarding" />
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="conversation/[id]"
          options={{
            headerShown: true,
            title: 'Konuşma',
            headerBackTitle: 'Mesajlar',
            headerTintColor: palette.navy,
            headerTitleStyle: { color: palette.navy, fontSize: 16, fontWeight: '800' },
            headerStyle: { backgroundColor: palette.surface },
            headerShadowVisible: false,
          }}
        />
      </Stack>
      {launchVisible && <AnimatedLaunchScreen ready={appReady} onFinish={finishLaunch} />}
    </>
  );
}

export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 20_000, retry: 1, refetchOnReconnect: true },
          mutations: { retry: 0 },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <FirstRunProvider>
        <AuthProvider>
          <Navigation />
        </AuthProvider>
      </FirstRunProvider>
    </QueryClientProvider>
  );
}
