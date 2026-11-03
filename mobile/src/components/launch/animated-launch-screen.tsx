import { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Image, StyleSheet, Text, View } from 'react-native';

import { palette } from '@/constants/theme';

type AnimatedLaunchScreenProps = {
  ready: boolean;
  onFinish: () => void;
};

export function AnimatedLaunchScreen({ ready, onFinish }: AnimatedLaunchScreenProps) {
  const [introFinished, setIntroFinished] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);
  const [opacity] = useState(() => new Animated.Value(1));
  const [logoOpacity] = useState(() => new Animated.Value(0));
  const [logoScale] = useState(() => new Animated.Value(0.9));
  const [wordmarkOpacity] = useState(() => new Animated.Value(0));
  const [wordmarkY] = useState(() => new Animated.Value(10));
  const [railScale] = useState(() => new Animated.Value(0));
  const [statusOpacity] = useState(() => new Animated.Value(0));
  const didFinish = useRef(false);

  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion);
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    const fast = reduceMotion ? 1 : undefined;

    const animation = Animated.sequence([
      Animated.parallel([
        Animated.timing(logoOpacity, { toValue: 1, duration: fast ?? 360, useNativeDriver: true }),
        Animated.spring(logoScale, { toValue: 1, damping: 12, stiffness: 120, useNativeDriver: true }),
      ]),
      Animated.parallel([
        Animated.timing(wordmarkOpacity, { toValue: 1, duration: fast ?? 360, useNativeDriver: true }),
        Animated.timing(wordmarkY, { toValue: 0, duration: fast ?? 420, useNativeDriver: true }),
        Animated.timing(railScale, { toValue: 1, duration: fast ?? 520, useNativeDriver: true }),
      ]),
      Animated.timing(statusOpacity, { toValue: 1, duration: fast ?? 320, useNativeDriver: true }),
      Animated.delay(reduceMotion ? 1 : 420),
    ]);

    animation.start(({ finished }) => {
      if (finished) setIntroFinished(true);
    });
    return () => animation.stop();
  }, [logoOpacity, logoScale, railScale, reduceMotion, statusOpacity, wordmarkOpacity, wordmarkY]);

  useEffect(() => {
    if (!ready || !introFinished || didFinish.current) return;
    didFinish.current = true;

    Animated.timing(opacity, {
      toValue: 0,
      duration: reduceMotion ? 100 : 340,
      useNativeDriver: true,
    }).start(() => onFinish());
  }, [introFinished, onFinish, opacity, ready, reduceMotion]);

  return (
    <Animated.View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={[styles.overlay, { opacity }]}>
      <View style={styles.center}>
        <Animated.View style={[styles.logoShell, { opacity: logoOpacity, transform: [{ scale: logoScale }] }]}>
          <Image source={require('@/assets/images/svontai-logo.png')} resizeMode="contain" style={styles.logo} />
        </Animated.View>

        <Animated.View style={[styles.wordmarkWrap, { opacity: wordmarkOpacity, transform: [{ translateY: wordmarkY }] }]}>
          <Text style={styles.wordmark}>SvontAI</Text>
          <Text style={styles.tagline}>İŞLETME OPERASYON MERKEZİ</Text>
        </Animated.View>

        <Animated.View style={[styles.signalRail, { transform: [{ scaleX: railScale }] }]}>
          <View style={styles.signalStrong} />
          <View style={styles.signalCore} />
          <View style={styles.signalStrong} />
        </Animated.View>
      </View>

      <Animated.View style={[styles.status, { opacity: statusOpacity }]}>
        <View style={styles.statusDot} />
        <Text style={styles.statusText}>GÜVENLİ BAĞLANTI HAZIR</Text>
      </Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFill,
    zIndex: 100,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F7F9FC',
  },
  center: { alignItems: 'center', justifyContent: 'center' },
  logoShell: {
    width: 112,
    height: 112,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logo: { width: 112, height: 112 },
  wordmarkWrap: { marginTop: 20, alignItems: 'center', gap: 8 },
  wordmark: { color: palette.navy, fontSize: 34, lineHeight: 40, fontWeight: '900' },
  tagline: { color: palette.primaryDark, fontSize: 11, lineHeight: 16, fontWeight: '800', letterSpacing: 0 },
  signalRail: {
    width: 156,
    height: 2,
    marginTop: 28,
    flexDirection: 'row',
    overflow: 'hidden',
    backgroundColor: palette.border,
  },
  signalStrong: { flex: 1, backgroundColor: palette.primary },
  signalCore: { width: 28, backgroundColor: palette.violet },
  status: {
    position: 'absolute',
    bottom: 54,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  statusDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: palette.success },
  statusText: { color: palette.inkSubtle, fontSize: 10, lineHeight: 14, fontWeight: '800', letterSpacing: 0 },
});
