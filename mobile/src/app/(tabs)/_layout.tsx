import { CalendarDays, House, MessageCircle, UserRound } from 'lucide-react-native';
import { Redirect, Tabs } from 'expo-router';

import { palette } from '@/constants/theme';
import { useAuth } from '@/lib/auth/auth-context';

export default function TabsLayout() {
  const { status } = useAuth();
  if (status === 'unauthenticated') return <Redirect href="/(auth)/login" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: palette.primaryDark,
        tabBarInactiveTintColor: palette.inkSubtle,
        tabBarStyle: { height: 78, paddingTop: 8, paddingBottom: 10, borderTopColor: palette.border },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Ana Sayfa', tabBarIcon: ({ color }) => <House size={22} color={color} /> }} />
      <Tabs.Screen
        name="conversations"
        options={{ title: 'Mesajlar', tabBarIcon: ({ color }) => <MessageCircle size={22} color={color} /> }}
      />
      <Tabs.Screen
        name="appointments"
        options={{ title: 'Randevular', tabBarIcon: ({ color }) => <CalendarDays size={22} color={color} /> }}
      />
      <Tabs.Screen name="profile" options={{ title: 'Hesap', tabBarIcon: ({ color }) => <UserRound size={22} color={color} /> }} />
    </Tabs>
  );
}
