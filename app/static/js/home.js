// Homepage choreography: loader → cinematic hero timeline, intro panel scrub,
// pinned storytelling (desktop) / stacked timeline (mobile), hero pointer depth.
import { QUERIES } from './animations.js';
import { initAnatomy } from './anatomy.js';
import { $, $$ } from './utils.js';

export function initHome({ motion }) {
  const root = document.documentElement;
  const anatomy = $('[data-anatomy]');
  if (anatomy) {
    initAnatomy(anatomy, { gsap: motion.gsap, animate: () => root.classList.contains('motion-ok') });
  }
  if (!motion.enabled) return;

  const { gsap, ScrollTrigger, SplitText, mm } = motion;
  heroIntro(gsap, SplitText);

  mm.add(
    QUERIES,
    (context) => {
      const { desktop, reduce, fine } = context.conditions;
      if (reduce) return undefined;
      introSection(gsap, SplitText, desktop);
      const cleanStory = desktop ? pinnedStory(gsap, ScrollTrigger) : stackedStory(gsap);
      const cleanPointer = desktop && fine ? heroPointer(gsap) : null;
      return () => { cleanStory?.(); cleanPointer?.(); };
    },
  );
}

function heroIntro(gsap, SplitText) {
  const root = document.documentElement;
  const loader = $('[data-loader]');
  const withLoader = root.classList.contains('show-loader') && loader;
  const title = $('[data-hero="title"]');
  const tl = gsap.timeline({ defaults: { ease: 'expo.out', duration: 1.1 } });

  if (withLoader) {
    tl.fromTo('[data-loader-mark]', { autoAlpha: 0, scale: 0.85 }, { autoAlpha: 1, scale: 1, duration: 0.7 })
      .fromTo('[data-loader-word]', { autoAlpha: 0, y: 10 }, { autoAlpha: 1, y: 0, duration: 0.6 }, '<0.12')
      .to('[data-loader-line]', { scaleX: 1, duration: 0.65, ease: 'power2.inOut' }, '<0.05')
      .to(loader, { yPercent: -100, duration: 0.85, ease: 'expo.inOut' }, '+=0.05')
      .add(() => {
        root.classList.remove('show-loader');
        try { sessionStorage.setItem('soc-intro', '1'); } catch { /* storage unavailable */ }
      })
      .addLabel('hero', '-=0.55');
  } else {
    tl.addLabel('hero', 0);
  }

  tl.fromTo('[data-intro="brand"]', { autoAlpha: 0, y: -14 }, { autoAlpha: 1, y: 0, duration: 0.9 }, 'hero')
    .fromTo('[data-intro="nav"]', { autoAlpha: 0, y: -12 }, { autoAlpha: 1, y: 0, duration: 0.8, stagger: 0.05 }, 'hero+=0.1')
    .fromTo('[data-hero="eyebrow"]', { autoAlpha: 0, y: 16 }, { autoAlpha: 1, y: 0, duration: 0.9 }, 'hero+=0.15');

  if (title && SplitText) {
    const split = SplitText.create(title, { type: 'lines', mask: 'lines', linesClass: 'split-line' });
    gsap.set(title, { autoAlpha: 1 });
    tl.from(split.lines, { yPercent: 110, duration: 1.25, stagger: 0.12 }, 'hero+=0.25');
    tl.add(() => split.revert());
  } else if (title) {
    tl.fromTo(title, { autoAlpha: 0, y: 30 }, { autoAlpha: 1, y: 0 }, 'hero+=0.25');
  }

  tl.fromTo('[data-hero="fade"]', { autoAlpha: 0, y: 26 }, { autoAlpha: 1, y: 0, duration: 1, stagger: 0.12 }, 'hero+=0.55')
    .fromTo('.hero__curtain', { scaleY: 1 }, { scaleY: 0, duration: 1.4, ease: 'expo.inOut' }, 'hero+=0.2')
    .fromTo('.hero__img', { scale: 1.18 }, { scale: 1, duration: 2, ease: 'expo.out' }, 'hero+=0.45')
    .fromTo('[data-hero="deco"]', { autoAlpha: 0, scale: 0.94 }, { autoAlpha: 1, scale: 1, duration: 1.6, stagger: 0.12 }, 'hero+=0.6')
    .fromTo('[data-hero="badge"]', { autoAlpha: 0, y: 22 }, { autoAlpha: 1, y: 0, duration: 1, stagger: 0.12 }, 'hero+=1');
  return tl;
}

// Exact on-screen length of a path drawn with vector-effect: non-scaling-stroke.
function screenLength(path) {
  const m = path.getScreenCTM();
  const total = path.getTotalLength();
  if (!m || !total) return 0;
  let length = 0;
  let prev = null;
  for (let i = 0; i <= 80; i += 1) {
    const p = path.getPointAtLength((total * i) / 80);
    const x = m.a * p.x + m.c * p.y;
    const y = m.b * p.x + m.d * p.y;
    if (prev) length += Math.hypot(x - prev.x, y - prev.y);
    prev = { x, y };
  }
  return Math.ceil(length) + 2;
}

