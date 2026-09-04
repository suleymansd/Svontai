import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Archive,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Edit3,
  FileText,
  MessageCircle,
  MoreHorizontal,
  Pin,
  PinOff,
  Plus,
  Share2,
  Sparkles,
  TriangleAlert,
  UsersRound,
  X,
} from 'lucide-react-native';
import { useMemo, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { Button } from '@/components/ui/button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/feedback';
import { PageHeader } from '@/components/ui/page-header';
import { Screen } from '@/components/ui/screen';
import { palette, radius, spacing } from '@/constants/theme';
import {
  createWorkspaceNote,
  getOperationalReport,
  getWorkspaceNotes,
  updateWorkspaceNote,
} from '@/lib/api/endpoints';
import type { OperationalReport, WorkspaceNote } from '@/lib/api/types';
import { useAuth } from '@/lib/auth/auth-context';

type ViewMode = 'reports' | 'notes';
type NoteDraft = { title: string; content: string; color: WorkspaceNote['color']; pinned: boolean };

const emptyDraft: NoteDraft = { title: '', content: '', color: 'slate', pinned: false };
const colors: { value: WorkspaceNote['color']; label: string; fill: string }[] = [
  { value: 'slate', label: 'Gri', fill: '#7C8798' },
  { value: 'blue', label: 'Mavi', fill: palette.primary },
  { value: 'amber', label: 'Sarı', fill: '#E59B24' },
  { value: 'emerald', label: 'Yeşil', fill: palette.success },
  { value: 'rose', label: 'Kırmızı', fill: palette.coral },
];

export default function NotesScreen() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const canEdit = Boolean(me?.permissions.includes('dashboard:edit'));
  const [mode, setMode] = useState<ViewMode>('reports');
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<WorkspaceNote | null>(null);
  const [draft, setDraft] = useState<NoteDraft>(emptyDraft);

  const dailyReport = useQuery({
    queryKey: ['operational-report', 'today'],
    queryFn: () => getOperationalReport('today'),
  });
  const weeklyReport = useQuery({
    queryKey: ['operational-report', 'week'],
    queryFn: () => getOperationalReport('week'),
  });
  const notes = useQuery({ queryKey: ['workspace-notes'], queryFn: getWorkspaceNotes });

  const saveNote = useMutation({
    mutationFn: () => editing
      ? updateWorkspaceNote(editing.id, draft)
      : createWorkspaceNote(draft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['workspace-notes'] });
      closeEditor();
    },
    onError: () => Alert.alert('Not kaydedilemedi', 'Bilgileri kontrol edip tekrar deneyin.'),
  });

  const updateNote = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<WorkspaceNote> }) => updateWorkspaceNote(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workspace-notes'] }),
    onError: () => Alert.alert('İşlem tamamlanamadı', 'Not güncellenemedi. Lütfen tekrar deneyin.'),
  });

  const sortedNotes = useMemo(() => notes.data || [], [notes.data]);
  const refreshing = dailyReport.isRefetching || weeklyReport.isRefetching || notes.isRefetching;
  const refresh = () => void Promise.all([dailyReport.refetch(), weeklyReport.refetch(), notes.refetch()]);

  function openNewNote(initial: NoteDraft = emptyDraft) {
    setEditing(null);
    setDraft(initial);
    setEditorOpen(true);
  }

  function openEditNote(note: WorkspaceNote) {
    setEditing(note);
    setDraft({ title: note.title, content: note.content, color: note.color, pinned: note.pinned });
    setEditorOpen(true);
  }

  function closeEditor() {
    setEditorOpen(false);
    setEditing(null);
    setDraft(emptyDraft);
  }

  function archiveNote(note: WorkspaceNote) {
    Alert.alert('Not arşivlensin mi?', 'Not aktif listeden kaldırılır, web panelindeki arşivden erişilebilir.', [
      { text: 'Vazgeç', style: 'cancel' },
      { text: 'Arşivle', style: 'destructive', onPress: () => updateNote.mutate({ id: note.id, data: { archived: true } }) },
    ]);
  }

  function saveReport(report: OperationalReport) {
    openNewNote({ title: report.title, content: report.text, color: 'blue', pinned: true });
  }

  const reportsLoading = dailyReport.isLoading || weeklyReport.isLoading;
  const reportsError = dailyReport.error || weeklyReport.error;

  return (
    <>
      <Screen
        refreshing={refreshing}
        onRefresh={refresh}
        header={<PageHeader title="Önemli Notlar" subtitle="Raporlar ve işletme hafızası" />}
      >
        <View style={styles.segmentedControl}>
          <SegmentButton kind="reports" label="Raporlar" active={mode === 'reports'} onPress={() => setMode('reports')} />
          <SegmentButton kind="notes" label="Notlar" active={mode === 'notes'} onPress={() => setMode('notes')} />
        </View>

        {mode === 'reports' ? (
          <>
            <View style={styles.introBand}>
              <View style={styles.introIcon}><Sparkles size={21} color="#82E6D0" /></View>
              <View style={styles.flex}>
                <Text style={styles.introTitle}>Operasyon raporları hazır</Text>
                <Text style={styles.introText}>Mesaj, müşteri, randevu ve otomasyon verileri canlı olarak özetlenir.</Text>
              </View>
            </View>
            {reportsLoading ? <LoadingState label="Raporlar hazırlanıyor" /> : null}
            {reportsError ? <ErrorState message="Operasyon raporları alınamadı." onRetry={refresh} /> : null}
            {dailyReport.data ? <ReportCard report={dailyReport.data} canSave={canEdit} onSave={saveReport} /> : null}
            {weeklyReport.data ? <ReportCard report={weeklyReport.data} canSave={canEdit} onSave={saveReport} /> : null}
          </>
        ) : (
          <>
            <View style={styles.sectionHeader}>
              <View>
                <Text style={styles.sectionTitle}>İşletme notları</Text>
                <Text style={styles.sectionCaption}>{sortedNotes.length} aktif kayıt</Text>
              </View>
              {canEdit ? (
                <Pressable accessibilityLabel="Yeni not ekle" onPress={() => openNewNote()} style={({ pressed }) => [styles.addButton, pressed && styles.pressed]}>
                  <Plus size={19} color="#FFFFFF" strokeWidth={2.6} />
                </Pressable>
              ) : null}
            </View>
            {notes.isLoading ? <LoadingState label="Notlar yükleniyor" /> : null}
            {notes.error ? <ErrorState message="Notlar alınamadı." onRetry={() => void notes.refetch()} /> : null}
            {!notes.isLoading && !notes.error && !sortedNotes.length ? (
              <EmptyState title="Henüz önemli not yok" description="Raporları kaydedebilir veya işletmeniz için takip edilmesi gereken bir not ekleyebilirsiniz." />
            ) : null}
            {sortedNotes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                canEdit={canEdit}
                busy={updateNote.isPending}
                onEdit={openEditNote}
                onTogglePin={(item) => updateNote.mutate({ id: item.id, data: { pinned: !item.pinned } })}
                onArchive={archiveNote}
              />
            ))}
          </>
        )}
      </Screen>

      <NoteEditor
        visible={editorOpen}
        editing={Boolean(editing)}
        draft={draft}
        saving={saveNote.isPending}
        onChange={setDraft}
        onClose={closeEditor}
        onSave={() => saveNote.mutate()}
      />
    </>
  );
}

