// Accessible lightbox built on the Bootstrap modal: focus trap, Esc to close,
// arrow keys and swipe to navigate, focus returned to the opening tile.
import { $, $$ } from './utils.js';

export function initGallery({ lenis }) {
  const modalEl = $('[data-lightbox]');
  const items = $$('[data-gallery-item]');
  if (!modalEl || !items.length || !window.bootstrap) return;

  const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
  const stage = $('[data-lightbox-stage]', modalEl);
  const title = $('[data-lightbox-title]', modalEl);
  const caption = $('[data-lightbox-caption]', modalEl);
  const counter = $('[data-lightbox-counter]', modalEl);
  let index = 0;
  let opener = null;
  let closeRequested = false;

  const render = (i) => {
    index = (i + items.length) % items.length;
    const item = items[index];
    const template = item.querySelector('template');
    stage.replaceChildren(template ? template.content.cloneNode(true) : document.createTextNode(''));
    title.textContent = item.dataset.title || 'Gallery';
    caption.textContent = item.dataset.caption || '';
    counter.textContent = `${index + 1} / ${items.length}`;
    if (window.gsap && document.documentElement.classList.contains('motion-ok')) {
      window.gsap.fromTo(stage.firstElementChild, { autoAlpha: 0, scale: 0.97 }, { autoAlpha: 1, scale: 1, duration: 0.5, ease: 'power3.out' });
    }
  };

  items.forEach((item, i) => {
    item.addEventListener('click', () => {
      opener = item;
      render(i);
      modal.show();
    });
  });
  $('[data-lightbox-prev]', modalEl).addEventListener('click', () => render(index - 1));
  $('[data-lightbox-next]', modalEl).addEventListener('click', () => render(index + 1));

  // Listen on the document so arrows work as soon as the dialog opens,
  // even before Bootstrap has moved focus inside it.
  document.addEventListener('keydown', (event) => {
    if (!modalEl.classList.contains('show')) return;
    if (event.key === 'Escape') {
      // Bootstrap ignores hide() during the opening fade, so remember the request.
      closeRequested = true;
      modal.hide();
      return;
    }
    if (event.key === 'ArrowLeft') { event.preventDefault(); render(index - 1); }
    if (event.key === 'ArrowRight') { event.preventDefault(); render(index + 1); }
  });

  let startX = null;
  stage.addEventListener('pointerdown', (e) => { startX = e.clientX; });
  stage.addEventListener('pointerup', (e) => {
    if (startX === null) return;
    const dx = e.clientX - startX;
    startX = null;
    if (Math.abs(dx) > 50) render(index + (dx < 0 ? 1 : -1));
  });

  modalEl.addEventListener('show.bs.modal', () => { closeRequested = false; lenis?.stop(); });
  modalEl.addEventListener('shown.bs.modal', () => { if (closeRequested) modal.hide(); });
  modalEl.addEventListener('hidden.bs.modal', () => {
    closeRequested = false;
    lenis?.start();
    stage.replaceChildren();
    opener?.focus({ preventScroll: true });
  });
}
