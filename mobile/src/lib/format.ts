export function formatRelativeTime(value: string | null): string {
  if (!value) return 'Henüz mesaj yok';
  const date = new Date(value);
  const diffMinutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 1) return 'Şimdi';
  if (diffMinutes < 60) return `${diffMinutes} dk`;
  if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)} sa`;
  return date.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' });
}

export function formatAppointmentDate(value: string): string {
  return new Date(value).toLocaleString('tr-TR', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function initials(value: string): string {
  return value
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || '?';
}