function SegmentButton({ kind, label, active, onPress }: { kind: ViewMode; label: string; active: boolean; onPress: () => void }) {
  const iconColor = active ? palette.primaryDark : palette.inkSubtle;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.segmentButton, active && styles.segmentButtonActive, pressed && styles.pressed]}>
      {kind === 'reports' ? <BarChart3 size={16} color={iconColor} /> : <FileText size={16} color={iconColor} />}
      <Text style={[styles.segmentText, active && styles.segmentTextActive]}>{label}</Text>
    </Pressable>
  );
}

function ReportCard({ report, canSave, onSave }: { report: OperationalReport; canSave: boolean; onSave: (report: OperationalReport) => void }) {
  const [expanded, setExpanded] = useState(false);
  const metrics = report.metrics;
  const generated = new Date(report.generated_at).toLocaleString('tr-TR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

  async function shareReport() {
    await Share.share({ title: report.title, message: report.text });
  }

  return (
    <View style={styles.reportCard}>
      <View style={styles.reportTop}>
        <View style={[styles.reportStatusIcon, report.health.healthy ? styles.reportHealthy : styles.reportWarning]}>
          {report.health.healthy ? <CheckCircle2 size={20} color={palette.success} /> : <TriangleAlert size={20} color={palette.warning} />}
        </View>
        <View style={styles.flex}>
          <Text style={styles.reportPeriod}>{report.period === 'today' ? 'GÜNLÜK RAPOR' : 'SON 7 GÜN'}</Text>
          <Text style={styles.reportTitle}>{report.health.healthy ? 'Operasyon sağlıklı' : 'Kontrol gereken durum var'}</Text>
          <Text style={styles.reportDate}>{generated}</Text>
        </View>
      </View>

      <Text style={styles.reportSummary}>{report.summary}</Text>
      <View style={styles.metricsGrid}>
        <Metric icon={<MessageCircle size={15} color={palette.primaryDark} />} value={metrics.incoming_messages} label="Mesaj" />
        <Metric icon={<Sparkles size={15} color={palette.violet} />} value={metrics.ai_replies} label="AI yanıtı" />
        <Metric icon={<UsersRound size={15} color={palette.warning} />} value={metrics.leads} label="Müşteri" />
        <Metric icon={<CalendarDays size={15} color={palette.success} />} value={metrics.appointments} label="Randevu" />
      </View>

      {expanded ? (
        <View style={styles.reportDetail}>
          {report.health.attention_reasons.map((reason) => <Text key={reason} style={styles.attentionText}>• {reason}</Text>)}
          <View style={styles.detailRow}><Text style={styles.detailLabel}>Yanıt oranı</Text><Text style={styles.detailValue}>%{metrics.response_rate}</Text></View>
          <View style={styles.detailRow}><Text style={styles.detailLabel}>Başarılı otomasyon</Text><Text style={styles.detailValue}>{metrics.successful_automations}</Text></View>
          <View style={styles.detailRow}><Text style={styles.detailLabel}>Açık otomasyon hatası</Text><Text style={styles.detailValue}>{metrics.unresolved_automation_failures}</Text></View>
        </View>
      ) : null}

      <View style={styles.reportActions}>
        <Pressable onPress={() => setExpanded((value) => !value)} style={({ pressed }) => [styles.textAction, pressed && styles.pressed]}>
          <MoreHorizontal size={17} color={palette.inkMuted} />
          <Text style={styles.textActionLabel}>{expanded ? 'Daralt' : 'Detaylar'}</Text>
        </Pressable>
        <Pressable onPress={() => void shareReport()} style={({ pressed }) => [styles.iconButton, pressed && styles.pressed]} accessibilityLabel="Raporu paylaş">
          <Share2 size={17} color={palette.ink} />
        </Pressable>
        {canSave ? (
          <Pressable onPress={() => onSave(report)} style={({ pressed }) => [styles.saveReportButton, pressed && styles.pressed]}>
            <Pin size={15} color="#FFFFFF" />
            <Text style={styles.saveReportText}>Nota kaydet</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function Metric({ icon, value, label }: { icon: React.ReactNode; value: number; label: string }) {
  return (
    <View style={styles.metric}>
      <View style={styles.metricIcon}>{icon}</View>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function NoteCard({ note, canEdit, busy, onEdit, onTogglePin, onArchive }: {
  note: WorkspaceNote;
  canEdit: boolean;
  busy: boolean;
  onEdit: (note: WorkspaceNote) => void;
  onTogglePin: (note: WorkspaceNote) => void;
  onArchive: (note: WorkspaceNote) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const updatedAt = new Date(note.updated_at).toLocaleString('tr-TR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  const accent = colors.find((item) => item.value === note.color)?.fill || colors[0].fill;
  return (
    <View style={styles.noteCard}>
      <View style={[styles.noteAccent, { backgroundColor: accent }]} />
      <View style={styles.noteBody}>
        <View style={styles.noteTop}>
          <View style={styles.flex}>
            <View style={styles.noteTitleRow}>
              {note.pinned ? <Pin size={13} color={palette.primaryDark} fill={palette.primarySoft} /> : null}
              <Text style={styles.noteTitle} numberOfLines={2}>{note.title}</Text>
            </View>
            <Text style={styles.noteDate}>Güncellendi · {updatedAt}</Text>
          </View>
          {canEdit ? (
            <View style={styles.noteActions}>
              <Pressable disabled={busy} onPress={() => onTogglePin(note)} style={styles.smallIconButton} accessibilityLabel={note.pinned ? 'Sabitlemeyi kaldır' : 'Notu sabitle'}>
                {note.pinned ? <PinOff size={16} color={palette.inkMuted} /> : <Pin size={16} color={palette.inkMuted} />}
              </Pressable>
              <Pressable disabled={busy} onPress={() => onEdit(note)} style={styles.smallIconButton} accessibilityLabel="Notu düzenle"><Edit3 size={16} color={palette.inkMuted} /></Pressable>
              <Pressable disabled={busy} onPress={() => onArchive(note)} style={styles.smallIconButton} accessibilityLabel="Notu arşivle"><Archive size={16} color={palette.inkMuted} /></Pressable>
            </View>
          ) : null}
        </View>
        <Pressable onPress={() => setExpanded((value) => !value)} accessibilityRole="button">
          <Text style={styles.noteContent} numberOfLines={expanded ? undefined : 6}>{note.content}</Text>
          {note.content.length > 220 ? <Text style={styles.expandLabel}>{expanded ? 'Daha az göster' : 'Tamamını göster'}</Text> : null}
        </Pressable>
      </View>
    </View>
  );
}

function NoteEditor({ visible, editing, draft, saving, onChange, onClose, onSave }: {
  visible: boolean;
  editing: boolean;
  draft: NoteDraft;
  saving: boolean;
  onChange: (draft: NoteDraft) => void;
  onClose: () => void;
  onSave: () => void;
}) {
  const valid = draft.title.trim().length > 0 && draft.content.trim().length > 0;
  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <KeyboardAvoidingView style={styles.modalRoot} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.modalHeader}>
          <Pressable onPress={onClose} style={styles.modalClose} accessibilityLabel="Not düzenleyiciyi kapat"><X size={21} color={palette.ink} /></Pressable>
          <View style={styles.modalHeading}>
            <Text style={styles.modalTitle}>{editing ? 'Notu düzenle' : 'Yeni önemli not'}</Text>
            <Text style={styles.modalSubtitle}>İşletme çalışma alanına kaydedilir</Text>
          </View>
          <View style={styles.modalClose} />
        </View>
        <ScrollView contentContainerStyle={styles.form} keyboardShouldPersistTaps="handled">
          <View style={styles.field}>
            <Text style={styles.fieldLabel}>Başlık</Text>
            <TextInput
              value={draft.title}
              onChangeText={(title) => onChange({ ...draft, title })}
              placeholder="Örn. Eylül kampanyası"
              placeholderTextColor={palette.inkSubtle}
              maxLength={140}
              style={styles.titleInput}
              returnKeyType="next"
            />
            <Text style={styles.counter}>{draft.title.length}/140</Text>
          </View>
          <View style={styles.field}>
            <Text style={styles.fieldLabel}>Not</Text>
            <TextInput
              value={draft.content}
              onChangeText={(content) => onChange({ ...draft, content })}
              placeholder="Takip edilmesi gereken bilgiyi yazın..."
              placeholderTextColor={palette.inkSubtle}
              multiline
              textAlignVertical="top"
              style={styles.contentInput}
            />
          </View>
          <View style={styles.field}>
            <Text style={styles.fieldLabel}>Renk</Text>
            <View style={styles.colorRow}>
              {colors.map((item) => (
                <Pressable
                  key={item.value}
                  accessibilityLabel={`${item.label} not rengi`}
                  onPress={() => onChange({ ...draft, color: item.value })}
                  style={[styles.colorButton, draft.color === item.value && styles.colorButtonActive]}
                >
                  <View style={[styles.colorSwatch, { backgroundColor: item.fill }]} />
                </Pressable>
              ))}
            </View>
          </View>
          <Pressable onPress={() => onChange({ ...draft, pinned: !draft.pinned })} style={styles.pinToggle}>
            <View style={[styles.checkbox, draft.pinned && styles.checkboxActive]}>{draft.pinned ? <Pin size={13} color="#FFFFFF" /> : null}</View>
            <View style={styles.flex}>
              <Text style={styles.pinTitle}>Önemli olarak sabitle</Text>
              <Text style={styles.pinDescription}>Sabitlenen notlar listenin en üstünde görünür.</Text>
            </View>
          </Pressable>
          <Button label={editing ? 'Değişiklikleri kaydet' : 'Notu kaydet'} loading={saving} disabled={!valid} onPress={onSave} icon={<FileText size={18} color="#FFFFFF" />} />
        </ScrollView>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  pressed: { opacity: 0.72 },
  segmentedControl: { minHeight: 44, flexDirection: 'row', padding: 3, borderRadius: radius.md, backgroundColor: palette.surfaceMuted },
  segmentButton: { flex: 1, minHeight: 38, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm, borderRadius: radius.sm },
  segmentButtonActive: { backgroundColor: palette.surface },
  segmentText: { color: palette.inkMuted, fontSize: 12, lineHeight: 17, fontWeight: '800' },
  segmentTextActive: { color: palette.ink },
  introBand: { minHeight: 82, padding: spacing.lg, flexDirection: 'row', alignItems: 'center', gap: spacing.md, borderRadius: radius.lg, backgroundColor: palette.navy },
  introIcon: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md, backgroundColor: palette.navySoft },
  introTitle: { color: palette.surface, fontSize: 14, lineHeight: 20, fontWeight: '900' },
  introText: { marginTop: 3, color: '#AEB8C9', fontSize: 10, lineHeight: 15 },
  reportCard: { padding: spacing.lg, gap: spacing.md, borderWidth: 1, borderColor: palette.border, borderRadius: radius.lg, backgroundColor: palette.surface },
  reportTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  reportStatusIcon: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md },
  reportHealthy: { backgroundColor: palette.successSoft },
  reportWarning: { backgroundColor: palette.warningSoft },
  reportPeriod: { color: palette.primaryDark, fontSize: 8, lineHeight: 11, fontWeight: '900' },
  reportTitle: { color: palette.ink, fontSize: 15, lineHeight: 20, fontWeight: '900' },
  reportDate: { marginTop: 1, color: palette.inkSubtle, fontSize: 9, lineHeight: 13 },
  reportSummary: { color: palette.inkMuted, fontSize: 12, lineHeight: 18 },
  metricsGrid: { flexDirection: 'row', borderTopWidth: 1, borderBottomWidth: 1, borderColor: palette.border, paddingVertical: spacing.md },
  metric: { flex: 1, minWidth: 0, alignItems: 'center', gap: 2 },
  metricIcon: { height: 19, alignItems: 'center', justifyContent: 'center' },
  metricValue: { color: palette.ink, fontSize: 16, lineHeight: 20, fontWeight: '900', fontVariant: ['tabular-nums'] },
  metricLabel: { color: palette.inkSubtle, fontSize: 8, lineHeight: 11, fontWeight: '700' },
  reportDetail: { gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, backgroundColor: palette.surfaceRaised },
  attentionText: { color: palette.warning, fontSize: 10, lineHeight: 15, fontWeight: '700' },
  detailRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  detailLabel: { color: palette.inkMuted, fontSize: 10, lineHeight: 15 },
  detailValue: { color: palette.ink, fontSize: 11, lineHeight: 15, fontWeight: '900', fontVariant: ['tabular-nums'] },
  reportActions: { minHeight: 36, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  textAction: { minHeight: 36, flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: spacing.sm },
  textActionLabel: { color: palette.inkMuted, fontSize: 10, fontWeight: '800' },
  iconButton: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: palette.border, borderRadius: radius.md },
  saveReportButton: { minHeight: 36, marginLeft: 'auto', paddingHorizontal: spacing.md, flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: radius.md, backgroundColor: palette.primary },
  saveReportText: { color: '#FFFFFF', fontSize: 10, fontWeight: '900' },
  sectionHeader: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  sectionTitle: { color: palette.ink, fontSize: 16, lineHeight: 22, fontWeight: '900' },
  sectionCaption: { marginTop: 2, color: palette.inkSubtle, fontSize: 10, lineHeight: 14 },
  addButton: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md, backgroundColor: palette.primary },
  noteCard: { minHeight: 124, flexDirection: 'row', overflow: 'hidden', borderWidth: 1, borderColor: palette.border, borderRadius: radius.lg, backgroundColor: palette.surface },
  noteAccent: { width: 5 },
  noteBody: { flex: 1, padding: spacing.lg, gap: spacing.md },
  noteTop: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  noteTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  noteTitle: { flex: 1, color: palette.ink, fontSize: 14, lineHeight: 19, fontWeight: '900' },
  noteDate: { marginTop: 3, color: palette.inkSubtle, fontSize: 9, lineHeight: 13 },
  noteActions: { flexDirection: 'row', gap: 2 },
  smallIconButton: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm },
  noteContent: { color: palette.inkMuted, fontSize: 12, lineHeight: 19 },
  expandLabel: { marginTop: spacing.sm, color: palette.primaryDark, fontSize: 10, lineHeight: 15, fontWeight: '800' },
  modalRoot: { flex: 1, backgroundColor: palette.canvas },
  modalHeader: { minHeight: 74, paddingHorizontal: spacing.lg, flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1, borderBottomColor: palette.border, backgroundColor: palette.surface },
  modalClose: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center' },
  modalHeading: { flex: 1, alignItems: 'center' },
  modalTitle: { color: palette.ink, fontSize: 16, lineHeight: 22, fontWeight: '900' },
  modalSubtitle: { color: palette.inkSubtle, fontSize: 9, lineHeight: 13 },
  form: { flexGrow: 1, padding: spacing.lg, paddingBottom: spacing.xxl, gap: 18 },
  field: { gap: spacing.sm },
  fieldLabel: { color: palette.ink, fontSize: 12, lineHeight: 17, fontWeight: '800' },
  titleInput: { minHeight: 50, paddingHorizontal: spacing.md, borderWidth: 1, borderColor: palette.borderStrong, borderRadius: radius.md, color: palette.ink, fontSize: 14, backgroundColor: palette.surface },
  counter: { alignSelf: 'flex-end', color: palette.inkSubtle, fontSize: 9 },
  contentInput: { minHeight: 180, padding: spacing.md, borderWidth: 1, borderColor: palette.borderStrong, borderRadius: radius.md, color: palette.ink, fontSize: 14, lineHeight: 21, backgroundColor: palette.surface },
  colorRow: { flexDirection: 'row', gap: spacing.md },
  colorButton: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: 'transparent', borderRadius: radius.md },
  colorButtonActive: { borderColor: palette.ink },
  colorSwatch: { width: 25, height: 25, borderRadius: 6 },
  pinToggle: { minHeight: 62, flexDirection: 'row', alignItems: 'center', gap: spacing.md, padding: spacing.md, borderWidth: 1, borderColor: palette.border, borderRadius: radius.md, backgroundColor: palette.surface },
  checkbox: { width: 26, height: 26, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: palette.borderStrong, borderRadius: radius.sm },
  checkboxActive: { borderColor: palette.primary, backgroundColor: palette.primary },
  pinTitle: { color: palette.ink, fontSize: 12, lineHeight: 17, fontWeight: '800' },
  pinDescription: { marginTop: 2, color: palette.inkSubtle, fontSize: 9, lineHeight: 13 },
});
