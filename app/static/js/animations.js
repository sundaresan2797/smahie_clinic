// Reusable, attribute-driven animation engine (GSAP + ScrollTrigger + SplitText).
//
//   data-anim="up" | "fade"          reveal on scroll
//   data-anim="stagger"              reveal [data-anim-child] children in sequence
//   data-anim="lines"                masked line-by-line heading reveal
//   data-anim="mask"                 clip-path image reveal
//   data-anim="rule"                 gold rule grows from the left
//   data-anim="draw"                 SVG .draw-path stroke drawing
//   data-parallax="0.2"              subtle parallax (desktop only)
//   data-magnetic                    cursor-responsive button (fine pointers only)
//
// Reveals animate opacity only (never visibility), so content that has not
// been revealed yet stays focusable and available to screen readers.
//
// Everything runs inside gsap.matchMedia(), so animations are reverted and
// rebuilt cleanly when the viewport or the reduced-motion preference changes.
import { $$ } from './utils.js';

// gsap.matchMedia() only runs the callback while at least one condition
// matches, so desktop + mobile together guarantee it always runs.
export const QUERIES = {
  desktop: '(min-width: 992px)',
  mobile: '(max-width: 991.98px)',
  reduce: '(prefers-reduced-motion: reduce)',
  fine: '(hover: hover) and (pointer: fine)',
};

export function initAnimations() {
  const root = document.documentElement;
  const { gsap, ScrollTrigger, SplitText } = window;
  if (!gsap || !ScrollTrigger) {
    root.classList.remove('motion-ok', 'show-loader');
    return { enabled: false };
  }
  gsap.registerPlugin(ScrollTrigger);
  if (SplitText) gsap.registerPlugin(SplitText);
  root.classList.add('motion-ready');

  if (!root.classList.contains('motion-ok')) {
    return { enabled: false, gsap, ScrollTrigger, SplitText };
  }

  ScrollTrigger.config({ ignoreMobileResize: true });
  const mm = gsap.matchMedia();
  mm.add(QUERIES, (context) => {
    const { desktop, reduce, fine } = context.conditions;
    if (reduce) {
      root.classList.remove('motion-ok');
      return undefined;
    }
    root.classList.add('motion-ok');
    reveals(gsap, desktop);
    staggers(gsap, desktop);
    lines(gsap, SplitText);
    masks(gsap);
    rules(gsap);
    draws(gsap);
    if (desktop) parallax(gsap);
    const cleanupMagnetic = desktop && fine ? magnetic(gsap) : null;
    return () => cleanupMagnetic?.();
  });

  const refresh = () => ScrollTrigger.refresh();
  window.addEventListener('load', refresh, { once: true });
  document.fonts?.ready.then(refresh);
  return { enabled: true, gsap, ScrollTrigger, SplitText, mm };
}

function reveals(gsap, desktop) {
  const y = desktop ? 44 : 26;
  $$('[data-anim="up"]').forEach((el) => {
    gsap.fromTo(el, { opacity: 0, y }, {
      opacity: 1, y: 0, duration: 1.1, ease: 'expo.out',
      scrollTrigger: { trigger: el, start: 'top 90%', once: true },
    });
  });
  $$('[data-anim="fade"]').forEach((el) => {
    gsap.fromTo(el, { opacity: 0 }, {
      opacity: 1, duration: 1.2, ease: 'power2.out',
      scrollTrigger: { trigger: el, start: 'top 92%', once: true },
    });
  });
}

function staggers(gsap, desktop) {
  const y = desktop ? 48 : 28;
  $$('[data-anim="stagger"]').forEach((group) => {
    const children = $$('[data-anim-child]', group).filter((c) => c.closest('[data-anim="stagger"]') === group);
    if (!children.length) return;
    gsap.fromTo(children, { opacity: 0, y }, {
      opacity: 1, y: 0, duration: 1.1, stagger: 0.09, ease: 'expo.out',
      scrollTrigger: { trigger: group, start: 'top 88%', once: true },
    });
  });
  // Safety net: a child outside any stagger group must never stay hidden.
  $$('[data-anim-child]').filter((c) => !c.closest('[data-anim="stagger"]')).forEach((el) => {
    gsap.set(el, { opacity: 1 });
  });
}

function lines(gsap, SplitText) {
  $$('[data-anim="lines"]').forEach((el) => {
    if (!SplitText) {
      gsap.set(el, { autoAlpha: 1 });
      return;
    }
    SplitText.create(el, {
      type: 'lines',
      mask: 'lines',
      linesClass: 'split-line',
      autoSplit: true,
      onSplit(self) {
        gsap.set(el, { autoAlpha: 1 });
        return gsap.from(self.lines, {
          yPercent: 110, duration: 1.2, stagger: 0.1, ease: 'expo.out',
          scrollTrigger: { trigger: el, start: 'top 88%', once: true },
        });
      },
    });
  });
}

function masks(gsap) {
  $$('[data-anim="mask"]').forEach((el) => {
    const img = el.querySelector('img');
    const tl = gsap.timeline({ scrollTrigger: { trigger: el, start: 'top 85%', once: true } });
    tl.fromTo(el, { clipPath: 'inset(100% 0% 0% 0%)' }, { clipPath: 'inset(0% 0% 0% 0%)', duration: 1.5, ease: 'expo.inOut' });
    if (img) tl.fromTo(img, { scale: 1.28 }, { scale: 1, duration: 2.1, ease: 'expo.out' }, 0);
  });
}

function rules(gsap) {
  $$('[data-anim="rule"]').forEach((el) => {
    gsap.fromTo(el, { scaleX: 0 }, {
      scaleX: 1, duration: 1.4, ease: 'expo.inOut',
      scrollTrigger: { trigger: el, start: 'top 92%', once: true },
    });
  });
}

function draws(gsap) {
  $$('[data-anim="draw"]').forEach((svg) => {
    const paths = $$('.draw-path', svg);
    paths.forEach((p) => {
      const length = Math.ceil(p.getTotalLength()) + 1;
      gsap.set(p, { strokeDasharray: length, strokeDashoffset: length });
    });
    gsap.to(paths, {
      strokeDashoffset: 0, duration: 1.8, ease: 'power2.inOut', stagger: 0.15,
      scrollTrigger: { trigger: svg, start: 'top 90%', once: true },
    });
  });
}

function parallax(gsap) {
  $$('[data-parallax]').forEach((el) => {
    const amount = parseFloat(el.dataset.parallax) || 0.15;
    gsap.fromTo(el, { yPercent: -amount * 50 }, {
      yPercent: amount * 50, ease: 'none',
      scrollTrigger: { trigger: el.closest('section') || el, start: 'top bottom', end: 'bottom top', scrub: true },
    });
  });
}

function magnetic(gsap) {
  const cleanups = $$('[data-magnetic]').map((el) => {
    const xTo = gsap.quickTo(el, 'x', { duration: 0.6, ease: 'power3.out' });
    const yTo = gsap.quickTo(el, 'y', { duration: 0.6, ease: 'power3.out' });
    const move = (event) => {
      const r = el.getBoundingClientRect();
      xTo((event.clientX - (r.left + r.width / 2)) * 0.16);
      yTo((event.clientY - (r.top + r.height / 2)) * 0.26);
    };
    const leave = () => { xTo(0); yTo(0); };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', leave);
    return () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerleave', leave);
      gsap.set(el, { x: 0, y: 0 });
    };
  });
  return () => cleanups.forEach((fn) => fn());
}
