// The same JSON endpoints work from these forms and from Postman.
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const notice = document.getElementById('notice');
function showNotice(message, error = false) {
  notice.textContent = message;
  notice.hidden = false;
  notice.classList.toggle('error', error);
}
const savedNotice = sessionStorage.getItem('fitnut_notice');
if (savedNotice) { showNotice(savedNotice); sessionStorage.removeItem('fitnut_notice'); }

async function sendJSON(url, method, body) {
  const response = await fetch(url, { method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || 'Something went wrong. Please try again.');
    error.confirmation = data.confirmation_required;
    throw error;
  }
  return data;
}

// Shared display helpers for the totals on the Overview, Food, and Activity pages.
function createElement(tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function formatNumber(value, maximumFractionDigits = 2) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits });
}
function formatDuration(minutes) {
  const total = Math.round(minutes);
  const hours = Math.floor(total / 60);
  return hours ? `${hours} h ${total % 60} min` : `${total} min`;
}
function dayRange(date) {
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start, end };
}
function weekRange(date) {
  const start = dayRange(date).start;
  start.setDate(start.getDate() - (start.getDay() + 6) % 7); // Weeks start on Monday.
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return { start, end };
}
function summaryPath(api, range) {
  return `${api}/summary?start=${encodeURIComponent(range.start.toISOString())}&end=${encodeURIComponent(range.end.toISOString())}`;
}
function factsRows(rows, list = document.createElement('dl')) {
  list.classList.add('facts-rows');
  list.replaceChildren(...rows.map(([label, value]) => {
    const row = document.createElement('div');
    row.append(createElement('dt', label), createElement('dd', value));
    return row;
  }));
  return list;
}
function targetProgress(value, target, label) {
  const bar = document.createElement('progress');
  bar.max = target;
  bar.value = Math.min(value, target);
  bar.setAttribute('aria-label', label);
  return bar;
}
function figureLine(value, unit) {
  const line = createElement('p', null, 'figure-line');
  // Very large totals drop a size so they always fit their panel.
  line.append(createElement('span', value, value.length > 5 ? 'figure long' : 'figure'), createElement('span', unit, 'figure-unit'));
  return line;
}
// Calories by source as one bar, with the grams spelled out underneath.
function macroParts(totals) {
  const shares = [['protein_g', 4, 'p'], ['carbs_g', 4, 'c'], ['fat_g', 9, 'f']].map(([key, perGram, cls]) => [cls, Number(totals[key] ?? 0) * perGram]);
  const whole = shares.reduce((sum, [, value]) => sum + value, 0);
  const bar = createElement('div', null, 'macro');
  bar.setAttribute('role', 'img');
  bar.setAttribute('aria-label', whole ? `Calories by source: protein ${Math.round(shares[0][1] / whole * 100)} percent, carbs ${Math.round(shares[1][1] / whole * 100)} percent, fat ${Math.round(shares[2][1] / whole * 100)} percent` : 'No nutrition entered yet');
  shares.forEach(([cls, value]) => {
    const part = createElement('b', null, cls);
    part.style.flexGrow = value;
    bar.append(part);
  });
  const key = createElement('div', null, 'macro-key');
  [['protein_g', 'protein', 'p'], ['carbs_g', 'carbs', 'c'], ['fat_g', 'fat', 'f'], ['fiber_g', 'fiber', '']].forEach(([field, name, cls]) => {
    const item = createElement('span');
    if (cls) item.append(createElement('i', null, cls));
    item.append(totals[field] == null ? `${name} not entered` : `${formatNumber(totals[field], 0)} g ${name}`);
    key.append(item);
  });
  return [bar, key];
}
function foodTotals({ totals, goals }) {
  const eaten = totals.calories ?? 0;
  const target = goals.daily_calorie_target;
  const summary = createElement('div', null, 'day-panel-figure');
  summary.append(figureLine(totals.calories == null && totals.entries ? '—' : formatNumber(eaten, 0), 'calories'));
  if (target != null) {
    const left = target - eaten;
    summary.append(targetProgress(eaten, target, 'Calories against your daily target'),
      createElement('p', `Target ${formatNumber(target)} calories. ${formatNumber(Math.abs(left))} ${left >= 0 ? 'left' : 'over'} from recorded calories.`, 'facts-note'));
  } else summary.append(createElement('p', 'No daily calorie target set.', 'facts-note'));
  const missing = totals.entries && ['calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g'].some(key => totals[key + '_entered'] < totals.entries);
  summary.append(createElement('p', `${totals.entries} ${totals.entries === 1 ? 'entry' : 'entries'}.${missing ? ' Missing nutrition is excluded, so each total may be partial.' : ''}`, 'facts-note quiet'));
  summary.append(...macroParts(totals));
  return [summary];
}
function activityTotals({ totals, goals }) {
  const minutes = totals.duration_minutes ?? 0;
  const target = goals.weekly_activity_minutes;
  const summary = createElement('div', null, 'day-panel-figure');
  summary.append(figureLine(formatNumber(minutes, 0), 'minutes'));
  if (target != null) {
    summary.append(targetProgress(minutes, target, 'Activity minutes against your weekly target'),
      createElement('p', `Target ${formatNumber(target)} minutes. ${formatNumber(minutes / target * 100, 0)}% of weekly target.`, 'facts-note'));
  } else summary.append(createElement('p', 'No weekly activity target set.', 'facts-note'));
  return [summary, factsRows([['Activities', formatNumber(totals.entries)],
    ['Calories burned', totals.calories_burned == null ? 'Not entered' : formatNumber(totals.calories_burned)],
    ['Calories entered for', `${totals.calories_burned_entered} of ${totals.entries} activities`]])];
}