function introSection(gsap, SplitText, desktop) {
  const panel = $('[data-intro-panel]');
  if (panel && desktop) {
    gsap.fromTo(panel, { clipPath: 'inset(0% 4% 0% 4% round 48px)' }, {
      clipPath: 'inset(0% 0% 0% 0% round 0px)', ease: 'none',
      scrollTrigger: { trigger: panel, start: 'top bottom', end: 'top 15%', scrub: true },
    });
  }
  const statement = $('[data-scrub-words]');
  if (statement && SplitText) {
    SplitText.create(statement, {
      type: 'words',
      aria: 'none',
      autoSplit: true,
      onSplit(self) {
        return gsap.fromTo(self.words, { opacity: 0.18 }, {
          opacity: 1, stagger: 0.08, ease: 'none',
          scrollTrigger: { trigger: statement, start: 'top 82%', end: 'bottom 50%', scrub: true },
        });
      },
    });
  }
  const wave = $('[data-anim="draw-scrub"] .draw-path');
  if (wave) {
    gsap.fromTo(wave, { strokeDasharray: () => screenLength(wave), strokeDashoffset: () => screenLength(wave) }, {
      strokeDashoffset: 0, ease: 'none',
      scrollTrigger: { trigger: wave.closest('svg'), start: 'top 92%', end: 'bottom 40%', scrub: true, invalidateOnRefresh: true },
    });
  }
}

function pinnedStory(gsap) {
  const section = $('[data-story]');
  if (!section) return null;
  const items = $$('[data-story-item]', section);
  const arts = $$('[data-story-art]', section);
  const bars = $$('[data-story-bar]', section);
  const ring = $('[data-story-ring]', section);
  const counter = $('[data-story-current]', section);
  const count = items.length;
  const circumference = 2 * Math.PI * 186;
  const colors = ['#071b2d', '#0a2338', '#0c2741', '#102f4a'];
  let active = 0;

  const setActive = (i) => {
    if (i === active) return;
    active = i;
    if (counter) counter.textContent = String(i + 1).padStart(2, '0');
    bars.forEach((bar, j) => bar.classList.toggle('is-active', j === i));
  };

  section.classList.add('is-pinned');
  gsap.set(section, { backgroundColor: colors[0] });
  gsap.set(items, { autoAlpha: 0, y: 40 });
  gsap.set(items[0], { autoAlpha: 1, y: 0 });
  gsap.set(arts, { autoAlpha: 0, scale: 0.92, transformOrigin: '50% 50%' });
  gsap.set(arts[0], { autoAlpha: 1, scale: 1 });
  gsap.set(ring, { strokeDasharray: circumference, strokeDashoffset: circumference * (1 - 1 / count) });

  const tl = gsap.timeline({
    defaults: { ease: 'power2.inOut' },
    scrollTrigger: {
      trigger: section,
      start: 'top top',
      end: () => `+=${Math.round(window.innerHeight * (count - 1) * 0.85)}`,
      pin: true,
      scrub: 0.6,
      anticipatePin: 1,
      invalidateOnRefresh: true,
      onUpdate: (self) => setActive(Math.min(count - 1, Math.round(self.progress * (count - 1)))),
    },
  });
  for (let i = 1; i < count; i += 1) {
    const at = (i - 1) * 1.2;
    tl.to(items[i - 1], { autoAlpha: 0, y: -40, duration: 0.6 }, at)
      .fromTo(items[i], { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.6 }, at + 0.45)
      .to(arts[i - 1], { autoAlpha: 0, scale: 1.06, duration: 0.6 }, at)
      .fromTo(arts[i], { autoAlpha: 0, scale: 0.92 }, { autoAlpha: 1, scale: 1, duration: 0.7 }, at + 0.4)
      .to(ring, { strokeDashoffset: circumference * (1 - (i + 1) / count), duration: 1.05 }, at)
      .to(section, { backgroundColor: colors[Math.min(i, colors.length - 1)], duration: 1.05 }, at);
  }

  return () => {
    section.classList.remove('is-pinned');
    active = -1;
    setActive(0);
  };
}

function stackedStory(gsap) {
  $$('[data-story-item]').forEach((item) => {
    gsap.fromTo(item, { opacity: 0, y: 30 }, {
      opacity: 1, y: 0, duration: 1, ease: 'expo.out',
      scrollTrigger: { trigger: item, start: 'top 88%', once: true },
    });
  });
  return null;
}

function heroPointer(gsap) {
  const hero = $('[data-hero-root]');
  if (!hero) return null;
  const layers = $$('[data-depth]', hero).map((el) => ({
    x: gsap.quickTo(el, 'x', { duration: 1.2, ease: 'power3.out' }),
    y: gsap.quickTo(el, 'y', { duration: 1.2, ease: 'power3.out' }),
    depth: parseFloat(el.dataset.depth) || 0.2,
  }));
  const move = (event) => {
    const r = hero.getBoundingClientRect();
    const nx = (event.clientX - r.left) / r.width - 0.5;
    const ny = (event.clientY - r.top) / r.height - 0.5;
    layers.forEach((l) => { l.x(nx * 44 * l.depth); l.y(ny * 32 * l.depth); });
  };
  const leave = () => layers.forEach((l) => { l.x(0); l.y(0); });
  hero.addEventListener('pointermove', move);
  hero.addEventListener('pointerleave', leave);
  return () => {
    hero.removeEventListener('pointermove', move);
    hero.removeEventListener('pointerleave', leave);
  };
}
