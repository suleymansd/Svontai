import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowUp, Bot, Send } from 'lucide-react-native';
import { Redirect, useLocalSearchParams } from 'expo-router';
import * as Crypto from 'expo-crypto';
import { useMemo, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/button';
import { ErrorState, LoadingState } from '@/components/ui/feedback';
import { palette, radius, spacing } from '@/constants/theme';
import { getConversationMessages, sendOperatorMessage, setConversationAIReply } from '@/lib/api/endpoints';
import { chronologicalMessages } from '@/lib/api/conversation-history';
import type { Message } from '@/lib/api/types';
import { useRealtimeConnected } from '@/lib/api/realtime';
import { useAuth } from '@/lib/auth/auth-context';
import { initials } from '@/lib/format';

export default function ConversationDetailScreen() {
  const { status } = useAuth();
  const realtimeConnected = useRealtimeConnected();
  const params = useLocalSearchParams<{ id: string }>();
  const id = String(params.id || '');
  const queryClient = useQueryClient();
  const scrollRef = useRef<FlatList<Message>>(null);
  const atBottom = useRef(true);
  const request = useRef<{ content: string; id: string; key: string } | null>(null);
  const [draft, setDraft] = useState('');
  const [deliveryError, setDeliveryError] = useState<string | null>(null);
  const messages = useInfiniteQuery({
    queryKey: ['conversation-messages', id],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => getConversationMessages(id, pageParam),
    getNextPageParam: (lastPage) => lastPage.next_message_cursor || undefined,
    enabled: Boolean(id) && status === 'authenticated',
    refetchInterval: realtimeConnected ? false : 60_000,
    refetchIntervalInBackground: false,
  });
  const conversation = messages.data?.pages[0];
  const items = useMemo(() => chronologicalMessages(messages.data?.pages), [messages.data]);
  const togglePolicy = useMutation({
    mutationFn: (enabled: boolean) => setConversationAIReply(id, enabled),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['conversations'] });
      void queryClient.invalidateQueries({ queryKey: ['conversation-messages', id] });
    },
    onError: () => setDeliveryError('AI yanıt tercihi kaydedilemedi. Tekrar deneyin.'),
  });
  const send = useMutation({
    mutationFn: (content: string) => {
      if (!request.current || request.current.content !== content || request.current.id !== id) {
        request.current = { content, id, key: Crypto.randomUUID() };
      }
      return sendOperatorMessage(id, content, request.current.key);
    },
    onSuccess: (result) => {
      if (result.delivered || result.delivery_status === 'failed') request.current = null;
      if (result.delivered) setDraft('');
      setDeliveryError(result.delivered ? null : result.note || 'Teslimat doğrulanamadı. Tekrar göndermeden önce konuşmayı kontrol edin.');
      void queryClient.invalidateQueries({ queryKey: ['conversation-messages', id] });
      void queryClient.invalidateQueries({ queryKey: ['conversations'] });
    },
    onError: () => setDeliveryError('Gönderim doğrulanamadı. Mesajınız korunuyor; tekrar göndermeden önce konuşmayı kontrol edin.'),
  });

  if (status === 'unauthenticated') return <Redirect href="/(auth)/login" />;
  if (messages.isLoading) return <SafeAreaView style={styles.safeArea}><LoadingState label="Mesajlar yükleniyor" /></SafeAreaView>;
  if (messages.error && !conversation) return <SafeAreaView style={styles.safeArea}><ErrorState message="Mesaj geçmişi alınamadı." onRetry={() => void messages.refetch()} /></SafeAreaView>;

  const name = conversation?.customer_name || conversation?.customer_phone || 'Konuşma';
  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={88}>
        <View style={styles.contactBar}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials(name)}</Text>
            <View style={styles.onlineDot} />
          </View>
          <View style={styles.contactCopy}>
            <Text style={styles.contactName} numberOfLines={1}>{name}</Text>
            <View style={styles.aiLabel}><Bot size={13} color={conversation?.ai_reply_enabled ? palette.violet : palette.inkSubtle} /><Text style={[styles.contactMeta, conversation?.ai_reply_enabled && styles.contactMetaActive]}>{conversation?.ai_reply_enabled ? 'SvontAI yönetiyor' : 'Manuel görüşme'}</Text></View>
          </View>
          <Switch
            value={conversation?.ai_reply_enabled ?? false}
            disabled={!conversation || togglePolicy.isPending}
            onValueChange={(enabled) => togglePolicy.mutate(enabled)}
            trackColor={{ false: palette.border, true: '#A8DDD4' }}
            thumbColor={conversation?.ai_reply_enabled ? palette.success : palette.inkSubtle}
          />
        </View>

        <FlatList
          ref={scrollRef}
          style={styles.flex}
          contentContainerStyle={styles.messages}
          data={items}
          keyExtractor={(message) => message.id}
          maintainVisibleContentPosition={{ minIndexForVisible: 0 }}
          onScroll={({ nativeEvent }) => {
            atBottom.current = nativeEvent.contentSize.height - nativeEvent.contentOffset.y - nativeEvent.layoutMeasurement.height < 80;
          }}
          scrollEventThrottle={100}
          onContentSizeChange={() => { if (atBottom.current) scrollRef.current?.scrollToEnd({ animated: false }); }}
          ListHeaderComponent={messages.hasNextPage ? <Button label="Önceki mesajlar" variant="secondary" icon={<ArrowUp size={18} color={palette.ink} />} loading={messages.isFetchingNextPage} disabled={messages.isFetching} onPress={() => { atBottom.current = false; void messages.fetchNextPage(); }} /> : null}
          ListFooterComponent={messages.error ? <ErrorState message="Mesajlar yenilenemedi." onRetry={() => void messages.refetch()} /> : null}
          renderItem={({ item: message }) => {
            const outgoing = message.sender !== 'user';
            const automated = message.sender === 'bot';
            return (
              <View key={message.id} style={[styles.bubble, outgoing ? styles.outgoing : styles.incoming, automated && styles.automated]}>
                {outgoing ? <Text style={[styles.senderLabel, automated && styles.automatedLabel]}>{automated ? 'SVONTAI' : 'SİZ'}</Text> : null}
                <Text style={[styles.messageText, outgoing && styles.outgoingText, automated && styles.automatedText]}>{message.content}</Text>
                <Text style={[styles.messageTime, outgoing && styles.outgoingTime, automated && styles.automatedTime]}>
                  {new Date(message.created_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
                </Text>
              </View>
            );
          }}
        />

        {deliveryError ? <Text style={styles.deliveryError}>{deliveryError}</Text> : null}
        <View style={styles.composer}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Mesaj yazın"
            placeholderTextColor={palette.inkSubtle}
            multiline
            editable={!send.isPending}
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
  contactBar: { minHeight: 70, flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm, backgroundColor: palette.surface, borderBottomWidth: 1, borderBottomColor: palette.border },
  avatar: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', backgroundColor: palette.primarySoft },
  avatarText: { color: palette.primaryDark, fontSize: 13, fontWeight: '900' },
  onlineDot: { position: 'absolute', right: 0, bottom: 1, width: 11, height: 11, borderRadius: 6, borderWidth: 2, borderColor: palette.surface, backgroundColor: palette.success },
  contactCopy: { flex: 1, gap: spacing.xs },
  contactName: { color: palette.ink, fontSize: 15, fontWeight: '900' },
  contactMeta: { color: palette.inkMuted, fontSize: 11 },
  contactMetaActive: { color: palette.violet, fontWeight: '700' },
  aiLabel: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  messages: { padding: spacing.lg, paddingBottom: spacing.xl, gap: spacing.sm },
  bubble: { maxWidth: '84%', paddingHorizontal: spacing.md, paddingVertical: 10, borderRadius: radius.lg, gap: 4 },
  incoming: { alignSelf: 'flex-start', backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border, borderBottomLeftRadius: radius.sm },
  outgoing: { alignSelf: 'flex-end', backgroundColor: palette.navy, borderBottomRightRadius: radius.sm },
  automated: { backgroundColor: palette.violetSoft, borderWidth: 1, borderColor: '#DDD6FA' },
  senderLabel: { color: '#83DCC9', fontSize: 8, lineHeight: 11, fontWeight: '900' },
  automatedLabel: { color: palette.violet },
  messageText: { color: palette.ink, fontSize: 14, lineHeight: 20 },
  outgoingText: { color: '#FFFFFF' },
  automatedText: { color: palette.ink },
  messageTime: { alignSelf: 'flex-end', color: palette.inkSubtle, fontSize: 10 },
  outgoingTime: { color: '#AAB5C5' },
  automatedTime: { color: palette.inkSubtle },
  deliveryError: { color: palette.danger, backgroundColor: palette.dangerSoft, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm, fontSize: 12 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm, padding: spacing.md, backgroundColor: palette.surface, borderTopWidth: 1, borderTopColor: palette.border },
  composerInput: { flex: 1, minHeight: 48, maxHeight: 120, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, color: palette.ink, backgroundColor: palette.surfaceRaised, borderWidth: 1, borderColor: palette.border, borderRadius: radius.lg, fontSize: 15 },
  sendButton: { width: 50, height: 50, minHeight: 50, paddingHorizontal: 0, borderRadius: 25, backgroundColor: palette.navy, borderColor: palette.navy },
});
