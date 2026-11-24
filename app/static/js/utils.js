// Small shared helpers: DOM queries, media queries, toast and clipboard.

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
export const mq = (query) => window.matchMedia(query);
export const prefersReducedMotion = () => mq('(prefers-reduced-motion: reduce)').matches;
export const isFinePointer = () => mq('(hover: hover) and (pointer: fine)').matches;

let toastTimer;
export function toast(message) {
  const region = $('[data-toast]');
  if (!region) return;
  region.replaceChildren();
  const el = document.createElement('div');
  el.className = 'toast-msg';
  el.innerHTML = '<svg class="icon" width="18" height="18" aria-hidden="true"><use href="#i-check"></use></svg>';
  const text = document.createElement('span');
  text.textContent = message;
  el.append(text);
  region.append(el);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), 2800);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    area.remove();
    return ok;
  }
}

export function initUtilities() {
  $$('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      const ok = await copyText(button.dataset.copy);
      toast(ok ? button.dataset.copyLabel || 'Copied' : 'Copy failed — please note the number manually');
    });
  });
  const autofocus = $('[data-autofocus]');
  if (autofocus) autofocus.focus({ preventScroll: true });
}
