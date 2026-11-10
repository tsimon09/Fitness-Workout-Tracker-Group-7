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
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
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
    const record = records.find(item => String(item[idKey]) === button.dataset.edit);
    logForm.dataset.editId = button.dataset.edit;
    for (const input of logForm.elements) {
      if (!input.name) continue;
      const value = record[input.name];
      input.value = value == null ? '' : input.type === 'datetime-local' ? localInput(new Date(value)) : value;
    }
    document.getElementById('entry-title').textContent = 'Edit ' + logForm.dataset.kind;
    logForm.querySelector('button[type="submit"]').textContent = 'Save changes';
    document.getElementById('cancel-edit').hidden = false;
    logForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
    logForm.elements[0].focus();
  }));
  document.getElementById('cancel-edit').addEventListener('click', () => {
    logForm.reset();
    delete logForm.dataset.editId;
    setDefaultDates();
    document.getElementById('entry-title').textContent = 'Add ' + logForm.dataset.kind;
    logForm.querySelector('button[type="submit"]').textContent = 'Save entry';
    document.getElementById('cancel-edit').hidden = true;
    logForm.querySelector('.form-message').hidden = true;
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
