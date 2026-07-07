// Central design tokens, ported from the Vivid Space .dc.html design system.
export const C = {
  cream: '#FBFAF7',
  paper: '#F3F1EC',
  ink: '#16171B',
  inkDeep: '#0E0F12',
  inkPanel: '#141519',
  text: '#1B1C20',
  muted: '#54555c',
  muted2: '#6B6B73',
  faint: '#9a9aa0',
  line: 'rgba(20,23,27,.08)',
  lineStrong: 'rgba(20,23,27,.14)',
  pink: '#C0379A',
  blue: '#2E73E0',
  purple: '#6B3DAE',
  red: '#E23A4B',
  orange: '#F0822E',
  teal: '#1FB9A6',
};

export const RAINBOW = 'linear-gradient(100deg,#2E73E0,#6B3DAE,#C0379A,#E23A4B,#F0822E,#C6CB3A,#1FB9A6)';
export const FONT_HEAD = "'Space Grotesk',sans-serif";
export const FONT_BODY = "'Manrope',sans-serif";

// Primary rainbow CTA button style
export const gradientBtn = {
  fontFamily: FONT_HEAD,
  fontWeight: 600,
  color: '#fff',
  border: 0,
  borderRadius: 13,
  cursor: 'pointer',
  background: RAINBOW,
  backgroundSize: '200% auto',
  boxShadow: '0 12px 30px -12px rgba(192,55,154,.55)',
  transition: 'background-position .6s, transform .2s',
};

// Map booking space keys -> presentation + rules (mirrors the design + backend spec)
export const SPACE_META = {
  meeting: { name: 'Meeting Room', icon: 'presentation', iconColor: C.blue, durations: ['hourly', 'fullday'] },
  office: { name: 'Day Office', icon: 'door-closed', iconColor: C.pink, durations: ['hourly', 'fullday'] },
  cowork: { name: 'Coworking', icon: 'users', iconColor: C.orange, durations: ['fullday'] },
  lounge: { name: 'Lounge', icon: 'armchair', iconColor: C.teal, durations: ['fullday'] },
};
