import { useQuery } from '@tanstack/react-query';
import { CalendarCheck, Clock3, MapPin } from 'lucide-react-native';
import { StyleSheet, Text, View } from 'react-native';

import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/feedback';
import { PageHeader } from '@/components/ui/page-header';
import { Screen } from '@/components/ui/screen';
import { palette, radius, spacing } from '@/constants/theme';
import { getAppointments } from '@/lib/api/endpoints';
import { formatAppointmentDate } from '@/lib/format';

const statusLabels: Record<string, string> = {
  scheduled: 'Planlandı',
  completed: 'Tamamlandı',
  cancelled: 'İptal edildi',
};

export default function AppointmentsScreen() {
  const appointments = useQuery({ queryKey: ['appointments'], queryFn: getAppointments });
  const upcoming = (appointments.data || []).filter((item) => item.status !== 'cancelled');

  return (
    <Screen
      refreshing={appointments.isRefetching}
      onRefresh={() => void appointments.refetch()}
      header={<PageHeader title="Randevular" subtitle="Takvim ve müşteri planlaması" />}
    >
      {appointments.isLoading ? <LoadingState label="Randevular yükleniyor" /> : null}
      {appointments.error ? <ErrorState message="Randevular alınamadı." onRetry={() => void appointments.refetch()} /> : null}
      {!appointments.isLoading && !appointments.error && !upcoming.length ? (
        <EmptyState title="Randevu bulunmuyor" description="AI tarafından oluşturulan ve manuel eklenen randevular burada görünür." />
      ) : null}

      {upcoming.map((appointment) => (
        <Card key={appointment.id} style={styles.card}>
          <View style={styles.icon}><CalendarCheck size={23} color={palette.primaryDark} /></View>
          <View style={styles.copy}>
            <View style={styles.titleRow}>
              <Text style={styles.customer} numberOfLines={1}>{appointment.customer_name}</Text>
              <Text style={[styles.status, appointment.status === 'completed' && styles.completed]}>{statusLabels[appointment.status] || appointment.status}</Text>
            </View>
            <Text style={styles.subject}>{appointment.subject}</Text>
            <View style={styles.metaRow}><Clock3 size={14} color={palette.inkSubtle} /><Text style={styles.meta}>{formatAppointmentDate(appointment.starts_at)} · {appointment.duration_minutes} dk</Text></View>
            {appointment.calendar_sync_status === 'synced' ? (
              <View style={styles.metaRow}><MapPin size={14} color={palette.success} /><Text style={styles.synced}>Takvimle senkronize</Text></View>
            ) : null}
          </View>
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: 'row', gap: spacing.md },
  icon: { width: 46, height: 46, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: palette.primarySoft },
  copy: { flex: 1, gap: spacing.sm },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  customer: { flex: 1, color: palette.ink, fontSize: 15, fontWeight: '800' },
  subject: { color: palette.inkMuted, fontSize: 13 },
  status: { color: palette.primaryDark, backgroundColor: palette.primarySoft, borderRadius: radius.pill, overflow: 'hidden', paddingHorizontal: spacing.sm, paddingVertical: spacing.xs, fontSize: 10, fontWeight: '800' },
  completed: { color: palette.success, backgroundColor: palette.successSoft },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  meta: { color: palette.inkSubtle, fontSize: 12 },
  synced: { color: palette.success, fontSize: 11, fontWeight: '700' },
});
