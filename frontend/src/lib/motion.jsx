/* ============================================================================
   Shared motion system for Vivid Space (landing + admin).

   Everything here is purely additive: it animates only `transform` and
   `opacity`, respects prefers-reduced-motion, and — crucially — defaults to
   VISIBLE. If the IntersectionObserver never runs (unsupported, or an element
   never crosses the threshold on mount) the element is shown immediately, so
   nothing can get stuck hidden.

   Layout/structure is never touched: the Reveal / RevealCard components render
   the SAME tag (a <div> by default) as the element they replace, so grid/flex
   parents keep the same direct children — no extra wrapper nesting.
============================================================================ */
import { useEffect, useRef, useState } from 'react';

// Soft, high-end easing used across every reveal.
export const REVEAL_EASE = 'cubic-bezier(0.22, 1, 0.36, 1)';

export const reduceMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------------------------------------------------------------------------
   One reusable IntersectionObserver for the whole app. Elements register a
   one-shot callback that fires the first time they reach ~15% visibility, then
   they're immediately unobserved (reveal once). This is the shared observer the
   design brief asks for — set up lazily, and every consumer cleans up after
   itself on unmount via the returned unregister function.
--------------------------------------------------------------------------- */
const supportsIO = typeof window !== 'undefined' && 'IntersectionObserver' in window;
const callbacks = supportsIO ? new WeakMap() : null;
const sharedIO = supportsIO
  ? new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const cb = callbacks.get(entry.target);
          sharedIO.unobserve(entry.target);
          callbacks.delete(entry.target);
          if (cb) cb();
        });
      },
      { threshold: 0.15 },
    )
  : null;

// Register `el` for a one-shot reveal. Returns an unregister function.
// When there's no observer support (or no element), reveal immediately.
export function observe(el, cb) {
  if (!sharedIO || !el) {
    cb();
    return () => {};
  }
  callbacks.set(el, cb);
  sharedIO.observe(el);
  return () => {
    callbacks.delete(el);
    sharedIO.unobserve(el);
  };
}

/* ---------------------------------------------------------------------------
   useReveal — returns [ref, shown]. `shown` starts false and flips true once
   the element scrolls into view (or right away under reduced motion / no IO).
--------------------------------------------------------------------------- */
export function useReveal() {
  const ref = useRef(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (reduceMotion()) {
      setShown(true);
      return undefined;
    }
    return observe(ref.current, () => setShown(true));
  }, []);
  return [ref, shown];
}

/* ---------------------------------------------------------------------------
   Reveal — drop-in for a plain element you want to fade + rise into view.
   Renders `as` (default 'div') directly, so it can stand in for an existing
   <div>/<p> without changing the DOM shape. Stagger siblings via `delay`.
--------------------------------------------------------------------------- */
export function Reveal({ as: Tag = 'div', delay = 0, style, children, ...rest }) {
  const [ref, shown] = useReveal();
  const reduce = reduceMotion();
  const motion = reduce
    ? null
    : {
        opacity: shown ? 1 : 0,
        transform: shown ? 'translateY(0)' : 'translateY(24px)',
        transition: `opacity 700ms ${REVEAL_EASE} ${delay}ms, transform 700ms ${REVEAL_EASE} ${delay}ms`,
        willChange: shown ? 'auto' : 'transform, opacity',
      };
  return (
    <Tag ref={ref} style={{ ...style, ...motion }} {...rest}>
      {children}
    </Tag>
  );
}

/* ---------------------------------------------------------------------------
   RevealCard — a Reveal that also carries a refined hover micro-interaction.
   Reveal offset and hover lift/scale are composed into a SINGLE transform
   string, so the two never fight (an inline transform would otherwise clobber
   a CSS :hover transform). Gives a gentle lift + scale + shadow bloom.
--------------------------------------------------------------------------- */
export function RevealCard({
  delay = 0,
  lift = 6,
  scale = 1.015,
  hoverShadow = '0 30px 60px -30px rgba(20, 18, 16, 0.28)',
  style,
  children,
  onMouseEnter,
  onMouseLeave,
  ...rest
}) {
  const [ref, shown] = useReveal();
  const [hover, setHover] = useState(false);
  const reduce = reduceMotion();

  const lifted = hover && !reduce;
  const revealY = shown ? 0 : 24;
  const y = revealY - (lifted ? lift : 0);
  const transform = reduce
    ? undefined
    : `translateY(${y}px)${lifted && scale ? ` scale(${scale})` : ''}`;
  const transition = reduce
    ? undefined
    : `opacity 700ms ${REVEAL_EASE} ${shown ? delay : 0}ms, transform ${
        hover ? '220ms ease-out' : `700ms ${REVEAL_EASE} ${shown ? delay : 0}ms`
      }, box-shadow 220ms ease-out`;

  const motion = {
    opacity: reduce ? 1 : shown ? 1 : 0,
    transform,
    transition,
    boxShadow: lifted ? hoverShadow : style?.boxShadow,
    willChange: 'transform, opacity',
  };

  return (
    <div
      ref={ref}
      onMouseEnter={(e) => {
        setHover(true);
        onMouseEnter?.(e);
      }}
      onMouseLeave={(e) => {
        setHover(false);
        onMouseLeave?.(e);
      }}
      style={{ ...style, ...motion }}
      {...rest}
    >
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------------------
   CountUp — ease-out numeric count-up that starts the first time it scrolls
   into view (via the same shared observer), over ~1.6s. Jumps straight to the
   final value under reduced motion. Renders an inline <span> so it can sit
   anywhere a number would.
--------------------------------------------------------------------------- */
export function CountUp({ value, decimals = 0, suffix = '', delay = 0, duration = 1600 }) {
  const ref = useRef(null);
  const [disp, setDisp] = useState(0);
  useEffect(() => {
    let raf;
    const animate = () => {
      if (reduceMotion()) {
        setDisp(value);
        return;
      }
      const startTs = performance.now() + delay;
      const tick = (now) => {
        if (now < startTs) {
          raf = requestAnimationFrame(tick);
          return;
        }
        const p = Math.min(1, (now - startTs) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        setDisp(value * eased);
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };
    const off = observe(ref.current, animate);
    return () => {
      off();
      cancelAnimationFrame(raf);
    };
  }, [value, delay, duration]);
  const num = decimals ? disp.toFixed(decimals) : Math.round(disp).toLocaleString();
  return (
    <span ref={ref} style={{ display: 'inline-block' }}>
      {num}
      {suffix}
    </span>
  );
}
