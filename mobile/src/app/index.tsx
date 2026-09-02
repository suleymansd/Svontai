import { Redirect } from 'expo-router';

import { LoadingState } from '@/components/ui/feedback';
import { Screen } from '@/components/ui/screen';
import { useAuth } from '@/lib/auth/auth-context';

export default function IndexScreen() {
  const { status } = useAuth();
  if (status === 'loading') {
    return (
      <Screen scroll={false}>
        <LoadingState label="Güvenli oturum açılıyor" />
      </Screen>
    );
  }
  return <Redirect href={status === 'authenticated' ? '/(tabs)' : '/(auth)/login'} />;
}
