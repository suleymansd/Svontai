import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, ChevronRight, Search } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/feedback';
import { PageHeader } from '@/components/ui/page-header';
import { Screen } from '@/components/ui/screen';
import { palette, radius, spacing } from '@/constants/theme';
import { getConversations, setConversationAIReply } from '@/lib/api/endpoints';
import type { Conversation } from '@/lib/api/types';
import { formatRelativeTime, initials } from '@/lib/format';

export default function ConversationsScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const conversations = useQuery({ queryKey: ['conversations'], queryFn: getConversations, refetchInterval: 30_000 });
  const togglePolicy = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => setConversationAIReply(id, enabled),
    onMutate: async ({ id, enabled }) => {
      await queryClient.cancelQueries({ queryKey: ['conversations'] });
      const previous = queryClient.getQueryData<Conversation[]>(['conversations']);
      queryClient.setQueryData<Conversation[]>(['conversations'], (items = []) =>
        items.map((item) => item.id === id ? { ...item, ai_reply_enabled: enabled } : item),
      );
      return { previous };
    },
    onError: (_error, _variables, context) => queryClient.setQueryData(['conversations'], context?.previous),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['conversations'] }),
  });

  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('tr-TR');
    if (!query) return conversations.data || [];
    return (conversations.data || []).filter((item) =>
      `${item.customer_name || ''} ${item.customer_phone} ${item.last_message || ''}`.toLocaleLowerCase('tr-TR').includes(query),
    );
  }, [conversations.data, search]);

  return (
    <Screen
      refreshing={conversations.isRefetching}
      onRefresh={() => void conversations.refetch()}
      header={<PageHeader title="Mesajlar" subtitle={`${conversations.data?.length || 0} konuşma`} />}
    >
      <View style={styles.searchWrap}>
        <Search size={19} color={palette.inkSubtle} />
        <TextInput
          value={search}
          onChangeText={setSearch}
          placeholder="İsim, telefon veya mesaj ara"
          placeholderTextColor={palette.inkSubtle}
          style={styles.searchInput}
        />
      </View>

      {conversations.isLoading ? <LoadingState label="Konuşmalar yükleniyor" /> : null}
      {conversations.error ? <ErrorState message="Konuşmalar alınamadı." onRetry={() => void conversations.refetch()} /> : null}
      {!conversations.isLoading && !conversations.error && !filtered.length ? (
        <EmptyState title="Konuşma bulunamadı" description={search ? 'Arama kriterinizi değiştirin.' : 'Yeni WhatsApp mesajları burada görünür.'} />
      ) : null}

      {filtered.map((conversation) => {
        const name = conversation.customer_name || conversation.customer_phone || 'Bilinmeyen kişi';
        return (
          <Card key={conversation.id} style={styles.rowCard}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${name} konuşmasını aç`}
              onPress={() => router.push(`/conversation/${conversation.id}`)}
              style={({ pressed }) => [styles.conversationLink, pressed && styles.rowPressed]}
            >
              <View style={styles.avatar}><Text style={styles.avatarText}>{initials(name)}</Text></View>
              <View style={styles.copy}>
                <View style={styles.nameRow}>
                  <Text style={styles.name} numberOfLines={1}>{name}</Text>
                  <Text style={styles.time}>{formatRelativeTime(conversation.last_message_at)}</Text>
                </View>
                <Text style={styles.message} numberOfLines={1}>{conversation.last_message || 'Henüz mesaj yok'}</Text>
              </View>
              <ChevronRight size={19} color={palette.inkSubtle} />
            </Pressable>
            <View style={styles.policyRow}>
              <Bot size={14} color={conversation.ai_reply_enabled ? palette.success : palette.inkSubtle} />
              <Text style={[styles.policy, conversation.ai_reply_enabled && styles.policyActive]}>
                {conversation.ai_reply_enabled ? 'AI otomatik yanıt açık' : 'AI otomatik yanıt kapalı'}
              </Text>
              <Switch
                accessibilityLabel={`${name} için AI otomatik yanıt`}
                accessibilityHint="Bu anahtar yalnızca bu konuşmanın otomatik yanıt politikasını değiştirir"
                value={conversation.ai_reply_enabled}
                disabled={togglePolicy.isPending}
                onValueChange={(enabled) => togglePolicy.mutate({ id: conversation.id, enabled })}
                trackColor={{ false: palette.border, true: '#A8DDD4' }}
                thumbColor={conversation.ai_reply_enabled ? palette.success : palette.inkSubtle}
              />
            </View>
          </Card>
        );
      })}
    </Screen>
  );
}

const styles = StyleSheet.create({
  searchWrap: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border, borderRadius: radius.md },
  searchInput: { flex: 1, color: palette.ink, fontSize: 15 },
  rowCard: { padding: 0, overflow: 'hidden' },
  conversationLink: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.md, paddingTop: spacing.md, paddingBottom: spacing.sm },
  rowPressed: { backgroundColor: palette.surfaceMuted },
  avatar: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center', backgroundColor: palette.primarySoft },
  avatarText: { color: palette.primaryDark, fontSize: 14, fontWeight: '800' },
  copy: { flex: 1, gap: spacing.xs },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  name: { flex: 1, color: palette.ink, fontSize: 15, fontWeight: '700' },
  time: { color: palette.inkSubtle, fontSize: 11 },
  message: { color: palette.inkMuted, fontSize: 13 },
  policyRow: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: spacing.xs, paddingHorizontal: spacing.md, borderTopWidth: 1, borderTopColor: palette.border },
  policy: { flex: 1, color: palette.inkSubtle, fontSize: 11, fontWeight: '700' },
  policyActive: { color: palette.success },
});
