document.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-copy]');
  if (!target) return;
  const text = target.getAttribute('data-copy') || '';
  try {
    await navigator.clipboard.writeText(text);
    const old = target.textContent;
    target.textContent = 'Copied';
    setTimeout(() => { target.textContent = old; }, 1200);
  } catch (err) {
    alert('Copy failed. Select and copy manually.');
  }
});

const PROFILE_KEY = 'matchday_brain_worldcup_profile_v1';

function normaliseXHandle(value) {
  value = (value || '').trim().replace(/^@+/, '').replace(/\s+/g, '');
  return value.replace(/[^A-Za-z0-9_]/g, '').slice(0, 15);
}

function readSavedProfile() {
  try {
    return JSON.parse(localStorage.getItem(PROFILE_KEY) || '{}') || {};
  } catch (err) {
    return {};
  }
}

function writeSavedProfile(form) {
  const payload = {};
  form.querySelectorAll('[data-profile-field]').forEach((field) => {
    let value = (field.value || '').trim();
    if (field.name === 'x_handle') value = normaliseXHandle(value);
    payload[field.name] = value;
  });
  localStorage.setItem(PROFILE_KEY, JSON.stringify(payload));
}

function applySavedProfile(form) {
  const saved = readSavedProfile();
  const hasSaved = Object.values(saved).some((value) => value);
  if (!hasSaved) return;

  form.querySelectorAll('[data-profile-field]').forEach((field) => {
    const savedValue = saved[field.name];
    if (!savedValue || field.value) return;

    if (field.tagName === 'SELECT') {
      const option = Array.from(field.options).find((opt) => opt.value === savedValue || opt.textContent === savedValue);
      if (option) field.value = option.value;
    } else {
      field.value = field.name === 'x_handle' ? normaliseXHandle(savedValue) : savedValue;
    }
  });

  const note = document.querySelector('[data-profile-note]');
  if (note) note.hidden = false;
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-profile-form]');
  if (!form) return;

  applySavedProfile(form);

  form.addEventListener('submit', () => {
    writeSavedProfile(form);
  });

  const clearButton = document.querySelector('[data-clear-profile]');
  if (clearButton) {
    clearButton.addEventListener('click', () => {
      localStorage.removeItem(PROFILE_KEY);
      form.querySelectorAll('[data-profile-field]').forEach((field) => { field.value = ''; });
      const note = document.querySelector('[data-profile-note]');
      if (note) note.hidden = true;
    });
  }
});

// Premium UI controls: score steppers and quick first-goal minute buttons
function clampScore(value, min, max) {
  const n = Number.isFinite(value) ? value : 0;
  return Math.max(min, Math.min(max, n));
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-step]');
  if (!button) return;
  const stepper = button.closest('[data-stepper]');
  const input = stepper ? stepper.querySelector('input[type="number"]') : null;
  if (!input) return;
  const step = Number(button.getAttribute('data-step') || '0');
  const min = Number(input.min || '0');
  const max = Number(input.max || '20');
  input.value = clampScore(Number(input.value || '0') + step, min, max);
  input.dispatchEvent(new Event('change', { bubbles: true }));
});

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-minute]');
  if (!button) return;
  const input = document.querySelector('[data-minute-input]');
  if (!input) return;
  input.value = button.getAttribute('data-minute');
  document.querySelectorAll('[data-minute]').forEach((el) => el.classList.toggle('is-active', el === button));
});
