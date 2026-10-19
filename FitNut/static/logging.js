// Logging-specific review and meal drafts; the existing account forms are shared.
let draftFoods = [];
let draftMeal = null;
let pendingLog = null;
const nutrientFields = ['calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g'];
const mealFields = ['eating_event_id', 'meal_type', 'logged_at', 'meal_notes'];
const review = document.getElementById('entry-review');
const existingMeals = JSON.parse(document.getElementById('meal-data')?.textContent || '[]');

function canStartLogEdit() {
  if (!draftFoods.length) return true;
  showNotice('Save or discard the meal draft before editing an entry.', true);
  return false;
}

function describeFood(item) {
  const shown = value => value == null ? 'not entered' : value;
  return `${item.food_name}: ${item.quantity} ${item.quantity_unit}\n` +
    `Calories ${shown(item.calories)} · Protein ${shown(item.protein_g)} g · Carbs ${shown(item.carbs_g)} g · Fat ${shown(item.fat_g)} g · Fiber ${shown(item.fiber_g)} g`;
}

async function handleLoggingSubmit(form, body, url) {
  const selectedMeal = existingMeals.find(meal => String(meal.eating_event_id) === body.eating_event_id);
  if (selectedMeal && (!form.dataset.editId || body.eating_event_id !== form.dataset.originalMealId)) {
    Object.assign(body, { meal_type: selectedMeal.meal_type, logged_at: selectedMeal.event_datetime, meal_notes: selectedMeal.comments || '' });
  }
  if (draftMeal) Object.assign(body, draftMeal);
  const kind = form.dataset.kind;
  const data = await sendJSON(`/${kind}-preview`, 'POST', body);
  if (kind === 'food' && !form.dataset.editId) {
    if (draftFoods.length >= 50) throw new Error('Save this meal before adding more than 50 foods.');
    if (!draftMeal) draftMeal = Object.fromEntries(mealFields.map(key => [key, body[key]]));
    draftFoods.push({ body, preview: data.item });
    renderDraft();
    clearFood();
    return;
  }
  pendingLog = { url, method: form.dataset.editId ? 'PUT' : 'POST', body };
  const item = data.item;
  document.getElementById('review-details').textContent = kind === 'food' ? describeFood(item) :
    `${body.activity_name} · ${body.intensity} intensity · ${body.duration_minutes} minutes\n` +
    `Start: ${new Date(item.time_started).toLocaleString()}\nFinish: ${new Date(item.time_finished).toLocaleString()}\n` +
    `Calories burned: ${item.calories_burned ?? 'not entered'} (${item.calorie_source === 'estimated' ? 'estimate' : 'entered by you'})` +
    (item.met_value ? `\nMET ${item.met_value} · Body weight ${item.body_weight_kg} kg` : '') +
    (item.distance_km != null ? `\nDistance ${item.distance_km} km` : '') +
    (item.set_count != null ? `\nSets ${item.set_count}` : '') + (item.rep_count != null ? ` · Reps ${item.rep_count}` : '') +
    (item.notes ? `\n${item.notes}` : '');
  document.getElementById('review-message').textContent = '';
  document.getElementById('confirm-save').textContent = 'Confirm and save';
  review.hidden = false;
  review.scrollIntoView({ block: 'nearest' });
}

function clearFood() {
  for (const name of ['food_name', 'quantity', 'quantity_unit', 'serving_grams', 'food_id', ...nutrientFields]) {
    logForm.elements[name].value = '';
  }
  syncFoodMode();
}

function renderDraft() {
  const list = document.getElementById('draft-items');
  list.replaceChildren();
  draftFoods.forEach((food, index) => {
    const item = document.createElement('li');
    const details = document.createElement('p');
    details.className = 'note-text';
    details.textContent = describeFood(food.preview);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Remove food';
    remove.addEventListener('click', () => { draftFoods.splice(index, 1); if (!draftFoods.length) draftMeal = null; renderDraft(); });
    item.append(details, remove);
    list.append(item);
  });
  document.getElementById('meal-draft').hidden = !draftFoods.length;
  for (const name of mealFields) logForm.elements[name].disabled = Boolean(draftMeal);
  if (!draftMeal) syncMeal(false);
}

