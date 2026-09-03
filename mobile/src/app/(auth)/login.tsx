import { Check, Eye, EyeOff, LockKeyhole, Mail, ShieldCheck } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Brand } from '@/components/ui/brand';
import { Button } from '@/components/ui/button';
import { palette, radius, shadow, spacing } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { useAuth } from '@/lib/auth/auth-context';

export default function LoginScreen() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [twoFactorCode, setTwoFactorCode] = useState('');
  const [requiresTwoFactor, setRequiresTwoFactor] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!email.trim() || !password) {
      setError('E-posta ve şifrenizi girin.');
      return;
    }
    if (requiresTwoFactor && twoFactorCode.length !== 6) {
      setError('Authenticator uygulamanızdaki 6 haneli kodu girin.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await signIn(email, password, requiresTwoFactor ? twoFactorCode : undefined);
    } catch (caught) {
      const apiError = caught instanceof ApiError ? caught : null;
      if (apiError?.code === 'TWO_FACTOR_REQUIRED') {
        setRequiresTwoFactor(true);
        setError('Hesabınız için Authenticator kodu gerekli.');
      } else if (apiError?.code === 'EMAIL_VERIFICATION_REQUIRED') {
        router.push({ pathname: '/(auth)/verify-email', params: { email: email.trim().toLowerCase() } });
      } else {
        setError(apiError?.message || 'Giriş yapılamadı. Lütfen tekrar deneyin.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.brandWrap}>
            <Brand />
            <View style={styles.productBadge}>
              <View style={styles.productDot} />
              <Text style={styles.eyebrow}>İŞLETME OPERASYON MERKEZİ</Text>
            </View>
            <Text style={styles.title}>İşletmenize güvenli giriş yapın</Text>
            <Text style={styles.subtitle}>Mesajlarınızı, randevularınızı ve AI operasyonunuzu tek yerden yönetin.</Text>
          </View>

          <View style={styles.formCard}>
            <View style={styles.formHeading}>
              <Text style={styles.formTitle}>Hesabınıza giriş yapın</Text>
              <View style={styles.encryptedBadge}><ShieldCheck size={13} color={palette.success} /><Text style={styles.encryptedText}>Şifreli</Text></View>
            </View>
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>E-posta</Text>
              <View style={styles.inputWrap}>
                <Mail size={19} color={palette.inkSubtle} />
                <TextInput
                  value={email}
                  onChangeText={setEmail}
                  placeholder="ornek@isletme.com"
                  placeholderTextColor={palette.inkSubtle}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="email-address"
                  textContentType="username"
                  style={styles.input}
                />
              </View>
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.label}>Şifre</Text>
              <View style={styles.inputWrap}>
                <LockKeyhole size={19} color={palette.inkSubtle} />
                <TextInput
                  value={password}
                  onChangeText={setPassword}
                  placeholder="Şifreniz"
                  placeholderTextColor={palette.inkSubtle}
                  secureTextEntry={!showPassword}
                  textContentType="password"
                  style={styles.input}
                />
                <Pressable accessibilityLabel={showPassword ? 'Şifreyi gizle' : 'Şifreyi göster'} onPress={() => setShowPassword((value) => !value)}>
                  {showPassword ? <EyeOff size={19} color={palette.inkMuted} /> : <Eye size={19} color={palette.inkMuted} />}
                </Pressable>
              </View>
            </View>

            {requiresTwoFactor && (
              <View style={styles.fieldGroup}>
                <Text style={styles.label}>Authenticator kodu</Text>
                <View style={styles.inputWrap}>
                  <LockKeyhole size={19} color={palette.violet} />
                  <TextInput
                    value={twoFactorCode}
                    onChangeText={(value) => setTwoFactorCode(value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="000000"
                    placeholderTextColor={palette.inkSubtle}
                    keyboardType="number-pad"
                    textContentType="oneTimeCode"
                    maxLength={6}
                    style={[styles.input, styles.codeInput]}
                  />
                </View>
              </View>
            )}

            {error && <Text style={styles.error}>{error}</Text>}
            <Button label="Giriş yap" variant="dark" loading={loading} icon={!loading ? <Check size={18} color={palette.surface} /> : undefined} onPress={submit} />
          </View>

          <View style={styles.securityRow}>
            <ShieldCheck size={14} color={palette.inkSubtle} />
            <Text style={styles.security}>Oturum bilgileriniz cihazınızın güvenli kasasında saklanır.</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: palette.canvas },
  flex: { flex: 1 },
  content: { width: '100%', maxWidth: 560, alignSelf: 'center', flexGrow: 1, justifyContent: 'center', padding: spacing.xl, gap: spacing.xl },
  brandWrap: { width: '100%', alignItems: 'center', gap: spacing.md },
  productBadge: { marginTop: spacing.sm, minHeight: 27, paddingHorizontal: 10, flexDirection: 'row', alignItems: 'center', gap: 7, borderRadius: 14, backgroundColor: palette.primarySoft },
  productDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: palette.primary },
  eyebrow: { color: palette.primaryDark, fontSize: 9, lineHeight: 13, fontWeight: '900', letterSpacing: 0 },
  title: { color: palette.navy, fontSize: 27, lineHeight: 33, fontWeight: '900', textAlign: 'center' },
  subtitle: { color: palette.inkMuted, fontSize: 14, lineHeight: 21, textAlign: 'center', maxWidth: 340 },
  formCard: { width: '100%', backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, padding: spacing.xl, gap: spacing.lg, ...shadow },
  formHeading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  formTitle: { color: palette.ink, fontSize: 16, lineHeight: 22, fontWeight: '900' },
  encryptedBadge: { minHeight: 26, paddingHorizontal: 8, flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 13, backgroundColor: palette.successSoft },
  encryptedText: { color: palette.success, fontSize: 9, lineHeight: 12, fontWeight: '900' },
  fieldGroup: { gap: spacing.sm },
  label: { color: palette.ink, fontSize: 14, fontWeight: '700' },
  inputWrap: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: spacing.md, borderWidth: 1, borderColor: palette.borderStrong, borderRadius: radius.md, paddingHorizontal: spacing.lg, backgroundColor: palette.surfaceRaised },
  input: { flex: 1, color: palette.ink, fontSize: 16, paddingVertical: 12 },
  codeInput: { letterSpacing: 0, fontWeight: '700', fontVariant: ['tabular-nums'] },
  error: { color: palette.danger, backgroundColor: palette.dangerSoft, padding: spacing.md, borderRadius: radius.md, fontSize: 13, lineHeight: 19 },
  securityRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm },
  security: { color: palette.inkSubtle, textAlign: 'center', fontSize: 11 },
});
