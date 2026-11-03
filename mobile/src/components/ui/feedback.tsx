import { AlertCircle, Inbox } from 'lucide-react-native';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { palette, spacing } from '@/constants/theme';
import { Button } from './button';

export function LoadingState({ label = 'Veriler hazırlanıyor' }: { label?: string }) {
  return (
    <View style={styles.container}>
      <View style={styles.iconSurface}><ActivityIndicator color={palette.primary} size="small" /></View>
      <Text style={styles.description}>{label}</Text>
    </View>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <View style={styles.container}>
      <View style={styles.iconSurface}><Inbox color={palette.inkSubtle} size={24} /></View>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.container}>
      <View style={[styles.iconSurface, styles.errorSurface]}><AlertCircle color={palette.danger} size={24} /></View>
      <Text style={styles.title}>Veriler yüklenemedi</Text>
      <Text style={styles.description}>{message}</Text>
      <Button label="Tekrar dene" variant="secondary" onPress={onRetry} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', justifyContent: 'center', paddingVertical: 48, gap: spacing.md },
  iconSurface: { width: 52, height: 52, borderRadius: 8, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface },
  errorSurface: { borderColor: '#F3CDD2', backgroundColor: palette.dangerSoft },
  title: { color: palette.ink, fontSize: 16, lineHeight: 22, fontWeight: '900', textAlign: 'center' },
  description: { color: palette.inkMuted, fontSize: 13, lineHeight: 20, textAlign: 'center', maxWidth: 310 },
});
