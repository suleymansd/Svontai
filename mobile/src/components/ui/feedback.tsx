import { AlertCircle, Inbox } from 'lucide-react-native';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { palette, spacing } from '@/constants/theme';
import { Button } from './button';

export function LoadingState({ label = 'Veriler hazırlanıyor' }: { label?: string }) {
  return (
    <View style={styles.container}>
      <ActivityIndicator color={palette.primary} size="large" />
      <Text style={styles.description}>{label}</Text>
    </View>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <View style={styles.container}>
      <Inbox color={palette.inkSubtle} size={30} />
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.container}>
      <AlertCircle color={palette.danger} size={30} />
      <Text style={styles.title}>Veriler yüklenemedi</Text>
      <Text style={styles.description}>{message}</Text>
      <Button label="Tekrar dene" variant="secondary" onPress={onRetry} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', justifyContent: 'center', paddingVertical: 48, gap: spacing.md },
  title: { color: palette.ink, fontSize: 17, fontWeight: '700', textAlign: 'center' },
  description: { color: palette.inkMuted, fontSize: 14, lineHeight: 21, textAlign: 'center', maxWidth: 310 },
});
