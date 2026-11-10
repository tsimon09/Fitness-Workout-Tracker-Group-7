// Logging-specific review and meal drafts; the existing account forms are shared.
let draftFoods = [];
let draftMeal = null;
// Almond transfers ingredient IDs, never trusted nutrition totals. Preview again before logging.
const almondDraft = sessionStorage.getItem('almond-log-draft');
if (almondDraft && document.getElementById('log-form')?.dataset.kind === 'food') {
  sessionStorage.removeItem('almond-log-draft');
  queueMicrotask(async () => {
    try {
      const draft = JSON.parse(almondDraft);
      if (!Array.isArray(draft.foods) || draft.foods.length > 20) throw new Error('Invalid Almond draft.');
      const meal = {meal_type: 'dinner', logged_at: new Date().toISOString(), meal_notes: draft.recipe.title};
      const prepared = [];
      for (const food of draft.foods) {
        const body = {...food, ...meal};
        const data = await sendJSON('/food-preview', 'POST', body);
        prepared.push({body, preview: data.item});
      }
      draftFoods = prepared; draftMeal = meal; renderDraft();
      showNotice('Almond meal draft loaded. Review the foods and portions before saving.');
    } catch (error) { showNotice(error.message, true); }
  });
}
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

function describeNutrition(item) {
  const grams = value => value == null ? 'not entered' : `${value} g`;
  return `Calories ${item.calories ?? 'not entered'}, protein ${grams(item.protein_g)}, carbs ${grams(item.carbs_g)}, fat ${grams(item.fat_g)}, fiber ${grams(item.fiber_g)}`;
}

function describeFood(item) {
  return `${item.food_name}: ${item.quantity} ${item.quantity_unit}\n${describeNutrition(item)}`;
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
    `${body.activity_name}, ${body.intensity} intensity, ${body.duration_minutes} minutes\n` +
    `Start: ${new Date(item.time_started).toLocaleString()}\nFinish: ${new Date(item.time_finished).toLocaleString()}\n` +
    `Calories burned: ${item.calories_burned ?? 'not entered'} (${item.calorie_source === 'estimated' ? 'estimate' : 'entered by you'})` +
    (item.met_value ? `\nMET ${item.met_value}, body weight ${item.body_weight_kg} kg` : '') +
    (item.distance_km != null ? `\nDistance ${item.distance_km} km` : '') +
    (item.set_count != null ? `\nSets ${item.set_count}` : '') + (item.rep_count != null ? `\nReps ${item.rep_count}` : '') +
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
    const top = createElement('div', null, 'draft-food');
    const name = createElement('span');
    name.append(createElement('strong', food.preview.food_name), ` ${food.preview.quantity} ${food.preview.quantity_unit}`);
    const remove = createElement('button', 'Remove food', 'text-button');
    remove.type = 'button';
    remove.setAttribute('aria-label', `Remove ${food.preview.food_name}`);
    remove.addEventListener('click', () => {
      draftFoods.splice(index, 1);
      if (!draftFoods.length) draftMeal = null;
      renderDraft();
      // The clicked button is gone, so keep keyboard users in a sensible place.
      (draftFoods.length ? document.getElementById('save-meal') : logForm.elements.food_name).focus();
    });
    top.append(name, remove);
    item.append(top, createElement('p', describeNutrition(food.preview), 'hint'));
    list.append(item);
  });
  renderDraftSummary();
  document.getElementById('meal-draft').hidden = !draftFoods.length;
  document.getElementById('meal-lock').hidden = !draftMeal;
  for (const name of mealFields) logForm.elements[name].disabled = Boolean(draftMeal);
  if (!draftMeal) syncMeal(false);
}

function renderDraftSummary() {
  // A nutrient no food has a value for reads "Not entered", because 0 would claim it was measured.
  const total = (key, unit = '') => {
    const values = draftFoods.map(food => food.preview[key]).filter(value => value != null);
    return values.length ? formatNumber(values.reduce((sum, value) => sum + Number(value), 0)) + unit : 'Not entered';
  };
  factsRows([['Meal calories', total('calories')], ['Protein', total('protein_g', ' g')], ['Carbs', total('carbs_g', ' g')],
    ['Fat', total('fat_g', ' g')], ['Fiber', total('fiber_g', ' g')]], document.getElementById('draft-totals'));
  const when = draftMeal && new Date(draftMeal.logged_at);
  document.getElementById('draft-meal').textContent = when && !Number.isNaN(when.getTime()) ?
    `Saving as ${draftMeal.meal_type}, ${when.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}` : '';
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
  // USDA foods calculate their own nutrition, so only the fields that apply stay on screen.
  document.getElementById('manual-nutrition').hidden = searched;
  document.getElementById('serving-grams-field').hidden = !searched;
  document.getElementById('selected-food').textContent = searched ?
    'USDA food selected. Use g, or serving with grams per serving. Nutrition is calculated when you review or add it.' :
    'Manual entry: enter nutrition for the whole quantity.';
}

