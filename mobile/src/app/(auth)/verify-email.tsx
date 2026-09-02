import { MailCheck } from 'lucide-react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';

import { Button } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { palette, radius, spacing } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { confirmEmailVerification, requestEmailVerification } from '@/lib/api/endpoints';

export default function VerifyEmailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ email?: string }>();
  const email = String(params.email || '').trim().toLowerCase();
  const [code, setCode] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const requestCode = useCallback(async () => {
    if (!email) return;
    setError(null);
    try {
      const result = await requestEmailVerification(email);
      setMessage(result.verified ? 'E-posta adresiniz zaten doğrulanmış.' : 'Yeni doğrulama kodu e-posta adresinize gönderildi.');
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Kod gönderilemedi.');
    }
  }, [email]);

  useEffect(() => {
    const timer = setTimeout(() => void requestCode(), 0);
    return () => clearTimeout(timer);
  }, [requestCode]);

  const confirm = async () => {
    if (code.length !== 6) {
      setError('E-postanıza gelen 6 haneli kodu girin.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await confirmEmailVerification(email, code);
      router.replace('/(auth)/login');
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Kod doğrulanamadı.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <View style={styles.hero}>
        <View style={styles.icon}><MailCheck size={30} color={palette.primaryDark} /></View>
        <Text style={styles.title}>E-postanızı doğrulayın</Text>
        <Text style={styles.description}>{email} adresine gönderilen kodu girin.</Text>
      </View>
      <View style={styles.card}>
        <Text style={styles.label}>Doğrulama kodu</Text>
        <TextInput
          value={code}
          onChangeText={(value) => setCode(value.replace(/\D/g, '').slice(0, 6))}
          keyboardType="number-pad"
          textContentType="oneTimeCode"
          maxLength={6}
          placeholder="000000"
          placeholderTextColor={palette.inkSubtle}
          style={styles.code}
        />
        {message && <Text style={styles.message}>{message}</Text>}
        {error && <Text style={styles.error}>{error}</Text>}
        <Button label="Doğrula" loading={loading} onPress={confirm} />
        <Button label="Yeni kod gönder" variant="secondary" onPress={requestCode} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { alignItems: 'center', paddingTop: 48, gap: spacing.md },
  icon: { width: 64, height: 64, borderRadius: 32, backgroundColor: palette.primarySoft, alignItems: 'center', justifyContent: 'center' },
  title: { color: palette.ink, fontSize: 25, fontWeight: '800' },
  description: { color: palette.inkMuted, textAlign: 'center', lineHeight: 21 },
  card: { backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border, borderRadius: radius.lg, padding: spacing.xl, gap: spacing.lg },
  label: { color: palette.ink, fontSize: 14, fontWeight: '700' },
  code: { minHeight: 58, borderWidth: 1, borderColor: palette.border, borderRadius: radius.md, paddingHorizontal: spacing.lg, color: palette.ink, fontSize: 24, fontWeight: '700', letterSpacing: 0, fontVariant: ['tabular-nums'], textAlign: 'center' },
  message: { color: palette.success, backgroundColor: palette.successSoft, padding: spacing.md, borderRadius: radius.md, fontSize: 13 },
  error: { color: palette.danger, backgroundColor: palette.dangerSoft, padding: spacing.md, borderRadius: radius.md, fontSize: 13 },
});
