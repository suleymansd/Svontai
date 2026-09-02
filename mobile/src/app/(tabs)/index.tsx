import { useQuery } from '@tanstack/react-query';
import { Bot, CalendarClock, CheckCircle2, ChevronRight, MessageCircle, UsersRound } from 'lucide-react-native';
import { StyleSheet, Text, View } from 'react-native';

import { Card } from '@/components/ui/card';
import { ErrorState, LoadingState } from '@/components/ui/feedback';
import { PageHeader } from '@/components/ui/page-header';
import { Screen } from '@/components/ui/screen';
import { palette, radius, spacing } from '@/constants/theme';
import { getActionCenter, getDashboardStats } from '@/lib/api/endpoints';
import { useAuth } from '@/lib/auth/auth-context';
import { formatAppointmentDate } from '@/lib/format';

export default function DashboardScreen() {
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
          <Bot size={30} color={palette.violet} />
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

  return (
    <Screen refreshing={refreshing} onRefresh={refresh} header={<PageHeader title={me.tenant.name} subtitle="Bugünün operasyon görünümü" />}>
      <View style={styles.healthStrip}>
        <View style={styles.liveDot} />
        <View style={styles.healthCopy}>
          <Text style={styles.healthTitle}>Panel bağlantısı aktif</Text>
          <Text style={styles.healthSubtitle}>Güncel operasyon verileri alındı</Text>
        </View>
        <CheckCircle2 size={22} color={palette.success} />
      </View>

      <View style={styles.statsGrid}>
        <StatCard icon={<MessageCircle size={20} color={palette.primaryDark} />} value={today?.messages_received || 0} label="Gelen mesaj" tone="cyan" />
        <StatCard icon={<Bot size={20} color={palette.violet} />} value={today?.ai_responses || 0} label="AI yanıtı" tone="violet" />
        <StatCard icon={<UsersRound size={20} color={palette.warning} />} value={today?.leads_captured || 0} label="Yeni müşteri" tone="orange" />
        <StatCard icon={<CalendarClock size={20} color={palette.success} />} value={appointments.length} label="Yaklaşan randevu" tone="green" />
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Müdahale gerekenler</Text>
        <Text style={styles.count}>{actions.length}</Text>
      </View>
      {actions.length ? actions.slice(0, 4).map((item) => (
        <Card key={item.id} style={styles.actionCard}>
          <View style={[styles.severity, item.severity === 'critical' ? styles.severityCritical : styles.severityWarning]} />
          <View style={styles.actionCopy}>
            <Text style={styles.actionTitle}>{item.title}</Text>
            <Text style={styles.muted} numberOfLines={2}>{item.description}</Text>
          </View>
          <ChevronRight size={20} color={palette.inkSubtle} />
        </Card>
      )) : (
        <Card style={styles.calmCard}>
          <CheckCircle2 size={24} color={palette.success} />
          <View style={styles.healthCopy}>
            <Text style={styles.actionTitle}>Bekleyen kritik işlem yok</Text>
            <Text style={styles.muted}>Sistem normal şekilde çalışıyor.</Text>
          </View>
        </Card>
      )}

      <Text style={styles.sectionTitle}>Yaklaşan randevular</Text>
      {appointments.length ? appointments.slice(0, 3).map((appointment) => (
        <Card key={appointment.id} style={styles.appointmentCard}>
          <View style={styles.dateBadge}><CalendarClock size={20} color={palette.primaryDark} /></View>
          <View style={styles.healthCopy}>
            <Text style={styles.actionTitle}>{appointment.customer_name}</Text>
            <Text style={styles.muted}>{appointment.subject}</Text>
            <Text style={styles.dateText}>{formatAppointmentDate(appointment.starts_at)}</Text>
          </View>
        </Card>
      )) : <Text style={styles.muted}>Yaklaşan randevu bulunmuyor.</Text>}
    </Screen>
  );
}

function StatCard({ icon, value, label, tone }: { icon: React.ReactNode; value: number; label: string; tone: 'cyan' | 'violet' | 'orange' | 'green' }) {
  return (
    <Card style={styles.statCard}>
      <View style={[styles.statIcon, styles[`${tone}Tone`]]}>{icon}</View>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  setupCard: { alignItems: 'center', gap: spacing.md, paddingVertical: spacing.xxl },
  healthStrip: { flexDirection: 'row', alignItems: 'center', backgroundColor: palette.successSoft, borderWidth: 1, borderColor: '#C6EADB', borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md },
  liveDot: { width: 9, height: 9, borderRadius: 5, backgroundColor: palette.success },
  healthCopy: { flex: 1, gap: 2 },
  healthTitle: { color: palette.success, fontSize: 15, fontWeight: '800' },
  healthSubtitle: { color: palette.inkMuted, fontSize: 12 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  statCard: { width: '47.8%', minHeight: 132, gap: spacing.sm, padding: spacing.md },
  statIcon: { width: 38, height: 38, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  cyanTone: { backgroundColor: palette.primarySoft },
  violetTone: { backgroundColor: palette.violetSoft },
  orangeTone: { backgroundColor: palette.warningSoft },
  greenTone: { backgroundColor: palette.successSoft },
  statValue: { color: palette.ink, fontSize: 27, fontWeight: '800' },
  statLabel: { color: palette.inkMuted, fontSize: 12 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  sectionTitle: { color: palette.ink, fontSize: 17, fontWeight: '800' },
  count: { minWidth: 28, height: 28, textAlign: 'center', textAlignVertical: 'center', borderRadius: 14, overflow: 'hidden', backgroundColor: palette.surfaceMuted, color: palette.inkMuted, fontWeight: '700' },
  actionCard: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, padding: spacing.md },
  actionCopy: { flex: 1, gap: spacing.xs },
  actionTitle: { color: palette.ink, fontSize: 14, fontWeight: '700' },
  muted: { color: palette.inkMuted, fontSize: 13, lineHeight: 19 },
  severity: { width: 4, alignSelf: 'stretch', borderRadius: 2 },
  severityWarning: { backgroundColor: palette.warning },
  severityCritical: { backgroundColor: palette.danger },
  calmCard: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, backgroundColor: palette.successSoft },
  appointmentCard: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  dateBadge: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: palette.primarySoft, alignItems: 'center', justifyContent: 'center' },
  dateText: { color: palette.primaryDark, fontSize: 12, fontWeight: '700', marginTop: spacing.xs },
});
