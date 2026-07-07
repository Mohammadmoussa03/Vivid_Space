// Shared Mindspace design tokens + small helpers used by Landing and Admin.
import { useEffect, useState } from 'react';

export const MS = {
  bg: '#F5F1ED',
  bg2: '#EDE8E2',
  card: '#ffffff',
  panel: '#FAF8F3',
  ink: '#1A1A1A',
  muted: '#6B6560',
  faint: '#8A857E',
  line: '#E5E3E6',
  line2: '#F0ECE6',
  accent: '#9B7EBD',
  accent2: '#C9A6E0',
  green: '#3B7554',
  amber: '#8A6D22',
  red: '#A0503F',
  serif: "'Playfair Display', serif",
  sans: "'Inter', system-ui, sans-serif",
};

// Soft status/badge tones (bg + text color) used across tables and pills.
export const TONES = {
  green: { bg: 'rgba(63,122,90,0.14)', color: '#3B7554' },
  amber: { bg: 'rgba(168,137,74,0.16)', color: '#8A6D22' },
  red: { bg: 'rgba(168,90,74,0.14)', color: '#A0503F' },
  neutral: { bg: 'rgba(107,101,96,0.14)', color: '#5A554F' },
  lilac: { bg: 'rgba(155,126,189,0.16)', color: '#7A5E9A' },
};

export function useVW() {
  const [vw, setVw] = useState(typeof window !== 'undefined' ? window.innerWidth : 1280);
  useEffect(() => {
    let t;
    const r = () => { if (t) return; t = requestAnimationFrame(() => { t = null; setVw(window.innerWidth); }); };
    window.addEventListener('resize', r);
    return () => window.removeEventListener('resize', r);
  }, []);
  return vw;
}

// Build a month grid for the booking calendar.
export function buildCalendar(monthOffset, selectedIso) {
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const base = new Date(now.getFullYear(), now.getMonth() + monthOffset, 1);
  const y = base.getFullYear(), m = base.getMonth();
  const startDow = new Date(y, m, 1).getDay();
  const dim = new Date(y, m + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startDow; i++) cells.push({ empty: true });
  for (let d = 1; d <= dim; d++) {
    const dt = new Date(y, m, d);
    const iso = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    cells.push({ day: d, iso, past: dt < now, sel: selectedIso === iso });
  }
  while (cells.length % 7) cells.push({ empty: true });
  return { cells, label: base.toLocaleString('en-US', { month: 'long', year: 'numeric' }) };
}

export const fmtDate = (iso) => {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
};

export const todayIso = () => {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
};

// Resolve an API image reference (absolute URL or /media path) to something <img> can load.
export const imgUrl = (v) => (!v ? '' : (/^https?:\/\//.test(v) ? v : v));

// Guard against javascript:/data: URLs in href/iframe sinks (defense-in-depth
// alongside server-side validation). Returns undefined for anything that isn't
// an http(s) URL or a site-relative /path, so React drops the attribute.
export const safeUrl = (v) => {
  if (typeof v !== 'string') return undefined;
  const t = v.trim();
  return /^(https?:\/\/|\/)/i.test(t) ? t : undefined;
};

// Extract a human-readable error message from an axios error.
export const apiError = (e, fallback = 'Something went wrong. Please try again.') => {
  const d = e?.response?.data;
  if (!d) return fallback;
  if (typeof d === 'string') return d;
  if (d.detail) return d.detail;
  const first = Object.values(d)[0];
  if (Array.isArray(first)) return first[0];
  if (typeof first === 'string') return first;
  return fallback;
};
