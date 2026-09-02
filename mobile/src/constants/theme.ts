import { Platform } from 'react-native';

export const palette = {
  ink: '#111827',
  inkMuted: '#667085',
  inkSubtle: '#98A2B3',
  canvas: '#F5F7FA',
  surface: '#FFFFFF',
  surfaceMuted: '#EEF2F6',
  border: '#E1E7EF',
  primary: '#119DB4',
  primaryDark: '#08798C',
  primarySoft: '#E8F8FA',
  violet: '#7656F6',
  violetSoft: '#F0EDFF',
  success: '#168B63',
  successSoft: '#E7F7F0',
  warning: '#C77700',
  warningSoft: '#FFF4DE',
  danger: '#D93F4B',
  dangerSoft: '#FDECEE',
  navy: '#101828',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 6,
  md: 8,
  lg: 12,
  pill: 999,
} as const;

export const shadow = Platform.select({
  web: { boxShadow: '0 4px 12px rgba(16, 24, 40, 0.08)' },
  default: {
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 3,
  },
});
