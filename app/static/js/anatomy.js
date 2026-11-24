// Interactive anatomy guide. Uses the WAI-ARIA tabs pattern (arrow keys,
// Home/End); the figure hotspots mirror the tabs for pointer users.
import { $$ } from './utils.js';

export function initAnatomy(root, { gsap, animate }) {
  const tabs = $$('[data-anat-tab]', root);
  const panels = $$('[data-anat-panel]', root);
  const regions = $$('[data-anat-region]', root);
  const hotspots = $$('[data-anat-select]', root);
  if (!tabs.length) return;

  const keys = tabs.map((t) => t.dataset.anatTab);
  let current = tabs.find((t) => t.getAttribute('aria-selected') === 'true')?.dataset.anatTab || keys[0];

  const select = (key, { focusTab = false } = {}) => {
    tabs.forEach((tab) => {
      const on = tab.dataset.anatTab === key;
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;
      if (on && focusTab) tab.focus();
    });
    panels.forEach((panel) => {
      const on = panel.dataset.anatPanel === key;
      const wasHidden = panel.hidden;
      panel.hidden = !on;
      if (on && wasHidden && gsap && animate()) {
        gsap.fromTo(panel, { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: 0.55, ease: 'power3.out' });
      }
    });
    regions.forEach((r) => r.classList.toggle('is-active', r.dataset.anatRegion === key));
    hotspots.forEach((h) => h.classList.toggle('is-active', h.dataset.anatSelect === key));
    current = key;
  };

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => select(tab.dataset.anatTab));
    tab.addEventListener('keydown', (event) => {
      const i = keys.indexOf(current);
      const next = {
        ArrowRight: keys[(i + 1) % keys.length],
        ArrowDown: keys[(i + 1) % keys.length],
        ArrowLeft: keys[(i - 1 + keys.length) % keys.length],
        ArrowUp: keys[(i - 1 + keys.length) % keys.length],
        Home: keys[0],
        End: keys[keys.length - 1],
      }[event.key];
      if (next) {
        event.preventDefault();
        select(next, { focusTab: true });
      }
    });
  });
  hotspots.forEach((h) => h.addEventListener('click', () => select(h.dataset.anatSelect)));
  regions.forEach((r) => r.addEventListener('click', () => select(r.dataset.anatRegion)));
  select(current);
}
