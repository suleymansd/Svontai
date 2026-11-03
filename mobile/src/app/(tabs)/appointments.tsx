import { useQuery } from '@tanstack/react-query';
import { CalendarCheck, CalendarDays, Check, Clock3, Link2, MapPin, X } from 'lucide-react-native';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/feedback';
import { PageHeader } from '@/components/ui/page-header';
import { Screen } from '@/components/ui/screen';
import { palette, radius, spacing } from '@/constants/theme';
import { getAppointments } from '@/lib/api/endpoints';
import type { Appointment } from '@/lib/api/types';

type AppointmentFilter = 'upcoming' | 'completed' | 'cancelled';

const statusLabels: Record<string, string> = {
  scheduled: 'Planlandı',
  completed: 'Tamamlandı',
  cancelled: 'İptal edildi',
};

export default function AppointmentsScreen() {
  const [filter, setFilter] = useState<AppointmentFilter>('upcoming');
  const appointments = useQuery({ queryKey: ['appointments'], queryFn: getAppointments });
  const items = useMemo(() => (appointments.data || []).filter((item) => {
    if (filter === 'completed') return item.status === 'completed';
    if (filter === 'cancelled') return item.status === 'cancelled';
    return item.status !== 'completed' && item.status !== 'cancelled';
  }), [appointments.data, filter]);
  const syncedCount = (appointments.data || []).filter((item) => item.calendar_sync_status === 'synced').length;

  return (
    <Screen
      refreshing={appointments.isRefetching}
      onRefresh={() => void appointments.refetch()}
      header={<PageHeader title="Randevular" subtitle="Takvim ve müşteri planlaması" />}
    >
      <View style={styles.summaryBand}>
        <View style={styles.summaryIcon}><CalendarDays size={21} color={palette.surface} /></View>
        <View style={styles.summaryCopy}>
          <Text style={styles.summaryValue}>{appointments.data?.length || 0} toplam randevu</Text>
          <Text style={styles.summaryLabel}>{syncedCount} kayıt işletme takvimiyle senkronize</Text>
        </View>
        <Link2 size={19} color="#7FE2CE" />
      </View>

      <View style={styles.filters}>
        <FilterButton label="Yaklaşan" active={filter === 'upcoming'} onPress={() => setFilter('upcoming')} />
        <FilterButton label="Tamamlanan" active={filter === 'completed'} onPress={() => setFilter('completed')} />
        <FilterButton label="İptal" active={filter === 'cancelled'} onPress={() => setFilter('cancelled')} />
      </View>

      {appointments.isLoading ? <LoadingState label="Randevular yükleniyor" /> : null}
      {appointments.error ? <ErrorState message="Randevular alınamadı." onRetry={() => void appointments.refetch()} /> : null}
      {!appointments.isLoading && !appointments.error && !items.length ? (
        <EmptyState title="Bu görünümde randevu yok" description="SvontAI tarafından oluşturulan ve panelden eklenen randevular burada görünür." />
      ) : null}

      {items.map((appointment) => <AppointmentRow key={appointment.id} appointment={appointment} />)}
    </Screen>
  );
}

function FilterButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.filterButton, active && styles.filterButtonActive, pressed && styles.pressed]}>
      <Text style={[styles.filterText, active && styles.filterTextActive]}>{label}</Text>
    </Pressable>
  );
}

