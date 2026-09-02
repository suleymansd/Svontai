import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, Send } from 'lucide-react-native';
import { Redirect, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/button';
import { ErrorState, LoadingState } from '@/components/ui/feedback';
import { palette, radius, spacing } from '@/constants/theme';
import { getConversationMessages, getConversations, sendOperatorMessage, setConversationAIReply } from '@/lib/api/endpoints';
import { useAuth } from '@/lib/auth/auth-context';

export default function ConversationDetailScreen() {
  const { status } = useAuth();
  const params = useLocalSearchParams<{ id: string }>();
  const id = String(params.id || '');
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState('');
  const [deliveryError, setDeliveryError] = useState<string | null>(null);
  const conversations = useQuery({ queryKey: ['conversations'], queryFn: getConversations });
  const messages = useQuery({
    queryKey: ['conversation-messages', id],
    queryFn: () => getConversationMessages(id),
    enabled: Boolean(id),
    refetchInterval: 5_000,
  });
  const conversation = useMemo(() => conversations.data?.find((item) => item.id === id), [conversations.data, id]);
  const togglePolicy = useMutation({
    mutationFn: (enabled: boolean) => setConversationAIReply(id, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['conversations'] }),
  });
  const send = useMutation({
    mutationFn: (content: string) => sendOperatorMessage(id, content),
    onSuccess: (result) => {
      setDraft('');
      setDeliveryError(result.delivered ? null : result.note || 'Mesaj WhatsApp’a iletilemedi.');
      void queryClient.invalidateQueries({ queryKey: ['conversation-messages', id] });
      void queryClient.invalidateQueries({ queryKey: ['conversations'] });
    },
    onError: () => setDeliveryError('Mesaj gönderilemedi. Bağlantınızı kontrol edin.'),
  });

  if (status === 'unauthenticated') return <Redirect href="/(auth)/login" />;
  if (messages.isLoading) return <SafeAreaView style={styles.safeArea}><LoadingState label="Mesajlar yükleniyor" /></SafeAreaView>;
  if (messages.error) return <SafeAreaView style={styles.safeArea}><ErrorState message="Mesaj geçmişi alınamadı." onRetry={() => void messages.refetch()} /></SafeAreaView>;

  const name = conversation?.customer_name || conversation?.customer_phone || 'Konuşma';
  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={88}>
        <View style={styles.contactBar}>
          <View style={styles.contactCopy}>
            <Text style={styles.contactName} numberOfLines={1}>{name}</Text>
            <View style={styles.aiLabel}><Bot size={14} color={conversation?.ai_reply_enabled ? palette.success : palette.inkSubtle} /><Text style={styles.contactMeta}>{conversation?.ai_reply_enabled ? 'AI otomatik yanıt açık' : 'AI otomatik yanıt kapalı'}</Text></View>
          </View>
          <Switch
            value={conversation?.ai_reply_enabled ?? false}
            disabled={!conversation || togglePolicy.isPending}
            onValueChange={(enabled) => togglePolicy.mutate(enabled)}
            trackColor={{ false: palette.border, true: '#A8DDD4' }}
            thumbColor={conversation?.ai_reply_enabled ? palette.success : palette.inkSubtle}
          />
        </View>

        <ScrollView style={styles.flex} contentContainerStyle={styles.messages}>
          {(messages.data || []).map((message) => {
            const outgoing = message.sender !== 'user';
            return (
              <View key={message.id} style={[styles.bubble, outgoing ? styles.outgoing : styles.incoming]}>
                <Text style={[styles.messageText, outgoing && styles.outgoingText]}>{message.content}</Text>
                <Text style={[styles.messageTime, outgoing && styles.outgoingTime]}>
                  {new Date(message.created_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
                </Text>
              </View>
            );
          })}
        </ScrollView>

        {deliveryError ? <Text style={styles.deliveryError}>{deliveryError}</Text> : null}
        <View style={styles.composer}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Mesaj yazın"
            placeholderTextColor={palette.inkSubtle}
            multiline
            maxLength={2000}
            style={styles.composerInput}
          />
          <Button
            accessibilityLabel="Mesajı gönder"
            label=""
            icon={<Send size={20} color="#FFFFFF" />}
            loading={send.isPending}
            disabled={!draft.trim()}
            onPress={() => send.mutate(draft.trim())}
            style={styles.sendButton}
          />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: palette.canvas },
  flex: { flex: 1 },
  contactBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: spacing.lg, paddingVertical: spacing.md, backgroundColor: palette.surface, borderBottomWidth: 1, borderBottomColor: palette.border },
  contactCopy: { flex: 1, gap: spacing.xs },
  contactName: { color: palette.ink, fontSize: 16, fontWeight: '800' },
  contactMeta: { color: palette.inkMuted, fontSize: 11 },
  aiLabel: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  messages: { padding: spacing.lg, gap: spacing.sm },
  bubble: { maxWidth: '82%', paddingHorizontal: spacing.md, paddingVertical: 10, borderRadius: radius.lg, gap: spacing.xs },
  incoming: { alignSelf: 'flex-start', backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border, borderBottomLeftRadius: radius.sm },
  outgoing: { alignSelf: 'flex-end', backgroundColor: palette.primaryDark, borderBottomRightRadius: radius.sm },
  messageText: { color: palette.ink, fontSize: 15, lineHeight: 21 },
  outgoingText: { color: '#FFFFFF' },
  messageTime: { alignSelf: 'flex-end', color: palette.inkSubtle, fontSize: 10 },
  outgoingTime: { color: '#CFEAF0' },
  deliveryError: { color: palette.danger, backgroundColor: palette.dangerSoft, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm, fontSize: 12 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm, padding: spacing.md, backgroundColor: palette.surface, borderTopWidth: 1, borderTopColor: palette.border },
  composerInput: { flex: 1, minHeight: 48, maxHeight: 120, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, color: palette.ink, backgroundColor: palette.surfaceMuted, borderRadius: radius.lg, fontSize: 15 },
  sendButton: { width: 50, height: 50, minHeight: 50, paddingHorizontal: 0 },
});
