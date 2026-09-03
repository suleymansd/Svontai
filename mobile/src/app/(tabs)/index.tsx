import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import {
  Activity,
  ArrowRight,
  Bot,
  CalendarClock,
  Check,
  CheckCircle2,
  MessageCircle,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Card } from '@/components/ui/card';
import { ErrorState, LoadingState } from '@/components/ui/feedback';
import { PageHeader } from '@/components/ui/page-header';
import { Screen } from '@/components/ui/screen';
import { palette, radius, spacing } from '@/constants/theme';
import { getActionCenter, getDashboardStats } from '@/lib/api/endpoints';
import { useAuth } from '@/lib/auth/auth-context';
import { formatAppointmentDate } from '@/lib/format';

export default function DashboardScreen() {
  const router = useRouter();
  const { me } = useAuth();
  const enabled = Boolean(me?.tenant);
  const stats = useQuery({ queryKey: ['dashboard-stats'], queryFn: getDashboardStats, enabled });
  const actionCenter = useQuery({ queryKey: ['action-center'], queryFn: getActionCenter, enabled });
  const refreshing = stats.isRefetching || actionCenter.isRefetching;
  const refresh = () => void Promise.all([stats.refetch(), actionCenter.refetch()]);

  if (!me?.tenant) {
    return (
      <Screen header={<PageHeader title="Kurulumu tamamlayın" subtitle={me?.user.email} />}>
        <Card style={styles.setupCard}>
          <View style={styles.setupIcon}><Bot size={25} color={palette.violet} /></View>
          <Text style={styles.sectionTitle}>İşletme çalışma alanınız hazır değil</Text>
          <Text style={styles.muted}>İlk işletmenizi web panelinden oluşturduktan sonra mobil operasyon ekranı otomatik açılır.</Text>
        </Card>
      </Screen>
    );
  }

  if (stats.isLoading || actionCenter.isLoading) {
    return <Screen header={<PageHeader title={me.tenant.name} subtitle="Operasyon özeti" />}><LoadingState /></Screen>;
  }
  if (stats.error || actionCenter.error) {
    return <Screen header={<PageHeader title={me.tenant.name} subtitle="Operasyon özeti" />}><ErrorState message="Operasyon verileri alınamadı." onRetry={refresh} /></Screen>;
  }

  const today = stats.data?.today;
  const actions = actionCenter.data?.items || [];
  const appointments = actionCenter.data?.upcoming_appointments || [];
  const received = today?.messages_received || 0;
  const answered = today?.ai_responses || 0;
  const responseRate = received ? Math.min(100, Math.round((answered / received) * 100)) : 100;

  return (
    <Screen refreshing={refreshing} onRefresh={refresh} header={<PageHeader title={me.tenant.name} subtitle="Bugünün operasyon görünümü" />}>
      <View style={styles.commandPanel}>
        <View style={styles.commandTop}>
          <View style={styles.liveBadge}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>OTONOM SİSTEM AKTİF</Text>
          </View>
          <ShieldCheck size={19} color="#71E1C0" />
        </View>
        <Text style={styles.commandTitle}>Müşteri iletişiminiz kontrol altında</Text>
        <Text style={styles.commandDescription}>SvontAI mesajları takip ediyor ve yalnızca gerektiğinde sizi devreye alıyor.</Text>
        <View style={styles.commandMetrics}>
          <View style={styles.commandMetric}>
            <Text style={styles.commandValue}>%{responseRate}</Text>
            <Text style={styles.commandLabel}>Yanıt oranı</Text>
          </View>
          <View style={styles.commandDivider} />
          <View style={styles.commandMetric}>
            <Text style={styles.commandValue}>{actions.length}</Text>
            <Text style={styles.commandLabel}>Bekleyen işlem</Text>
          </View>
          <View style={styles.commandDivider} />
          <View style={styles.commandMetric}>
            <Text style={styles.commandValue}>{appointments.length}</Text>
            <Text style={styles.commandLabel}>Yaklaşan</Text>
          </View>
        </View>
      </View>

      <SectionHeading title="Bugün" caption="Canlı veriler" />
      <View style={styles.statsGrid}>
        <StatCard icon={<MessageCircle size={19} color={palette.primaryDark} />} value={received} label="Gelen mesaj" tone="cyan" />
        <StatCard icon={<Sparkles size={19} color={palette.violet} />} value={answered} label="AI yanıtı" tone="violet" />
        <StatCard icon={<UsersRound size={19} color={palette.warning} />} value={today?.leads_captured || 0} label="Yeni müşteri" tone="orange" />
        <StatCard icon={<CalendarClock size={19} color={palette.success} />} value={appointments.length} label="Randevu" tone="green" />
      </View>

      <SectionHeading title="Müdahale gerekenler" caption={actions.length ? `${actions.length} işlem` : 'Temiz'} />
      {actions.length ? (
        <Card style={styles.listCard}>
          {actions.slice(0, 4).map((item, index) => (
            <View key={item.id} style={[styles.actionRow, index > 0 && styles.rowBorder]}>
              <View style={[styles.actionIcon, item.severity === 'critical' ? styles.criticalIcon : styles.warningIcon]}>
                <Activity size={17} color={item.severity === 'critical' ? palette.danger : palette.warning} />
              </View>
              <View style={styles.actionCopy}>
                <Text style={styles.actionTitle}>{item.title}</Text>
                <Text style={styles.muted} numberOfLines={2}>{item.description}</Text>
              </View>
            </View>
          ))}
        </Card>
      ) : (
        <View style={styles.calmBand}>
          <View style={styles.calmIcon}><CheckCircle2 size={20} color={palette.success} /></View>
          <View style={styles.flex}>
            <Text style={styles.actionTitle}>Bekleyen kritik işlem yok</Text>
            <Text style={styles.muted}>Tüm operasyon akışları normal çalışıyor.</Text>
          </View>
          <Check size={18} color={palette.success} strokeWidth={3} />
        </View>
      )}

      <SectionHeading
        title="Yaklaşan randevular"
        caption={appointments.length ? `${appointments.length} kayıt` : 'Kayıt yok'}
        action={() => router.push('/(tabs)/appointments')}
      />
      {appointments.length ? (
        <Card style={styles.listCard}>
          {appointments.slice(0, 3).map((appointment, index) => (
            <View key={appointment.id} style={[styles.appointmentRow, index > 0 && styles.rowBorder]}>
              <View style={styles.dateBadge}><CalendarClock size={19} color={palette.primaryDark} /></View>
              <View style={styles.flex}>
                <Text style={styles.actionTitle}>{appointment.customer_name}</Text>
                <Text style={styles.muted} numberOfLines={1}>{appointment.subject}</Text>
                <Text style={styles.dateText}>{formatAppointmentDate(appointment.starts_at)}</Text>
              </View>
            </View>
          ))}
        </Card>
      ) : (
        <View style={styles.emptyLine}>
          <CalendarClock size={19} color={palette.inkSubtle} />
          <Text style={styles.muted}>Yaklaşan randevu bulunmuyor.</Text>
        </View>
      )}
    </Screen>
  );
}

