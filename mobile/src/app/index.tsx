import { Redirect } from 'expo-router';

import { LoadingState } from '@/components/ui/feedback';
import { Screen } from '@/components/ui/screen';
import { useAuth } from '@/lib/auth/auth-context';
import { useFirstRun } from '@/lib/onboarding/first-run-context';

export default function IndexScreen() {
  const { status: authStatus } = useAuth();
  const { status: firstRunStatus, hasCompletedOnboarding } = useFirstRun();
  if (authStatus === 'loading' || firstRunStatus === 'loading') {
    return (
      <Screen scroll={false}>
        <LoadingState label="Güvenli oturum açılıyor" />
      </Screen>
    );
  }
  if (!hasCompletedOnboarding) return <Redirect href="/onboarding" />;
  return <Redirect href={authStatus === 'authenticated' ? '/(tabs)' : '/(auth)/login'} />;
}
