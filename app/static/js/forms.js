// Progressive enhancement for the appointment and contact forms. Without
// JavaScript the forms post normally and the server re-renders any errors.
import { $, $$ } from './utils.js';

const REQUIRED_MESSAGES = {
  full_name: 'Please enter your full name.',
  name: 'Please enter your name.',
  phone: 'Please enter your 10-digit mobile number.',
  preferred_date: 'Please choose a preferred date.',
  preferred_session: 'Please choose a morning or evening session.',
  message: 'Please write your message.',
  consent: 'Please agree to the privacy notice to continue.',
};
const ALERT_ICON = '<svg class="icon" width="16" height="16" aria-hidden="true"><use href="#i-alert"></use></svg>';

export function isIndianMobile(raw) {
  let digits = String(raw || '').replace(/[\s\-().]/g, '');
  if (digits.startsWith('+91')) digits = digits.slice(3);
  else if (digits.startsWith('0091')) digits = digits.slice(4);
  else if (digits.startsWith('91') && digits.length === 12) digits = digits.slice(2);
  else if (digits.startsWith('0') && digits.length === 11) digits = digits.slice(1);
  return /^[6-9]\d{9}$/.test(digits);
}

function messageFor(input) {
  const v = input.validity;
  const name = input.name;
  if (v.valueMissing) return REQUIRED_MESSAGES[name] || 'Please fill in this field.';
  if (v.typeMismatch && input.type === 'email') return 'Please enter a valid email address, or leave this blank.';
  if (v.tooShort) return name === 'message' ? 'Please write a little more (at least 10 characters).' : 'Please enter at least 2 characters.';
  if (v.rangeUnderflow) return 'Please choose today or a future date.';
  if (v.rangeOverflow) return 'Please choose a date closer to today.';
  if (v.badInput) return 'Please enter a valid date.';
  if (name === 'phone' && input.value.trim() && !isIndianMobile(input.value)) {
    return 'Please enter a valid 10-digit Indian mobile number.';
  }
  return '';
}

function setFieldError(form, name, message) {
  const output = form.querySelector(`#${CSS.escape(name)}-error`);
  const inputs = $$(`[name="${name}"]`, form);
  const group = inputs[0]?.closest('fieldset.field');
  if (output) {
    output.replaceChildren();
    if (message) {
      output.insertAdjacentHTML('afterbegin', ALERT_ICON);
      const text = document.createElement('span');
      text.textContent = message;
      output.append(text);
    }
    output.hidden = !message;
  }
  inputs.forEach((i) => (message ? i.setAttribute('aria-invalid', 'true') : i.removeAttribute('aria-invalid')));
  if (group) message ? group.setAttribute('aria-invalid', 'true') : group.removeAttribute('aria-invalid');
}

function validateField(form, input) {
  const message = messageFor(input);
  setFieldError(form, input.name, message);
  return message;
}

function validate(form) {
  const errors = {};
  const seen = new Set();
  $$('input, select, textarea', form).forEach((input) => {
    if (!input.name || input.type === 'hidden' || input.closest('.hp-field') || seen.has(input.name)) return;
    seen.add(input.name);
    const message = validateField(form, input);
    if (message) errors[input.name] = message;
  });
  const requireOne = form.dataset.requireOne?.split(',');
  if (requireOne && requireOne.every((n) => !form.elements[n]?.value.trim()) && !errors[requireOne[0]]) {
    errors[requireOne[0]] = 'Please give a mobile number or an email address so we can reply.';
    setFieldError(form, requireOne[0], errors[requireOne[0]]);
  }
  return errors;
}

function focusFirstError(form) {
  const invalid = form.querySelector('[aria-invalid="true"]');
  const target = invalid?.matches('fieldset') ? invalid.querySelector('input') : invalid;
  target?.focus();
}

function showAlert(form, message) {
  const alert = $('[data-form-alert]', form);
  const text = $('[data-form-alert-text]', form);
  if (!alert || !text) return;
  text.textContent = message || '';
  alert.hidden = !message;
}

function showSuccess(form, message) {
  const card = form.closest('.form-card');
  const success = card && $('[data-form-success]', card);
  if (!success) return;
  const text = $('[data-form-success-text]', success);
  if (text && message) text.textContent = message;
  form.hidden = true;
  success.hidden = false;
  success.focus({ preventScroll: true });
  card.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

function linkSessionAndTime(form) {
  const select = $('[data-time-select]', form);
  const radios = $$('[name="preferred_session"]', form);
  if (!select || !radios.length) return;
  const sync = () => {
    const session = radios.find((r) => r.checked)?.value;
    $$('optgroup', select).forEach((group) => {
      const match = !session || group.dataset.session === session;
      group.disabled = !match;
      group.hidden = !match;
    });
    const chosen = select.selectedOptions[0];
    if (session && chosen?.dataset.session && chosen.dataset.session !== session) select.value = '';
  };
  radios.forEach((r) => r.addEventListener('change', sync));
  select.addEventListener('change', () => {
    const session = select.selectedOptions[0]?.dataset.session;
    const radio = radios.find((r) => r.value === session);
    if (radio && !radio.checked) {
      radio.checked = true;
      setFieldError(form, 'preferred_session', '');
      sync();
    }
  });
  sync();
}

function initCounters(form) {
  $$('[data-counter]', form).forEach((area) => {
    const output = area.closest('.field')?.querySelector('[data-counter-output]');
    if (!output) return;
    const max = area.maxLength > 0 ? area.maxLength : 500;
    const render = () => { output.textContent = `${area.value.length} / ${max}`; };
    area.addEventListener('input', render);
    render();
  });
}

async function submit(form) {
  showAlert(form, '');
  const errors = validate(form);
  if (Object.keys(errors).length) {
    showAlert(form, 'Please correct the highlighted fields.');
    focusFirstError(form);
    return;
  }

  const data = Object.fromEntries(new FormData(form).entries());
  data.consent = Boolean(form.elements.consent?.checked);
  const button = $('[data-submit]', form);
  const label = $('[data-submit-label]', form);
  const original = label?.textContent;
  button?.setAttribute('disabled', '');
  button?.classList.add('is-loading');
  if (label) label.textContent = 'Sending…';

  try {
    const response = await fetch(form.dataset.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(data),
    });
    const body = await response.json().catch(() => ({}));
    if (response.ok && body.ok) {
      showSuccess(form, body.message);
      return;
    }
    Object.entries(body.errors || {}).forEach(([name, message]) => {
      if (name !== 'form') setFieldError(form, name, message);
    });
    showAlert(form, body.errors?.form || body.message || 'Something went wrong. Please try again or call the clinic.');
    focusFirstError(form);
  } catch {
    showAlert(form, 'We could not send this. Please check your connection and try again, or call the clinic.');
  } finally {
    button?.removeAttribute('disabled');
    button?.classList.remove('is-loading');
    if (label && original) label.textContent = original;
  }
}

export function initForms() {
  $$('form[data-ajax-form]').forEach((form) => {
    linkSessionAndTime(form);
    initCounters(form);
    $$('input, select, textarea', form).forEach((input) => {
      if (input.type === 'hidden' || input.closest('.hp-field')) return;
      input.addEventListener('blur', () => { if (input.value || input.hasAttribute('aria-invalid')) validateField(form, input); });
      input.addEventListener('input', () => { if (input.hasAttribute('aria-invalid') && !messageFor(input)) setFieldError(form, input.name, ''); });
      input.addEventListener('change', () => { if (input.hasAttribute('aria-invalid')) validateField(form, input); });
    });
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      submit(form);
    });
  });
}
