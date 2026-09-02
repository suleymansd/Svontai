import { ShieldCheck } from 'lucide-react-native';
import { StyleSheet, Text, View } from 'react-native';

import { palette, spacing } from '@/constants/theme';
import { Brand } from './brand';

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.header}>
      <View style={styles.topRow}>
        <Brand compact />
        <View style={styles.securityBadge}>
          <ShieldCheck size={14} color={palette.success} />
          <Text style={styles.securityText}>Güvenli</Text>
        </View>
      </View>
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: { backgroundColor: palette.surface, borderBottomWidth: 1, borderBottomColor: palette.border, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.lg, gap: spacing.xs },
  topRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.md },
  securityBadge: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, paddingHorizontal: spacing.sm, height: 30, borderRadius: 15, backgroundColor: palette.successSoft },
  securityText: { color: palette.success, fontSize: 11, fontWeight: '800' },
  title: { color: palette.ink, fontSize: 24, lineHeight: 30, fontWeight: '800' },
  subtitle: { color: palette.inkMuted, fontSize: 13, lineHeight: 19 },
});
