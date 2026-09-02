import { Redirect, Stack } from 'expo-router';

import { useAuth } from '@/lib/auth/auth-context';

export default function AuthLayout() {
  const { status } = useAuth();
  if (status === 'authenticated') return <Redirect href="/(tabs)" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
