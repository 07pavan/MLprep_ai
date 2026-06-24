import { Dimensions, Platform } from 'react-native'

const { width: SCREEN_W, height: SCREEN_H } = Dimensions.get('window')

// ── Color Palette ─────────────────────────────────────────────────────────────
export const COLORS = {
  // Backgrounds
  bg00: '#05070F',       // deepest bg
  bg01: '#090C18',       // primary bg
  bg02: '#0D1124',       // surface
  bg03: '#121729',       // elevated surface
  bg04: '#1A2038',       // card

  // Brand / Accent
  indigo:      '#6366F1',
  indigoLight: '#818CF8',
  indigoDark:  '#4F52C8',
  violet:      '#8B5CF6',
  blue:        '#3B82F6',
  blueLight:   '#60A5FA',
  cyan:        '#06B6D4',

  // Semantic
  success:  '#10B981',
  warning:  '#F59E0B',
  error:    '#EF4444',
  info:     '#3B82F6',

  // Text
  text100: '#F8FAFC',   // primary
  text200: '#CBD5E1',   // secondary
  text300: '#94A3B8',   // tertiary
  text400: '#64748B',   // muted/placeholder
  text500: '#475569',   // disabled

  // Borders
  border:       'rgba(255,255,255,0.06)',
  borderMid:    'rgba(255,255,255,0.10)',
  borderAccent: 'rgba(99,102,241,0.35)',

  // Overlays / Glass
  glass:        'rgba(13,17,36,0.75)',
  glassBorder:  'rgba(255,255,255,0.08)',
  indigoGlass:  'rgba(99,102,241,0.08)',

  white: '#FFFFFF',
  black: '#000000',
}

// ── Gradients (arrays for LinearGradient) ─────────────────────────────────────
export const GRADIENTS = {
  brand:       ['#6366F1', '#8B5CF6'],
  brandWarm:   ['#6366F1', '#3B82F6'],
  hero:        ['#0D1124', '#121729'],
  surface:     ['#0F1325', '#141B2D'],
  indigo:      ['rgba(99,102,241,0.18)', 'rgba(99,102,241,0.04)'],
  success:     ['rgba(16,185,129,0.16)', 'rgba(16,185,129,0.04)'],
  warning:     ['rgba(245,158,11,0.16)', 'rgba(245,158,11,0.04)'],
  error:       ['rgba(239,68,68,0.16)', 'rgba(239,68,68,0.04)'],
  dark:        ['#090C18', '#05070F'],
}

// ── Typography ─────────────────────────────────────────────────────────────────
export const FONT = {
  // weights mapped to system (Inter loaded via @expo-google-fonts)
  regular:  '400',
  medium:   '500',
  semibold: '600',
  bold:     '700',
  extrabold:'800',

  size: {
    xs:   10,
    sm:   12,
    base: 14,
    md:   15,
    lg:   17,
    xl:   20,
    xxl:  24,
    xxxl: 30,
    hero: 36,
  },
  lineHeight: {
    tight:   1.25,
    normal:  1.5,
    relaxed: 1.75,
  },
}

// ── Spacing ────────────────────────────────────────────────────────────────────
export const SPACE = {
  xs:  4,
  sm:  8,
  md:  12,
  lg:  16,
  xl:  20,
  xxl: 24,
  xxxl:32,
  huge:48,
}

// ── Radii ──────────────────────────────────────────────────────────────────────
export const RADIUS = {
  sm:   6,
  md:   10,
  lg:   14,
  xl:   18,
  xxl:  24,
  pill: 999,
}

// ── Shadows ────────────────────────────────────────────────────────────────────
export const SHADOW = {
  indigo: {
    shadowColor: COLORS.indigo,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 16,
    elevation: 8,
  },
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 5,
  },
  glow: {
    shadowColor: COLORS.indigo,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 10,
  },
}

// ── Layout Helpers ─────────────────────────────────────────────────────────────
export const SCREEN = {
  width:  SCREEN_W,
  height: SCREEN_H,
}

export const NAV_HEIGHT  = Platform.OS === 'ios' ? 80 : 64
export const HEADER_HEIGHT = 56
