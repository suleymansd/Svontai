import type { ConversationPage, Message } from './types';

export function chronologicalMessages(pages: ConversationPage[] = []): Message[] {
  const unique = new Map<string, Message>();
  for (const page of pages.slice().reverse()) {
    for (const message of page.messages) unique.set(message.id, message);
  }
  return Array.from(unique.values());
}
