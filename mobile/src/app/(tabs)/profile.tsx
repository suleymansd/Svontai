import Constants from 'expo-constants';
import { Building2, LogOut, Mail, ShieldCheck, Smartphone } from 'lucide-react-native';
import { useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { Screen } from '@/components/ui/screen';
import { palette, radius, spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth/auth-context';
import { initials } from '@/lib/format';

export default function ProfileScreen() {
  const { me, signOut } = useAuth();
  const [loading, setLoading] = useState(false);
  const fullName = me?.user.full_name || 'SvontAI Kullanıcısı';

  const confirmLogout = () => {
    Alert.alert('Oturumu kapat', 'Bu cihazdaki güvenli oturum kapatılacak.', [
      { text: 'Vazgeç', style: 'cancel' },
      {
        text: 'Çıkış yap',
        style: 'destructive',
        onPress: () => {
          setLoading(true);
          void signOut().finally(() => setLoading(false));
        },
      },
    ]);
  };

  return (
    <Screen header={<PageHeader title="Hesap" subtitle="Güvenlik ve çalışma alanı" />}>
      <Card style={styles.identityCard}>
        <View style={styles.avatar}><Text style={styles.avatarText}>{initials(fullName)}</Text></View>
        <View style={styles.copy}>
          <Text style={styles.name}>{fullName}</Text>
          <Text style={styles.muted}>{me?.tenant?.name || 'İşletme kurulumu bekleniyor'}</Text>
        </View>
      </Card>

      <Text style={styles.sectionTitle}>Hesap bilgileri</Text>
      <Card style={styles.detailsCard}>
        <DetailRow icon={<Mail size={19} color={palette.primaryDark} />} label="E-posta" value={me?.user.email || '-'} />
        <View style={styles.divider} />
        <DetailRow icon={<Building2 size={19} color={palette.violet} />} label="Çalışma alanı" value={me?.tenant?.name || 'Tanımlanmadı'} />
        <View style={styles.divider} />
        <DetailRow icon={<ShieldCheck size={19} color={palette.success} />} label="Oturum" value="Cihaz kasasıyla korunuyor" />
      </Card>

      <Text style={styles.sectionTitle}>Uygulama</Text>
      <Card style={styles.detailsCard}>
        <DetailRow icon={<Smartphone size={19} color={palette.warning} />} label="SvontAI Mobil" value={`Sürüm ${Constants.expoConfig?.version || '1.0.0'}`} />
      </Card>

      <Button label="Çıkış yap" variant="secondary" loading={loading} icon={<LogOut size={19} color={palette.danger} />} onPress={confirmLogout} />
    </Screen>
  );
}

function DetailRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <View style={styles.detailIcon}>{icon}</View>
      <View style={styles.copy}>
        <Text style={styles.detailLabel}>{label}</Text>
        <Text style={styles.detailValue} numberOfLines={1}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  identityCard: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  avatar: { width: 58, height: 58, borderRadius: 29, backgroundColor: palette.violetSoft, alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: palette.violet, fontSize: 18, fontWeight: '800' },
  copy: { flex: 1, gap: spacing.xs },
  name: { color: palette.ink, fontSize: 18, fontWeight: '800' },
  muted: { color: palette.inkMuted, fontSize: 13 },
  sectionTitle: { color: palette.ink, fontSize: 16, fontWeight: '800' },
  detailsCard: { paddingVertical: spacing.sm },
  detailRow: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.sm },
  detailIcon: { width: 38, height: 38, borderRadius: radius.md, backgroundColor: palette.surfaceMuted, alignItems: 'center', justifyContent: 'center' },
  detailLabel: { color: palette.inkSubtle, fontSize: 11 },
  detailValue: { color: palette.ink, fontSize: 14, fontWeight: '600' },
  divider: { height: 1, backgroundColor: palette.border, marginLeft: 58 },
});