function localInput(date) {
  const pad = value => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function setDefaultDates() {
  document.querySelectorAll('input[data-now]').forEach(input => {
    if (!input.value) input.value = localInput(new Date());
  });
}
setDefaultDates();
document.querySelectorAll('time[data-date]').forEach(time => {
  const date = new Date(time.dataset.date);
  if (!Number.isNaN(date.getTime())) time.textContent = date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
});
// Saved meals and sleep arrive as UTC timestamps, so local wording is filled in here.
document.querySelectorAll('option[data-meal-date]').forEach(option => {
  const date = new Date(option.dataset.mealDate);
  if (!Number.isNaN(date.getTime())) option.textContent = `${option.dataset.mealType}, ${date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`;
});
document.querySelectorAll('[data-sleep-start]').forEach(heading => {
  const minutes = (new Date(heading.dataset.sleepEnd) - new Date(heading.dataset.sleepStart)) / 60000;
  if (minutes > 0) heading.textContent = formatDuration(minutes);
});

document.querySelectorAll('form[data-api]:not(.admin-form)').forEach(form => {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const message = form.querySelector('.form-message');
    const button = form.querySelector('button[type="submit"]');
    message.hidden = true;
    button.disabled = true;
    try {
      const body = Object.fromEntries(new FormData(form));
      form.querySelectorAll('input[type="datetime-local"]').forEach(input => {
        if (body[input.name]) body[input.name] = new Date(body[input.name]).toISOString();
      });
      const url = form.dataset.api + (form.dataset.editId ? '/' + form.dataset.editId : '');
      if (form.id === 'log-form' && ['food', 'activity'].includes(form.dataset.kind)) {
        await handleLoggingSubmit(form, body, url);
        button.disabled = false;
        return;
      }
      const data = await sendJSON(url, form.dataset.editId ? 'PUT' : 'POST', body);
      sessionStorage.setItem('fitnut_notice', data.message);
      if (form.dataset.redirect) window.location.assign(form.dataset.redirect);
      else window.location.reload();
    } catch (error) {
      message.textContent = error.message;
      message.hidden = false;
      button.disabled = false;
    }
  });
  // logging.js enables the log form once its own handler is ready.
  if (form.id !== 'log-form') form.querySelector('button[type="submit"]').disabled = false;
});

document.querySelector('[data-logout]')?.addEventListener('click', async () => {
  try {
    await sendJSON('/logout', 'POST', {});
    sessionStorage.setItem('fitnut_notice', 'You have been logged out.');
    window.location.assign('/login');
  } catch (error) { showNotice(error.message, true); }
});

const logForm = document.getElementById('log-form');
if (logForm) {
  const records = JSON.parse(document.getElementById('record-data').textContent);
  const idKey = logForm.dataset.kind + '_log_id';
  document.querySelectorAll('[data-edit]').forEach(button => button.addEventListener('click', () => {
    if (typeof canStartLogEdit === 'function' && !canStartLogEdit()) return;
    const record = records.find(item => String(item[idKey]) === button.dataset.edit);
    logForm.dataset.editId = button.dataset.edit;
    for (const input of logForm.elements) {
      if (!input.name) continue;
      const value = record[input.name];
      input.value = value == null ? '' : input.type === 'datetime-local' ? localInput(new Date(value)) : value;
    }
    document.getElementById('entry-title').textContent = 'Edit ' + logForm.dataset.kind;
    logForm.querySelector('button[type="submit"]').textContent = ['food', 'activity'].includes(logForm.dataset.kind) ? 'Review changes' : 'Save changes';
    logForm.dispatchEvent(new CustomEvent('log-edit', { detail: record }));
    document.getElementById('cancel-edit').hidden = false;
    logForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
    logForm.querySelector('input:not([type="hidden"])').focus();
  }));
  document.getElementById('cancel-edit').addEventListener('click', () => {
    logForm.reset();
    delete logForm.dataset.editId;
    setDefaultDates();
    document.getElementById('entry-title').textContent = 'Add ' + logForm.dataset.kind;
    logForm.querySelector('button[type="submit"]').textContent = logForm.dataset.kind === 'food' ? 'Add food to meal' : logForm.dataset.kind === 'activity' ? 'Review activity' : 'Save entry';
    document.getElementById('cancel-edit').hidden = true;
    logForm.querySelector('.form-message').hidden = true;
    logForm.dispatchEvent(new Event('log-reset'));
  });
  document.querySelectorAll('[data-delete]').forEach(button => button.addEventListener('click', async () => {
    if (!window.confirm('Delete this entry?')) return;
    button.disabled = true;
    try {
      await sendJSON(logForm.dataset.api + '/' + button.dataset.delete, 'DELETE');
      sessionStorage.setItem('fitnut_notice', 'Entry deleted.');
      window.location.reload();
    } catch (error) { showNotice(error.message, true); button.disabled = false; }
  }));
}
document.querySelectorAll('[data-admin-save]').forEach(button => button.addEventListener('click', async () => {
  const form = document.querySelector(`form[data-api="/admin/users/${button.dataset.adminSave}"]`);
  button.disabled = true;
  try {
    const data = await sendJSON(form.dataset.api, 'PATCH', Object.fromEntries(new FormData(form)));
    sessionStorage.setItem('fitnut_notice', data.message);
    window.location.reload();
  } catch (error) { showNotice(error.message, true); button.disabled = false; }
}));
