import Constants from 'expo-constants';
import { Building2, Check, Fingerprint, LogOut, Mail, ShieldCheck, Smartphone } from 'lucide-react-native';
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
      <View style={styles.identityCard}>
        <View style={styles.identityTop}>
          <View style={styles.avatar}><Text style={styles.avatarText}>{initials(fullName)}</Text></View>
          <View style={styles.copy}>
            <Text style={styles.name}>{fullName}</Text>
            <Text style={styles.identityMuted}>{me?.tenant?.name || 'İşletme kurulumu bekleniyor'}</Text>
          </View>
          <View style={styles.verified}><Check size={13} color={palette.navy} strokeWidth={3} /></View>
        </View>
        <View style={styles.securityLine}>
          <Fingerprint size={16} color="#74DCC5" />
          <Text style={styles.securityLineText}>Bu cihazda güvenli oturum açık</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Hesap bilgileri</Text>
      <Card style={styles.detailsCard}>
        <DetailRow icon={<Mail size={19} color={palette.primaryDark} />} label="E-posta" value={me?.user.email || '-'} />
        <View style={styles.divider} />
        <DetailRow icon={<Building2 size={19} color={palette.violet} />} label="Çalışma alanı" value={me?.tenant?.name || 'Tanımlanmadı'} />
        <View style={styles.divider} />
        <DetailRow icon={<ShieldCheck size={19} color={palette.success} />} label="Oturum güvenliği" value="Cihaz kasasıyla korunuyor" />
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
  identityCard: { padding: spacing.lg, borderRadius: radius.lg, backgroundColor: palette.navy },
  identityTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  avatar: { width: 54, height: 54, borderRadius: 27, backgroundColor: palette.primary, alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: palette.surface, fontSize: 17, fontWeight: '900' },
  copy: { flex: 1, gap: spacing.xs },
  name: { color: palette.surface, fontSize: 17, fontWeight: '900' },
  identityMuted: { color: '#9EA9BA', fontSize: 12 },
  verified: { width: 25, height: 25, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: '#74DCC5' },
  securityLine: { marginTop: spacing.lg, paddingTop: spacing.md, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, borderTopWidth: 1, borderTopColor: '#293448' },
  securityLineText: { color: '#B2BECE', fontSize: 10, lineHeight: 14, fontWeight: '700' },
  muted: { color: palette.inkMuted, fontSize: 13 },
  sectionTitle: { marginTop: spacing.sm, color: palette.ink, fontSize: 15, lineHeight: 21, fontWeight: '900' },
  detailsCard: { paddingVertical: 2, paddingHorizontal: spacing.md },
  detailRow: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.sm },
  detailIcon: { width: 38, height: 38, borderRadius: radius.md, backgroundColor: palette.surfaceRaised, borderWidth: 1, borderColor: palette.border, alignItems: 'center', justifyContent: 'center' },
  detailLabel: { color: palette.inkSubtle, fontSize: 11 },
  detailValue: { color: palette.ink, fontSize: 13, fontWeight: '700' },
  divider: { height: 1, backgroundColor: palette.border, marginLeft: 58 },
});