function syncMeal(changed) {
  const select = logForm.elements.eating_event_id;
  const selected = existingMeals.find(meal => String(meal.eating_event_id) === select.value);
  const reuse = selected && (!logForm.dataset.editId || select.value !== logForm.dataset.originalMealId);
  for (const name of mealFields.filter(name => name !== 'eating_event_id')) logForm.elements[name].disabled = Boolean(reuse);
  if (reuse) {
    logForm.elements.meal_type.value = selected.meal_type;
    logForm.elements.logged_at.value = localInput(new Date(selected.event_datetime));
    logForm.elements.meal_notes.value = selected.comments || '';
  } else if (changed && !selected) {
    logForm.elements.logged_at.value = localInput(new Date());
    logForm.elements.meal_notes.value = '';
  }
}

function syncFoodMode() {
  const searched = Boolean(logForm.elements.food_id.value);
  logForm.elements.food_name.readOnly = searched;
  nutrientFields.forEach(name => { logForm.elements[name].readOnly = searched; });
  document.getElementById('selected-food').textContent = searched ?
    'USDA food selected. Use g, or serving with grams per serving. Nutrition is calculated when you review or add it.' :
    'Manual entry: enter nutrition for the whole quantity.';
}

function syncActivityMode() {
  const estimated = logForm.elements.calorie_source.value === 'estimated';
  logForm.elements.calories_burned.disabled = estimated;
  logForm.elements.body_weight_kg.required = estimated;
}

if (review) {
  document.getElementById('back-to-form').addEventListener('click', () => { review.hidden = true; pendingLog = null; });
  logForm.addEventListener('input', () => { review.hidden = true; pendingLog = null; });
  document.getElementById('confirm-save').addEventListener('click', async event => {
    if (!pendingLog) return;
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const data = await sendJSON(pendingLog.url, pendingLog.method, pendingLog.body);
      sessionStorage.setItem('fitnut_notice', data.message);
      window.location.reload();
    } catch (error) {
      document.getElementById('review-message').textContent = error.message;
      if (error.confirmation === 'overlap') {
        pendingLog.body.confirm_overlap = true;
        button.textContent = 'Keep overlapping activity and save';
      }
    } finally { button.disabled = false; }
  });
}

if (document.getElementById('food-search-form')) {
  document.getElementById('food-search-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button[type="submit"]');
    const message = document.getElementById('food-search-message');
    const results = document.getElementById('food-results');
    button.disabled = true;
    results.replaceChildren();
    message.textContent = 'Searching…';
    try {
      const data = await sendJSON('/food-search?q=' + encodeURIComponent(document.getElementById('food-query').value), 'GET');
      message.textContent = data.items.length ? `Source: ${data.source}. Nutrition is per 100 g.` : 'No matching foods. Try a different name or enter food manually.';
      for (const item of data.items) {
        const choice = document.createElement('button');
        choice.type = 'button';
        choice.textContent = `${item.food_name} (${item.calories} calories per 100 g)`;
        choice.addEventListener('click', () => {
          logForm.elements.food_id.value = item.food_id;
          logForm.elements.food_name.value = item.food_name;
          logForm.elements.quantity_unit.value = 'g';
          nutrientFields.forEach(name => { logForm.elements[name].value = ''; });
          syncFoodMode();
          if (review) review.hidden = true;
        });
        results.append(choice);
      }
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; }
  });
  document.getElementById('manual-food').addEventListener('click', () => {
    logForm.elements.food_id.value = '';
    syncFoodMode();
    if (review) review.hidden = true;
  });
  document.getElementById('save-meal').addEventListener('click', async event => {
    const button = event.currentTarget;
    const message = document.getElementById('draft-message');
    if (logForm.elements.food_name.value.trim()) { message.textContent = 'Add the current food to the draft before saving the meal.'; return; }
    button.disabled = true;
    try {
      const data = await sendJSON('/meals', 'POST', { ...draftMeal, items: draftFoods.map(item => item.body) });
      sessionStorage.setItem('fitnut_notice', data.message);
      window.location.reload();
    } catch (error) { message.textContent = error.message; button.disabled = false; }
  });
  document.getElementById('discard-meal').addEventListener('click', () => {
    draftFoods = []; draftMeal = null; renderDraft();
  });
  logForm.elements.eating_event_id.addEventListener('change', () => syncMeal(true));
  logForm.addEventListener('log-edit', event => {
    logForm.dataset.originalMealId = String(event.detail.eating_event_id);
    syncFoodMode(); syncMeal(false);
  });
  logForm.addEventListener('log-reset', () => { delete logForm.dataset.originalMealId; syncFoodMode(); syncMeal(false); });
}