function SectionHeading({ title, caption, action }: { title: string; caption: string; action?: () => void }) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {action ? (
        <Pressable onPress={action} hitSlop={10} style={styles.sectionAction}>
          <Text style={styles.sectionActionText}>{caption}</Text>
          <ArrowRight size={15} color={palette.primaryDark} />
        </Pressable>
      ) : <Text style={styles.sectionCaption}>{caption}</Text>}
    </View>
  );
}

function StatCard({ icon, value, label, tone }: { icon: React.ReactNode; value: number; label: string; tone: 'cyan' | 'violet' | 'orange' | 'green' }) {
  return (
    <View style={styles.statCard}>
      <View style={[styles.statIcon, styles[`${tone}Tone`]]}>{icon}</View>
      <View style={styles.statCopy}>
        <Text style={styles.statValue}>{value}</Text>
        <Text style={styles.statLabel}>{label}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  setupCard: { alignItems: 'center', gap: spacing.md, paddingVertical: spacing.xxl },
  setupIcon: { width: 52, height: 52, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: palette.violetSoft },
  commandPanel: { padding: 18, borderRadius: radius.lg, backgroundColor: palette.navy, overflow: 'hidden' },
  commandTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  liveBadge: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  liveDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#43D6AA' },
  liveText: { color: '#8FE5CC', fontSize: 9, lineHeight: 13, fontWeight: '900' },
  commandTitle: { marginTop: spacing.lg, color: palette.surface, fontSize: 19, lineHeight: 25, fontWeight: '900' },
  commandDescription: { marginTop: 6, color: '#AEB8C9', fontSize: 12, lineHeight: 18 },
  commandMetrics: { marginTop: 20, paddingTop: spacing.lg, flexDirection: 'row', borderTopWidth: 1, borderTopColor: '#2A3447' },
  commandMetric: { flex: 1, gap: 2 },
  commandValue: { color: palette.surface, fontSize: 18, lineHeight: 22, fontWeight: '900', fontVariant: ['tabular-nums'] },
  commandLabel: { color: '#8995A8', fontSize: 9, lineHeight: 13, fontWeight: '700' },
  commandDivider: { width: 1, marginHorizontal: spacing.md, backgroundColor: '#2A3447' },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  statCard: { minWidth: 136, flexBasis: '47%', flexGrow: 1, minHeight: 82, padding: spacing.md, flexDirection: 'row', alignItems: 'center', gap: spacing.md, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface },
  statIcon: { width: 36, height: 36, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  statCopy: { flex: 1, gap: 1 },
  cyanTone: { backgroundColor: palette.primarySoft },
  violetTone: { backgroundColor: palette.violetSoft },
  orangeTone: { backgroundColor: palette.warningSoft },
  greenTone: { backgroundColor: palette.successSoft },
  statValue: { color: palette.ink, fontSize: 21, lineHeight: 25, fontWeight: '900', fontVariant: ['tabular-nums'] },
  statLabel: { color: palette.inkMuted, fontSize: 10, lineHeight: 14, fontWeight: '600' },
  sectionHeader: { minHeight: 28, marginTop: spacing.sm, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  sectionTitle: { color: palette.ink, fontSize: 16, lineHeight: 22, fontWeight: '900' },
  sectionCaption: { color: palette.inkSubtle, fontSize: 11, fontWeight: '700' },
  sectionAction: { minHeight: 28, flexDirection: 'row', alignItems: 'center', gap: 4 },
  sectionActionText: { color: palette.primaryDark, fontSize: 11, fontWeight: '800' },
  listCard: { paddingVertical: 2, paddingHorizontal: spacing.md },
  actionRow: { minHeight: 74, flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.md },
  actionIcon: { width: 36, height: 36, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  warningIcon: { backgroundColor: palette.warningSoft },
  criticalIcon: { backgroundColor: palette.dangerSoft },
  actionCopy: { flex: 1, gap: 3 },
  actionTitle: { color: palette.ink, fontSize: 13, lineHeight: 18, fontWeight: '800' },
  muted: { color: palette.inkMuted, fontSize: 11, lineHeight: 16 },
  rowBorder: { borderTopWidth: 1, borderTopColor: palette.border },
  calmBand: { minHeight: 68, paddingHorizontal: spacing.md, flexDirection: 'row', alignItems: 'center', gap: spacing.md, borderRadius: radius.lg, borderWidth: 1, borderColor: '#CBEBDD', backgroundColor: palette.successSoft },
  calmIcon: { width: 36, height: 36, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: palette.surface },
  appointmentRow: { minHeight: 82, flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.md },
  dateBadge: { width: 40, height: 46, borderRadius: radius.md, backgroundColor: palette.primarySoft, alignItems: 'center', justifyContent: 'center' },
  dateText: { color: palette.primaryDark, fontSize: 10, lineHeight: 14, fontWeight: '800', marginTop: 3 },
  emptyLine: { minHeight: 64, paddingHorizontal: spacing.lg, flexDirection: 'row', alignItems: 'center', gap: spacing.md, borderWidth: 1, borderColor: palette.border, borderRadius: radius.lg, backgroundColor: palette.surfaceRaised },
});