function AppointmentRow({ appointment }: { appointment: Appointment }) {
  const startsAt = new Date(appointment.starts_at);
  const day = startsAt.toLocaleDateString('tr-TR', { day: '2-digit' });
  const month = startsAt.toLocaleDateString('tr-TR', { month: 'short' }).replace('.', '').toLocaleUpperCase('tr-TR');
  const dateLine = startsAt.toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long' });
  const time = startsAt.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  const cancelled = appointment.status === 'cancelled';
  const completed = appointment.status === 'completed';

  return (
    <Card style={styles.card}>
      <View style={[styles.dateTile, completed && styles.dateTileCompleted, cancelled && styles.dateTileCancelled]}>
        <Text style={[styles.day, cancelled && styles.cancelledText]}>{day}</Text>
        <Text style={[styles.month, cancelled && styles.cancelledText]}>{month}</Text>
      </View>
      <View style={styles.copy}>
        <View style={styles.titleRow}>
          <Text style={styles.customer} numberOfLines={1}>{appointment.customer_name}</Text>
          <View style={[styles.status, completed && styles.statusCompleted, cancelled && styles.statusCancelled]}>
            {completed ? <Check size={10} color={palette.success} strokeWidth={3} /> : cancelled ? <X size={10} color={palette.danger} strokeWidth={3} /> : <CalendarCheck size={10} color={palette.primaryDark} />}
            <Text style={[styles.statusText, completed && styles.completedText, cancelled && styles.cancelledStatusText]}>{statusLabels[appointment.status] || appointment.status}</Text>
          </View>
        </View>
        <Text style={styles.subject} numberOfLines={1}>{appointment.subject}</Text>
        <View style={styles.metaRow}>
          <Clock3 size={14} color={palette.inkSubtle} />
          <Text style={styles.meta}>{dateLine} · {time} · {appointment.duration_minutes} dk</Text>
        </View>
        {appointment.calendar_sync_status === 'synced' ? (
          <View style={styles.metaRow}><MapPin size={13} color={palette.success} /><Text style={styles.synced}>Takvimle senkronize</Text></View>
        ) : null}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  summaryBand: { minHeight: 78, paddingHorizontal: spacing.lg, flexDirection: 'row', alignItems: 'center', gap: spacing.md, borderRadius: radius.lg, backgroundColor: palette.navy },
  summaryIcon: { width: 40, height: 40, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: palette.navySoft },
  summaryCopy: { flex: 1, gap: 3 },
  summaryValue: { color: palette.surface, fontSize: 14, lineHeight: 19, fontWeight: '900' },
  summaryLabel: { color: '#9DA9BA', fontSize: 10, lineHeight: 14 },
  filters: { minHeight: 38, flexDirection: 'row', padding: 3, borderRadius: radius.md, backgroundColor: palette.surfaceMuted },
  filterButton: { flex: 1, minHeight: 32, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm },
  filterButtonActive: { backgroundColor: palette.surface },
  pressed: { opacity: 0.78 },
  filterText: { color: palette.inkMuted, fontSize: 10, fontWeight: '800' },
  filterTextActive: { color: palette.ink },
  card: { flexDirection: 'row', gap: spacing.md, padding: spacing.md },
  dateTile: { width: 48, height: 58, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: palette.primarySoft },
  dateTileCompleted: { backgroundColor: palette.successSoft },
  dateTileCancelled: { backgroundColor: palette.dangerSoft },
  day: { color: palette.primaryDark, fontSize: 19, lineHeight: 22, fontWeight: '900', fontVariant: ['tabular-nums'] },
  month: { color: palette.primaryDark, fontSize: 8, lineHeight: 12, fontWeight: '900' },
  cancelledText: { color: palette.danger },
  copy: { flex: 1, gap: 5 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  customer: { flex: 1, color: palette.ink, fontSize: 14, lineHeight: 19, fontWeight: '900' },
  subject: { color: palette.inkMuted, fontSize: 12, lineHeight: 17 },
  status: { minHeight: 23, flexDirection: 'row', alignItems: 'center', gap: 3, borderRadius: radius.pill, paddingHorizontal: 7, backgroundColor: palette.primarySoft },
  statusCompleted: { backgroundColor: palette.successSoft },
  statusCancelled: { backgroundColor: palette.dangerSoft },
  statusText: { color: palette.primaryDark, fontSize: 8, lineHeight: 11, fontWeight: '900' },
  completedText: { color: palette.success },
  cancelledStatusText: { color: palette.danger },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  meta: { flex: 1, color: palette.inkSubtle, fontSize: 10, lineHeight: 14 },
  synced: { color: palette.success, fontSize: 10, lineHeight: 14, fontWeight: '700' },
});
