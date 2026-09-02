import type { PropsWithChildren } from 'react';
import { StyleSheet, View, ViewProps } from 'react-native';

import { palette, radius, shadow, spacing } from '@/constants/theme';

export function Card({ children, style, ...props }: PropsWithChildren<ViewProps>) {
  return (
    <View style={[styles.card, style]} {...props}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: palette.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: palette.border,
    padding: spacing.lg,
    ...shadow,
  },
});
