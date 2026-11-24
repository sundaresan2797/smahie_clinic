// Header state, sliding active-link indicator, mobile menu, mobile CTA and
// back-to-top. One rAF-throttled passive scroll listener drives all of them.
import { $, $$, mq, prefersReducedMotion } from './utils.js';

export function initNavigation({ lenis }) {
  const header = $('[data-header]');
  const backTop = $('[data-back-to-top]');
  const mobileCta = $('[data-mobile-cta]');
  const hero = $('.hero, .page-hero, .profile-hero, .status-page, .error-page');

  let ticking = false;
  const update = () => {
    ticking = false;
    const y = window.scrollY;
    header?.classList.toggle('is-scrolled', y > 24);
    backTop?.classList.toggle('is-visible', y > 900);
    if (mobileCta) {
      const threshold = hero ? hero.offsetHeight * 0.55 : 320;
      const nearBottom = window.innerHeight + y >= document.documentElement.scrollHeight - 140;
      mobileCta.classList.toggle('is-visible', y > threshold && !nearBottom);
    }
  };
  window.addEventListener('scroll', () => {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true });
  update();

  backTop?.addEventListener('click', () => {
    if (lenis) lenis.scrollTo(0, { duration: 1.4 });
    else window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
    $('.site-header .brand')?.focus({ preventScroll: true });
  });

  initIndicator();
  initMobileMenu(lenis);
}

function initIndicator() {
  const list = $('[data-nav-list]');
  const indicator = $('[data-nav-indicator]');
  if (!list || !indicator) return;
  const nav = list.parentElement;
  const links = $$('[data-nav-link]', list);
  const active = links.find((l) => l.classList.contains('is-active')) || null;

  const moveTo = (el) => {
    if (!el) { indicator.style.setProperty('--o', '0'); return; }
    const navBox = nav.getBoundingClientRect();
    const box = el.getBoundingClientRect();
    const inset = 16;
    indicator.style.setProperty('--x', `${box.left - navBox.left + inset}px`);
    indicator.style.setProperty('--w', `${Math.max(box.width - inset * 2, 8)}px`);
    indicator.style.setProperty('--o', '1');
  };
  links.forEach((link) => {
    link.addEventListener('mouseenter', () => moveTo(link));
    link.addEventListener('focus', () => moveTo(link));
  });
  list.addEventListener('mouseleave', () => moveTo(active));
  list.addEventListener('focusout', (e) => { if (!list.contains(e.relatedTarget)) moveTo(active); });

  const snap = () => {
    indicator.style.transition = 'none';
    moveTo(active);
    void indicator.offsetWidth;
    indicator.style.transition = '';
  };
  window.addEventListener('resize', snap);
  document.fonts?.ready.then(snap);
  snap();
}

function initMobileMenu(lenis) {
  const panel = $('#mobileNav');
  if (!panel) return;
  panel.addEventListener('show.bs.offcanvas', () => lenis?.stop());
  panel.addEventListener('hidden.bs.offcanvas', () => lenis?.start());
  const hide = () => window.bootstrap?.Offcanvas.getInstance(panel)?.hide();
  $$('a[href^="#"]', panel).forEach((a) => a.addEventListener('click', hide));
  mq('(min-width: 1200px)').addEventListener('change', (e) => { if (e.matches) hide(); });
}