if (logForm?.dataset.kind === 'activity') {
  logForm.elements.calorie_source.addEventListener('change', syncActivityMode);
  logForm.addEventListener('log-edit', syncActivityMode);
  logForm.addEventListener('log-reset', syncActivityMode);
  syncActivityMode();
}
logForm?.addEventListener('log-edit', () => { if (review) review.hidden = true; pendingLog = null; });
logForm?.addEventListener('log-reset', () => { if (review) review.hidden = true; pendingLog = null; });

async function refreshLogTotals() {
  const input = document.getElementById('summary-date');
  const output = document.getElementById('log-totals');
  if (!input?.value) return;
  const start = new Date(input.value + 'T00:00:00');
  const end = new Date(start);
  if (logForm.dataset.kind === 'activity') {
    start.setDate(start.getDate() - (start.getDay() + 6) % 7);
    end.setTime(start.getTime()); end.setDate(end.getDate() + 7);
  } else end.setDate(end.getDate() + 1);
  try {
    const data = await sendJSON(logForm.dataset.api + '/summary?start=' + encodeURIComponent(start.toISOString()) + '&end=' + encodeURIComponent(end.toISOString()), 'GET');
    const totals = data.totals;
    const shown = value => value == null ? 'not entered' : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
    output.textContent = `${totals.entries} entries · ` + (logForm.dataset.kind === 'food' ?
      `Calories ${shown(totals.calories)} · Protein ${shown(totals.protein_g)} g · Carbs ${shown(totals.carbs_g)} g · Fat ${shown(totals.fat_g)} g · Fiber ${shown(totals.fiber_g)} g. Missing nutrition is excluded; each total may be partial.` :
      `${shown(totals.duration_minutes)} minutes · ${shown(totals.calories_burned)} calories burned. Calories entered for ${totals.calories_burned_entered} of ${totals.entries} activities.`);
    const goal = logForm.dataset.kind === 'food' ? data.goals.daily_calorie_target : data.goals.weekly_activity_minutes;
    if (goal != null) output.textContent += logForm.dataset.kind === 'food' ?
      ` Target ${shown(goal)} calories; ${shown(goal - (totals.calories ?? 0))} remaining from recorded calories${totals.calories_entered < totals.entries ? ' (partial: some calories are missing)' : ''}.` :
      ` Target ${shown(goal)} minutes; ${shown((totals.duration_minutes ?? 0) / goal * 100)}% of weekly target.`;
  } catch (error) { output.textContent = error.message; }
}
if (document.getElementById('summary-date')) {
  const dateInput = document.getElementById('summary-date');
  dateInput.value = localInput(new Date()).slice(0, 10);
  dateInput.addEventListener('change', refreshLogTotals);
  refreshLogTotals();
  document.getElementById('logging-goal-form').addEventListener('submit', async event => {
    event.preventDefault();
    const message = document.getElementById('goal-message');
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try {
      const data = await sendJSON('/logging-goal', 'POST', { kind: logForm.dataset.kind, target: document.getElementById('logging-target').value });
      message.textContent = data.message;
      await refreshLogTotals();
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; }
  });
}