function syncActivityMode() {
  const estimated = logForm.elements.calorie_source.value === 'estimated';
  logForm.elements.calories_burned.disabled = estimated;
  logForm.elements.body_weight_kg.required = estimated;
  document.getElementById('estimate-fields').hidden = !estimated;
  document.getElementById('manual-calorie-field').hidden = estimated;
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
        choice.setAttribute('aria-pressed', 'false');
        choice.append(createElement('span', item.food_name), createElement('span', `${item.calories} calories per 100 g`, 'per-100'));
        choice.addEventListener('click', () => {
          results.querySelectorAll('button').forEach(other => other.setAttribute('aria-pressed', String(other === choice)));
          logForm.elements.food_id.value = item.food_id;
          logForm.elements.food_name.value = item.food_name;
          logForm.elements.quantity_unit.value = 'g';
          nutrientFields.forEach(name => { logForm.elements[name].value = ''; });
          syncFoodMode();
          if (review) review.hidden = true;
          logForm.elements.quantity.focus();
        });
        results.append(choice);
      }
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; }
  });
  document.getElementById('manual-food').addEventListener('click', () => {
    logForm.elements.food_id.value = '';
    document.querySelectorAll('#food-results button').forEach(choice => choice.setAttribute('aria-pressed', 'false'));
    syncFoodMode();
    if (review) review.hidden = true;
    logForm.elements.food_name.focus();
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
  logForm.addEventListener('log-edit', event => {
    syncActivityMode();
    // Show the optional details when the entry being edited has any.
    const { distance_km, set_count, rep_count, notes } = event.detail;
    if (distance_km != null || set_count != null || rep_count != null || notes) document.getElementById('activity-extras').open = true;
  });
  logForm.addEventListener('log-reset', syncActivityMode);
  syncActivityMode();
}
logForm?.addEventListener('log-edit', () => { if (review) review.hidden = true; pendingLog = null; });
logForm?.addEventListener('log-reset', () => { if (review) review.hidden = true; pendingLog = null; });

// Sleep: show how long the night was while the times are being entered.
if (logForm?.dataset.kind === 'sleep') {
  const syncSleepLength = () => {
    const start = logForm.elements.sleep_start.value, end = logForm.elements.sleep_end.value;
    const minutes = start && end ? (new Date(end) - new Date(start)) / 60000 : null;
    document.getElementById('sleep-length').textContent = minutes == null ? '' :
      minutes > 0 ? `${formatDuration(minutes)} of sleep` : 'Wake time needs to be after the start time.';
  };
  logForm.addEventListener('input', syncSleepLength);
  logForm.addEventListener('log-edit', syncSleepLength);
  logForm.addEventListener('log-reset', syncSleepLength);

  // The band names the latest night. graphics.js draws the dial beside it.
  const nights = JSON.parse(document.getElementById('record-data').textContent)
    .map(night => ({ ...night, minutes: (new Date(night.sleep_end) - new Date(night.sleep_start)) / 60000 }))
    .filter(night => night.minutes > 0);
  if (nights.length) {
    const latest = nights[0];
    const ended = new Date(latest.sleep_end).toLocaleDateString([], { month: 'short', day: 'numeric' });
    document.getElementById('sleep-latest').textContent = formatDuration(latest.minutes);
    document.getElementById('sleep-latest-note').textContent = `Latest entry, ending ${ended}${latest.sleep_quality ? `, quality ${latest.sleep_quality}/5` : ''}`;
    document.getElementById('sleep-band').hidden = false;
  }
}

let showDayJar = null;
async function refreshLogTotals() {
  const input = document.getElementById('summary-date');
  const output = document.getElementById('log-totals');
  if (!input?.value) return;
  const date = new Date(input.value + 'T00:00:00');
  const isFood = logForm.dataset.kind === 'food';
  try {
    const data = await sendJSON(summaryPath(logForm.dataset.api, isFood ? dayRange(date) : weekRange(date)), 'GET');
    output.replaceChildren(...(isFood ? foodTotals(data) : activityTotals(data)));
    if (isFood && window.FitNutDayJar) {
      showDayJar ??= FitNutDayJar(document.getElementById('jar-stage'));
      showDayJar(date, data.goals).catch(() => {});
    }
  } catch (error) { output.textContent = error.message; }
}
if (document.getElementById('summary-date')) {
  const dateInput = document.getElementById('summary-date');
  dateInput.value = localInput(new Date()).slice(0, 10);
  dateInput.addEventListener('change', refreshLogTotals);
  // Wait for the deferred 3D scripts, which load after this file.
  addEventListener('DOMContentLoaded', refreshLogTotals);
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
// Prevent native form navigation during the short interval before handlers attach.
document.querySelector('#food-search-form button[type="submit"]')?.removeAttribute('disabled');
document.querySelector('#log-form button[type="submit"]')?.removeAttribute('disabled');
document.querySelector('#logging-goal-form button[type="submit"]')?.removeAttribute('disabled');
document.documentElement.dataset.loggingReady = 'true';
