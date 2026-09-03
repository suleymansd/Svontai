import {
  Bot,
  CalendarCheck2,
  Check,
  ChevronRight,
  Clock3,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
} from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { ComponentType, useMemo, useRef, useState } from 'react';
import {
  Animated,
  FlatList,
  ListRenderItemInfo,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Brand } from '@/components/ui/brand';
import { palette, radius, shadow, spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth/auth-context';
import { useFirstRun } from '@/lib/onboarding/first-run-context';

type IconComponent = ComponentType<{ color?: string; size?: number; strokeWidth?: number }>;

type Slide = {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  icon: IconComponent;
  visual: 'conversations' | 'knowledge' | 'appointments';
};

const slides: Slide[] = [
  {
    id: 'conversations',
    eyebrow: 'KESİNTİSİZ İLETİŞİM',
    title: 'Her konuşma kontrolünüzde',
    description: 'Gelen talepleri, AI yanıtlarını ve müdahale gerektiren görüşmeleri tek akışta izleyin.',
    icon: MessageSquareText,
    visual: 'conversations',
  },
  {
    id: 'knowledge',
    eyebrow: 'İŞLETMENİZİ TANIYAN AI',
    title: 'Bilginizle çalışan bir asistan',
    description: 'SvontAI hizmetlerinizi, çalışma kurallarınızı ve medyanızı kullanarak tutarlı yanıtlar üretir.',
    icon: Bot,
    visual: 'knowledge',
  },
  {
    id: 'appointments',
    eyebrow: 'UÇTAN UCA OTOMASYON',
    title: 'Randevudan sonuca, otomatik',
    description: 'Uygunluğu kontrol eder, müşteri onayını alır ve randevuyu işletme takviminize kaydeder.',
    icon: CalendarCheck2,
    visual: 'appointments',
  },
];

function ConversationVisual() {
  return (
    <View style={styles.visualCard}>
      <View style={styles.visualTopRow}>
        <View>
          <Text style={styles.visualLabel}>Canlı görüşme</Text>
          <Text style={styles.visualMeta}>WhatsApp operasyonu</Text>
        </View>
        <View style={styles.liveBadge}>
          <View style={styles.liveDot} />
          <Text style={styles.liveText}>Aktif</Text>
        </View>
      </View>
      <View style={styles.messageIncoming}>
        <Text style={styles.messageText}>Yarın öğleden sonra uygun musunuz?</Text>
        <Text style={styles.messageTime}>14:21</Text>
      </View>
      <View style={styles.messageOutgoing}>
        <View style={styles.aiRow}>
          <Sparkles size={13} color={palette.violet} />
          <Text style={styles.aiLabel}>SvontAI yanıtladı</Text>
        </View>
        <Text style={styles.messageText}>14.00 ve 15.30 saatleri uygun. Hangisini ayıralım?</Text>
        <Text style={styles.messageTime}>14:21</Text>
      </View>
      <View style={styles.resolutionRow}>
        <Check size={15} color={palette.success} strokeWidth={3} />
        <Text style={styles.resolutionText}>Talep anlaşıldı ve takipte</Text>
      </View>
    </View>
  );
}

function KnowledgeVisual() {
  return (
    <View style={styles.visualCard}>
      <View style={styles.knowledgeCore}>
        <View style={styles.coreIcon}>
          <Bot size={28} color={palette.surface} strokeWidth={2.2} />
        </View>
        <View>
          <Text style={styles.visualLabel}>İşletme hafızası</Text>
          <Text style={styles.visualMeta}>Her yanıtta güncel bağlam</Text>
        </View>
      </View>
      <View style={styles.knowledgeGrid}>
        <KnowledgeItem label="Hizmetler" value="12 bilgi" icon={Sparkles} tone="violet" />
        <KnowledgeItem label="Kurallar" value="Güncel" icon={ShieldCheck} tone="teal" />
        <KnowledgeItem label="Çalışma saatleri" value="Tanımlı" icon={Clock3} tone="navy" />
      </View>
      <View style={styles.contextBar}>
        <View style={styles.contextFill} />
      </View>
      <Text style={styles.contextText}>Yanıt bağlamı hazır</Text>
    </View>
  );
}

function KnowledgeItem({ label, value, icon: Icon, tone }: { label: string; value: string; icon: IconComponent; tone: 'violet' | 'teal' | 'navy' }) {
  const colors = {
    violet: { background: palette.violetSoft, foreground: palette.violet },
    teal: { background: palette.primarySoft, foreground: palette.primaryDark },
    navy: { background: palette.surfaceMuted, foreground: palette.navy },
  }[tone];

  return (
    <View style={styles.knowledgeItem}>
      <View style={[styles.knowledgeIcon, { backgroundColor: colors.background }]}>
        <Icon size={17} color={colors.foreground} />
      </View>
      <Text style={styles.knowledgeLabel}>{label}</Text>
      <Text style={styles.knowledgeValue}>{value}</Text>
    </View>
  );
}

function AppointmentVisual() {
  return (
    <View style={styles.visualCard}>
      <View style={styles.visualTopRow}>
        <View>
          <Text style={styles.visualLabel}>Randevu akışı</Text>
          <Text style={styles.visualMeta}>Bugün, İstanbul</Text>
        </View>
        <CalendarCheck2 size={25} color={palette.primaryDark} />
      </View>
      <View style={styles.timeline}>
        <TimelineItem title="Talep anlaşıldı" detail="Saç bakımı" done />
        <TimelineItem title="Uygunluk kontrol edildi" detail="14.00 boş" done />
        <TimelineItem title="Müşteri onayı alındı" detail="Onaylandı" done />
      </View>
      <View style={styles.calendarResult}>
        <View style={styles.calendarDate}>
          <Text style={styles.calendarDay}>24</Text>
          <Text style={styles.calendarMonth}>EYL</Text>
        </View>
        <View style={styles.calendarCopy}>
          <Text style={styles.calendarTitle}>Randevu takvime işlendi</Text>
          <Text style={styles.calendarMeta}>14.00 · 45 dakika</Text>
        </View>
        <Check size={18} color={palette.success} strokeWidth={3} />
      </View>
    </View>
  );
}

function TimelineItem({ title, detail, done }: { title: string; detail: string; done?: boolean }) {
  return (
    <View style={styles.timelineItem}>
      <View style={[styles.timelineCheck, done && styles.timelineCheckDone]}>
        {done && <Check size={12} color={palette.surface} strokeWidth={3} />}
      </View>
      <View style={styles.timelineCopy}>
        <Text style={styles.timelineTitle}>{title}</Text>
        <Text style={styles.timelineDetail}>{detail}</Text>
      </View>
    </View>
  );
}

function SlideVisual({ type }: { type: Slide['visual'] }) {
  if (type === 'conversations') return <ConversationVisual />;
  if (type === 'knowledge') return <KnowledgeVisual />;
  return <AppointmentVisual />;
}

export default function OnboardingScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { status: authStatus } = useAuth();
  const { completeOnboarding } = useFirstRun();
  const listRef = useRef<FlatList<Slide>>(null);
  const [scrollX] = useState(() => new Animated.Value(0));
  const [activeIndex, setActiveIndex] = useState(0);
  const [saving, setSaving] = useState(false);
  const pageWidth = Math.max(width, 320);
  const isLast = activeIndex === slides.length - 1;

  const finish = async () => {
    if (saving) return;
    setSaving(true);
    try {
      await completeOnboarding();
      if (authStatus === 'authenticated') router.replace('/(tabs)');
      else router.replace('/(auth)/login');
    } finally {
      setSaving(false);
    }
  };

  const next = () => {
    if (isLast) {
      void finish();
      return;
    }
    listRef.current?.scrollToIndex({ index: activeIndex + 1, animated: true });
  };

  const renderItem = ({ item, index }: ListRenderItemInfo<Slide>) => {
    const inputRange = [(index - 1) * pageWidth, index * pageWidth, (index + 1) * pageWidth];
    const contentOpacity = scrollX.interpolate({ inputRange, outputRange: [0.2, 1, 0.2], extrapolate: 'clamp' });
    const contentY = scrollX.interpolate({ inputRange, outputRange: [18, 0, 18], extrapolate: 'clamp' });
    const visualScale = scrollX.interpolate({ inputRange, outputRange: [0.94, 1, 0.94], extrapolate: 'clamp' });
    const Icon = item.icon;

    return (
      <View style={[styles.slide, { width: pageWidth }]}>
        <Animated.View style={[styles.slideInner, { opacity: contentOpacity, transform: [{ translateY: contentY }] }]}>
          <Animated.View style={[styles.visualStage, { transform: [{ scale: visualScale }] }]}>
            <View style={styles.featureIcon}>
              <Icon size={23} color={palette.surface} strokeWidth={2.2} />
            </View>
            <SlideVisual type={item.visual} />
          </Animated.View>
          <View style={styles.copyBlock}>
            <Text style={styles.eyebrow}>{item.eyebrow}</Text>
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.description}>{item.description}</Text>
          </View>
        </Animated.View>
      </View>
    );
  };

  const progress = useMemo(
    () => slides.map((slide, index) => <View key={slide.id} style={[styles.progressSegment, index <= activeIndex && styles.progressSegmentActive]} />),
    [activeIndex],
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <Brand compact />
        <Pressable accessibilityRole="button" accessibilityLabel="Tanıtımı geç" hitSlop={12} onPress={() => void finish()}>
          <Text style={styles.skip}>Geç</Text>
        </Pressable>
      </View>

      <View style={styles.progress}>{progress}</View>

      <Animated.FlatList
        ref={listRef}
        data={slides}
        horizontal
        pagingEnabled
        bounces={false}
        showsHorizontalScrollIndicator={false}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        onScroll={Animated.event([{ nativeEvent: { contentOffset: { x: scrollX } } }], { useNativeDriver: true })}
        onMomentumScrollEnd={(event) => setActiveIndex(Math.round(event.nativeEvent.contentOffset.x / pageWidth))}
        scrollEventThrottle={16}
        getItemLayout={(_, index) => ({ length: pageWidth, offset: pageWidth * index, index })}
      />

      <View style={styles.footer}>
        <Text style={styles.stepText}>{activeIndex + 1} / {slides.length}</Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isLast ? 'SvontAI kullanmaya başla' : 'Sonraki tanıtım sayfası'}
          disabled={saving}
          onPress={next}
          style={({ pressed }) => [styles.nextButton, pressed && styles.nextButtonPressed, saving && styles.nextButtonDisabled]}
        >
          <Text style={styles.nextButtonText}>{isLast ? 'Kullanmaya başla' : 'Devam et'}</Text>
          <ChevronRight size={20} color={palette.surface} strokeWidth={2.5} />
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: palette.canvas },
  header: {
    minHeight: 56,
    paddingHorizontal: spacing.xl,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  skip: { color: palette.inkMuted, fontSize: 14, lineHeight: 20, fontWeight: '700' },
  progress: { height: 3, marginHorizontal: spacing.xl, flexDirection: 'row', gap: 6 },
  progressSegment: { flex: 1, borderRadius: 2, backgroundColor: palette.border },
  progressSegmentActive: { backgroundColor: palette.primary },
  slide: { flex: 1 },
  slideInner: { flex: 1, paddingHorizontal: spacing.xl, justifyContent: 'center', gap: spacing.xxl },
  visualStage: {
    width: '100%',
    maxWidth: 520,
    minHeight: 294,
    alignSelf: 'center',
    justifyContent: 'center',
  },
  featureIcon: {
    position: 'absolute',
    zIndex: 2,
    top: 0,
    left: 18,
    width: 46,
    height: 46,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: palette.navy,
    ...shadow,
  },
  visualCard: {
    minHeight: 256,
    marginTop: 24,
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: palette.surface,
    ...shadow,
  },
  visualTopRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.lg },
  visualLabel: { color: palette.ink, fontSize: 14, lineHeight: 20, fontWeight: '800' },
  visualMeta: { marginTop: 2, color: palette.inkSubtle, fontSize: 11, lineHeight: 15 },
  liveBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: radius.pill, backgroundColor: palette.successSoft, paddingHorizontal: 10, paddingVertical: 6 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: palette.success },
  liveText: { color: palette.success, fontSize: 11, fontWeight: '800' },
  messageIncoming: { maxWidth: '79%', padding: spacing.md, borderRadius: radius.md, backgroundColor: palette.surfaceMuted, gap: 5 },
  messageOutgoing: { maxWidth: '88%', alignSelf: 'flex-end', marginTop: spacing.md, padding: spacing.md, borderRadius: radius.md, backgroundColor: palette.violetSoft, gap: 5 },
  messageText: { color: palette.ink, fontSize: 12, lineHeight: 17, fontWeight: '600' },
  messageTime: { alignSelf: 'flex-end', color: palette.inkSubtle, fontSize: 9 },
  aiRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  aiLabel: { color: palette.violet, fontSize: 9, lineHeight: 13, fontWeight: '800' },
  resolutionRow: { marginTop: spacing.lg, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  resolutionText: { color: palette.success, fontSize: 11, lineHeight: 16, fontWeight: '700' },
  knowledgeCore: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginBottom: spacing.lg },
  coreIcon: { width: 48, height: 48, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: palette.violet },
  knowledgeGrid: { flexDirection: 'row', gap: spacing.sm },
  knowledgeItem: { flex: 1, minHeight: 118, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.canvas },
  knowledgeIcon: { width: 32, height: 32, borderRadius: radius.sm, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.sm },
  knowledgeLabel: { minHeight: 30, color: palette.inkMuted, fontSize: 10, lineHeight: 14, fontWeight: '700' },
  knowledgeValue: { marginTop: 4, color: palette.ink, fontSize: 11, lineHeight: 15, fontWeight: '800' },
  contextBar: { height: 4, overflow: 'hidden', marginTop: spacing.lg, borderRadius: 2, backgroundColor: palette.surfaceMuted },
  contextFill: { width: '86%', height: '100%', backgroundColor: palette.primary },
  contextText: { marginTop: spacing.sm, color: palette.primaryDark, fontSize: 10, lineHeight: 14, fontWeight: '800' },
  timeline: { gap: spacing.md },
  timelineItem: { minHeight: 34, flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  timelineCheck: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: palette.border },
  timelineCheckDone: { borderColor: palette.success, backgroundColor: palette.success },
  timelineCopy: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  timelineTitle: { flex: 1, color: palette.ink, fontSize: 11, lineHeight: 16, fontWeight: '700' },
  timelineDetail: { color: palette.inkMuted, fontSize: 10, lineHeight: 15, fontWeight: '600' },
  calendarResult: { marginTop: spacing.lg, padding: spacing.md, flexDirection: 'row', alignItems: 'center', gap: spacing.md, borderRadius: radius.md, backgroundColor: palette.successSoft },
  calendarDate: { width: 38, alignItems: 'center', justifyContent: 'center' },
  calendarDay: { color: palette.success, fontSize: 18, lineHeight: 20, fontWeight: '900' },
  calendarMonth: { color: palette.success, fontSize: 8, lineHeight: 11, fontWeight: '800' },
  calendarCopy: { flex: 1 },
  calendarTitle: { color: palette.ink, fontSize: 11, lineHeight: 16, fontWeight: '800' },
  calendarMeta: { marginTop: 2, color: palette.inkMuted, fontSize: 9, lineHeight: 13 },
  copyBlock: { width: '100%', maxWidth: 520, alignSelf: 'center', alignItems: 'center', gap: spacing.md },
  eyebrow: { color: palette.primaryDark, fontSize: 11, lineHeight: 16, fontWeight: '900', letterSpacing: 0 },
  title: { color: palette.navy, fontSize: 29, lineHeight: 35, fontWeight: '900', textAlign: 'center' },
  description: { maxWidth: 430, color: palette.inkMuted, fontSize: 15, lineHeight: 23, textAlign: 'center' },
  footer: { minHeight: 84, paddingHorizontal: spacing.xl, paddingBottom: spacing.md, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.lg },
  stepText: { minWidth: 36, color: palette.inkSubtle, fontSize: 12, lineHeight: 18, fontWeight: '800', fontVariant: ['tabular-nums'] },
  nextButton: { minWidth: 154, minHeight: 52, paddingHorizontal: spacing.lg, borderRadius: radius.md, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm, backgroundColor: palette.navy },
  nextButtonPressed: { opacity: 0.86, transform: [{ scale: 0.98 }] },
  nextButtonDisabled: { opacity: 0.55 },
  nextButtonText: { color: palette.surface, fontSize: 14, lineHeight: 20, fontWeight: '800' },
});
