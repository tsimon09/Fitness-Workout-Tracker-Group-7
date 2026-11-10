const profileForm = document.getElementById('profile-form');
const allergyStatus = profileForm.elements.allergy_status;
function syncAllergies() {
  document.getElementById('allergy-details').disabled = allergyStatus.value !== 'listed';
}

// Height and weight are shown in feet, inches and pounds but stored in centimeters and kilograms.
// The stored values only change when the person edits these controls, so an unrelated save never rounds them.
const heightCm = profileForm.elements.height_cm;
const weightKg = profileForm.elements.weight_kg;
const weightLb = document.getElementById('weight-lb');
const originalHeight = heightCm.value;
const originalWeight = weightKg.value;
const LB_PER_KG = 2.2046226218;
const ROW = 44;

function wheel(id, values, unit, onUserChange) {
  const el = document.getElementById(id);
  // The first row means not set, so a blank height stays blank.
  const rows = ['', ...values];
  const pad = () => createElement('div', null, 'pad');
  el.replaceChildren(pad(), ...rows.map(value => createElement('div', value === '' ? '—' : `${value} ${unit}`)), pad());
  let touched = false, timer = 0;
  const describe = value => {
    el.setAttribute('aria-valuenow', value === '' ? rows.indexOf('') : value);
    el.setAttribute('aria-valuetext', value === '' ? 'Not set' : `${value} ${unit}`);
  };
  el.setAttribute('aria-valuemin', 0);
  el.setAttribute('aria-valuemax', values[values.length - 1]);
  const get = () => rows[Math.max(0, Math.min(rows.length - 1, Math.round(el.scrollTop / ROW)))];
  const set = value => { el.scrollTop = Math.max(rows.indexOf(value), 0) * ROW; describe(value); };
  for (const type of ['pointerdown', 'wheel', 'touchstart']) el.addEventListener(type, () => { touched = true; }, { passive: true });
  el.addEventListener('scroll', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      describe(get());
      if (touched) { touched = false; onUserChange(); }
    }, 110);
  });
  el.addEventListener('keydown', event => {
    const here = rows.indexOf(get());
    const next = { ArrowUp: here - 1, ArrowDown: here + 1, Home: 0, End: rows.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    set(rows[Math.max(0, Math.min(rows.length - 1, next))]);
    onUserChange();
  });
  return { get, set };
}

let feet, inches;
function updateHeight() {
  const ft = feet.get();
  if (ft === '') { inches.set(''); heightCm.value = ''; return; }
  if (inches.get() === '') inches.set(0);
  heightCm.value = ((ft * 12 + inches.get()) * 2.54).toFixed(2);
}
feet = wheel('height-feet', [0, 1, 2, 3, 4, 5, 6, 7, 8], 'ft', updateHeight);
inches = wheel('height-inches', [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], 'in', updateHeight);

function showHeight(cm) {
  if (!cm) { feet.set(''); inches.set(''); return; }
  const total = Math.round(Number(cm) / 2.54);
  feet.set(Math.min(Math.floor(total / 12), 8));
  inches.set(total % 12);
}
const showWeight = kg => { weightLb.value = kg ? String(Math.round(Number(kg) * LB_PER_KG * 10) / 10) : ''; };
function restoreMeasures() {
  heightCm.value = originalHeight;
  weightKg.value = originalWeight;
  showHeight(originalHeight);
  showWeight(originalWeight);
}
restoreMeasures();

const updateWeight = () => { weightKg.value = weightLb.value === '' ? '' : (Number(weightLb.value) / LB_PER_KG).toFixed(2); };
weightLb.addEventListener('input', updateWeight);
document.querySelectorAll('[data-step-weight]').forEach(button => button.addEventListener('click', () => {
  weightLb.value = String(Math.max(1, Math.round((Number(weightLb.value || 0) + Number(button.dataset.stepWeight)) * 10) / 10));
  updateWeight();
}));
document.getElementById('clear-measures').addEventListener('click', () => {
  feet.set(''); inches.set(''); weightLb.value = ''; heightCm.value = ''; weightKg.value = '';
});

// Each target has a slider for quick changes and a box for an exact value. Blank means no target, which differs from zero.
function syncTarget(control) {
  const range = control.querySelector('.target-range'), number = control.querySelector('.target-number');
  const value = Number(number.value);
  range.disabled = number.value === '' || !Number.isFinite(value);
  range.value = range.disabled ? range.min : String(Math.min(Number(range.max), Math.max(Number(range.min), value)));
}
profileForm.querySelectorAll('.target-control').forEach(control => {
  const range = control.querySelector('.target-range'), number = control.querySelector('.target-number');
  range.addEventListener('input', () => { number.value = range.value; });
  number.addEventListener('input', () => syncTarget(control));
  control.querySelector('.target-clear').addEventListener('click', () => { number.value = ''; syncTarget(control); });
  syncTarget(control);
});

allergyStatus.addEventListener('change', syncAllergies);
profileForm.addEventListener('reset', () => {
  profileForm.querySelector('.form-message').hidden = true;
  requestAnimationFrame(() => {
    syncAllergies();
    restoreMeasures();
    profileForm.querySelectorAll('.target-control').forEach(syncTarget);
  });
});
profileForm.addEventListener('submit', async event => {
  event.preventDefault();
  const message = profileForm.querySelector('.form-message');
  const button = profileForm.querySelector('button[type="submit"]');
  message.hidden = true;
  button.disabled = true;
  const data = new FormData(profileForm);
  const body = Object.fromEntries(data);
  const lines = key => String(data.get(key) || '').split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  body.allergens = allergyStatus.value === 'listed' ? data.getAll('allergens') : [];
  body.other_allergies = allergyStatus.value === 'listed' ? lines('other_allergies') : [];
  body.intolerances = lines('intolerances');
  body.preferences = lines('preferences');
  try {
    const result = await sendJSON('/profile-data', 'POST', body);
    sessionStorage.setItem('fitnut_notice', result.message);
    window.location.reload();
  } catch (error) {
    message.textContent = error.message;
    message.hidden = false;
    button.disabled = false;
  }
});
syncAllergies();
// Enabled only now, so an early click cannot submit the form as a page load.
profileForm.querySelector('button[type="submit"]').disabled = false;
