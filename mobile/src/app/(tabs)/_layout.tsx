import { CalendarDays, House, MessageCircle, UserRound } from 'lucide-react-native';
import { Redirect, Tabs } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { palette } from '@/constants/theme';
import { useAuth } from '@/lib/auth/auth-context';

export default function TabsLayout() {
  const { status } = useAuth();
  if (status === 'unauthenticated') return <Redirect href="/(auth)/login" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: palette.navy,
        tabBarInactiveTintColor: palette.inkSubtle,
        tabBarStyle: styles.tabBar,
        tabBarItemStyle: styles.tabItem,
        tabBarLabelStyle: styles.tabLabel,
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Ana Sayfa', tabBarIcon: ({ color, focused }) => <TabIcon focused={focused}><House size={20} color={color} strokeWidth={focused ? 2.6 : 2} /></TabIcon> }} />
      <Tabs.Screen
        name="conversations"
        options={{ title: 'Mesajlar', tabBarIcon: ({ color, focused }) => <TabIcon focused={focused}><MessageCircle size={20} color={color} strokeWidth={focused ? 2.6 : 2} /></TabIcon> }}
      />
      <Tabs.Screen
        name="appointments"
        options={{ title: 'Randevular', tabBarIcon: ({ color, focused }) => <TabIcon focused={focused}><CalendarDays size={20} color={color} strokeWidth={focused ? 2.6 : 2} /></TabIcon> }}
      />
      <Tabs.Screen name="profile" options={{ title: 'Hesap', tabBarIcon: ({ color, focused }) => <TabIcon focused={focused}><UserRound size={20} color={color} strokeWidth={focused ? 2.6 : 2} /></TabIcon> }} />
    </Tabs>
  );
}

function TabIcon({ focused, children }: { focused: boolean; children: React.ReactNode }) {
  return <View style={[styles.iconWrap, focused && styles.iconWrapActive]}>{children}</View>;
}

const styles = StyleSheet.create({
  tabBar: {
    height: 82,
    paddingTop: 7,
    paddingBottom: 10,
    borderTopWidth: 1,
    borderTopColor: palette.border,
    backgroundColor: palette.surface,
  },
  tabItem: { paddingVertical: 2 },
  tabLabel: { fontSize: 10, lineHeight: 14, fontWeight: '700' },
  iconWrap: { width: 42, height: 30, alignItems: 'center', justifyContent: 'center', borderRadius: 8 },
  iconWrapActive: { backgroundColor: palette.primarySoft },
});
