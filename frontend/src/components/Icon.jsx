import { icons } from 'lucide-react';

// Convert a kebab-case lucide name (as used in the .dc.html designs) to the
// PascalCase component key exported by lucide-react. e.g. "arrow-right" -> "ArrowRight".
function toPascal(name) {
  return name
    .split('-')
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join('');
}

/**
 * Thin wrapper around lucide-react so we can keep the design's kebab icon names.
 * Usage: <Icon name="arrow-right" size={18} />
 */
export default function Icon({ name, size = 18, color = 'currentColor', strokeWidth = 2, style, ...rest }) {
  const Cmp = icons[toPascal(name)];
  if (!Cmp) return null;
  return <Cmp size={size} color={color} strokeWidth={strokeWidth} style={style} {...rest} />;
}
