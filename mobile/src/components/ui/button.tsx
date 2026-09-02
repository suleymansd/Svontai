import type { ComponentProps, ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';

import { palette, radius, spacing } from '@/constants/theme';

type ButtonProps = ComponentProps<typeof Pressable> & {
  label: string;
  loading?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  icon?: ReactNode;
};

export function Button({ label, loading, variant = 'primary', icon, disabled, style, ...props }: ButtonProps) {
  const inactive = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      disabled={inactive}
      style={(state) => [
        styles.base,
        styles[variant],
        inactive && styles.disabled,
        state.pressed && !inactive && styles.pressed,
        typeof style === 'function' ? style(state) : style,
      ]}
      {...props}
    >
      {loading ? <ActivityIndicator color={variant === 'secondary' ? palette.primary : '#FFFFFF'} /> : icon}
      {label ? <Text style={[styles.label, variant === 'secondary' && styles.secondaryLabel]}>{label}</Text> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 50,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    borderWidth: 1,
  },
  primary: { backgroundColor: palette.primary, borderColor: palette.primary },
  secondary: { backgroundColor: palette.surface, borderColor: palette.border },
  danger: { backgroundColor: palette.danger, borderColor: palette.danger },
  label: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
  secondaryLabel: { color: palette.ink },
  disabled: { opacity: 0.55 },
  pressed: { transform: [{ scale: 0.985 }] },
});
