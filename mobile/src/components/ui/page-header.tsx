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
          <View style={styles.liveDot} />
          <ShieldCheck size={14} color={palette.success} />
          <Text style={styles.securityText}>Güvenli bağlantı</Text>
        </View>
      </View>
      <View style={styles.titleBlock}>
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { backgroundColor: palette.surface, borderBottomWidth: 1, borderBottomColor: palette.border, paddingHorizontal: spacing.lg, paddingTop: spacing.xs, paddingBottom: spacing.md },
  topRow: { minHeight: 42, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  securityBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, height: 28, borderRadius: 14, backgroundColor: palette.successSoft },
  liveDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: palette.success },
  securityText: { color: palette.success, fontSize: 10, fontWeight: '800' },
  titleBlock: { marginTop: spacing.sm, gap: 2 },
  title: { color: palette.ink, fontSize: 23, lineHeight: 29, fontWeight: '900' },
  subtitle: { color: palette.inkMuted, fontSize: 13, lineHeight: 19 },
});
