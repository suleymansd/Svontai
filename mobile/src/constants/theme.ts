import { Platform } from 'react-native';

export const palette = {
  ink: '#17202F',
  inkMuted: '#667085',
  inkSubtle: '#98A2B3',
  canvas: '#F4F6F8',
  surface: '#FFFFFF',
  surfaceMuted: '#EEF1F5',
  surfaceRaised: '#F9FAFB',
  border: '#E2E7ED',
  borderStrong: '#D2D9E2',
  primary: '#08A4BD',
  primaryDark: '#087C91',
  primarySoft: '#E7F8FA',
  violet: '#7357E8',
  violetSoft: '#F0EDFC',
  success: '#168B63',
  successSoft: '#E7F7F0',
  warning: '#B96A00',
  warningSoft: '#FFF2D8',
  danger: '#CF3F4C',
  dangerSoft: '#FDECEF',
  coral: '#E8675A',
  coralSoft: '#FFF0EE',
  navy: '#0B1220',
  navySoft: '#182235',
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
  sm: 5,
  md: 8,
  lg: 8,
  pill: 999,
} as const;

export const shadow = Platform.select({
  web: { boxShadow: '0 8px 24px rgba(11, 18, 32, 0.08)' },
  default: {
    shadowColor: '#0B1220',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.07,
    shadowRadius: 18,
    elevation: 2,
  },
});

export const shadowSoft = Platform.select({
  web: { boxShadow: '0 2px 10px rgba(11, 18, 32, 0.05)' },
  default: {
    shadowColor: '#0B1220',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.05,
    shadowRadius: 9,
    elevation: 1,
  },
});
