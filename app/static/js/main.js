// Entry point. Vendor scripts (Bootstrap, GSAP, Lenis) load first with `defer`;
// this module runs after them. Homepage-only code is loaded on demand.
import { initAnimations } from './animations.js';
import { initForms } from './forms.js';
import { initGallery } from './gallery.js';
import { initNavigation } from './navigation.js';
import { initAnchors, initSmoothScroll } from './scroll.js';
import { initUtilities } from './utils.js';

const root = document.documentElement;
const motion = initAnimations();
const lenis = initSmoothScroll(motion);

initAnchors(lenis);
initNavigation({ lenis });
initForms();
initGallery({ lenis });
initUtilities();

if (root.dataset.page === 'home') {
  import('./home.js')
    .then(({ initHome }) => initHome({ motion, lenis }))
    .catch((error) => {
      root.classList.remove('motion-ok', 'show-loader');
      console.error('Homepage enhancements failed to load', error);
    });
}
