import mark from '../assets/brand/vivid-mark.png';
import { FONT_HEAD } from '../lib/theme';

/**
 * The Vivid Space logo lockup: mark + "VividSpace" wordmark.
 * `tone` controls text color for light vs dark backgrounds.
 */
export default function Brand({ height = 36, fontSize = 21, tone = 'dark', sub }) {
  const isDark = tone === 'dark'; // dark text (on light bg)
  const main = isDark ? '#16171B' : '#fff';
  const soft = isDark ? '#54555c' : 'rgba(255,255,255,.6)';
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 11, flexShrink: 0 }}>
      <img src={mark} alt="Vivid Space" style={{ height, width: 'auto', display: 'block' }} />
      <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
        <span style={{ fontFamily: FONT_HEAD, fontWeight: 700, fontSize, letterSpacing: '-.02em', color: main }}>
          Vivid<span style={{ fontWeight: 400, color: soft }}>Space</span>
        </span>
        {sub && (
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,.45)', fontWeight: 600, letterSpacing: '.04em', marginTop: 2 }}>{sub}</span>
        )}
      </span>
    </span>
  );
}
