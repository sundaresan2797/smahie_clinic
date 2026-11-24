// Lenis smooth scrolling synced with GSAP ScrollTrigger, plus accessible
// in-page anchor scrolling. Lenis is skipped for touch devices and for
// visitors who prefer reduced motion, so native scrolling is kept there.
import { mq, prefersReducedMotion } from './utils.js';

export function initSmoothScroll(motion) {
  if (!window.Lenis || prefersReducedMotion() || mq('(pointer: coarse)').matches) return null;

  const lenis = new window.Lenis({
    lerp: 0.1,
    smoothWheel: true,
    syncTouch: false,
    wheelMultiplier: 0.95,
    // Never hijack scrolling inside dialogs, menus or marked regions.
    prevent: (node) => Boolean(node.closest?.('.modal, .offcanvas, .dropdown-menu, [data-lenis-prevent]')),
  });

  if (motion?.gsap && motion?.ScrollTrigger) {
    lenis.on('scroll', motion.ScrollTrigger.update);
    motion.gsap.ticker.add((time) => lenis.raf(time * 1000));
    motion.gsap.ticker.lagSmoothing(0);
  } else {
    const raf = (time) => { lenis.raf(time); requestAnimationFrame(raf); };
    requestAnimationFrame(raf);
  }
  return lenis;
}

function headerOffset() {
  const value = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop);
  return Number.isFinite(value) ? value : 100;
}

function focusTarget(target) {
  const focusable = /^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(target.tagName);
  if (!focusable && !target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
}

export function initAnchors(lenis) {
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href^="#"]');
    if (!link || link.hasAttribute('data-bs-toggle') || event.defaultPrevented) return;
    const hash = link.getAttribute('href');
    if (hash.length < 2) return;
    const target = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!target) return;
    event.preventDefault();

    const isSkip = link.classList.contains('skip-link');
    const offset = isSkip ? 0 : -headerOffset();
    if (lenis) {
      lenis.scrollTo(target, { offset, immediate: isSkip, duration: 1.3, onComplete: () => focusTarget(target) });
      if (isSkip) focusTarget(target);
    } else {
      const top = target.getBoundingClientRect().top + window.scrollY + offset;
      window.scrollTo({ top, behavior: isSkip || prefersReducedMotion() ? 'auto' : 'smooth' });
      focusTarget(target);
    }
    if (!isSkip) history.replaceState(null, '', hash);
  });
}
