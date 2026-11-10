// All responses render as text. Credentials and food checks stay on the server.
(() => {
  if (!document.getElementById('almond')) return;
  const el = id => document.getElementById('almond-' + id);
  const GOAL_LABELS = { maintain: 'Maintain weight', lose_weight: 'Lose weight', gain_weight: 'Gain weight', gain_muscle: 'Build muscle', improve_fitness: 'Improve fitness' };
  // Default and Fitness behave the same. Each keeps its own open chat and unsent text.
  const chats = { default: { id: null, draft: '' }, fitness: { id: null, draft: '' } };
  let mode = 'default', favoriteId = null, busy = false, available = false, dietaryConfirmed = false, conversations = [];
  let liveGoalRow = null, openRecipe = null, mealOpener = null;
  const savedFavorites = new Map();
  const chat = () => chats[mode];

  function error(text) { el('error').textContent = text || ''; el('error').hidden = !text; }
  function node(tag, text, cls) { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; }
  function button(text, action, cls) {
    const b = node('button', text, cls);
    b.type = 'button';
    b.addEventListener('click', () => Promise.resolve(action(b)).catch(e => error(e.message)));
    return b;
  }

  function message(role, content) {
    const a = node('article', null, 'almond-message' + (role === 'user' ? '' : ' from-almond'));
    a.append(node('strong', role === 'user' ? 'You' : 'Almond'), node('p', content, 'note-text'));
    el('messages').append(a);
    el('messages').scrollTop = el('messages').scrollHeight;
    return a;
  }

  // Three small Almonds hop while a reply is being checked. Screen readers hear the words.
  function loadingMessage() {
    const a = node('article', null, 'almond-message from-almond is-pending');
    const hops = node('div', null, 'almond-hops');
    hops.setAttribute('role', 'status');
    hops.append(node('span', 'Almond is checking your request', 'sr-only'));
    for (let i = 0; i < 3; i++) {
      const hop = node('img', null, 'hop');
      hop.src = el('mark').src;
      hop.alt = '';
      hops.append(hop);
    }
    a.append(node('strong', 'Almond'), hops);
    el('messages').append(a);
    el('messages').scrollTop = el('messages').scrollHeight;
    return a;
  }

  // The recipe contents are shared by the meal popup and saved favorites.
  function recipeBody(recipe) {
    const body = document.createDocumentFragment();
    const layout = node('div', null, 'recipe-layout');
    const method = node('div', null, 'recipe-method');
    const foods = node('ul'), steps = node('ol');
    recipe.foods.forEach(f => foods.append(node('li', `${f.grams} g ${f.food_name}`)));
    recipe.instructions.forEach(s => steps.append(node('li', s)));
    const ingredients = node('div'), preparation = node('div');
    ingredients.append(node('h4', 'Ingredients'), foods);
    preparation.append(node('h4', 'Steps'), steps);
    method.append(ingredients, preparation);
    if (recipe.substitutions?.length) {
      const swaps = node('ul'), box = node('div');
      recipe.substitutions.forEach(s => swaps.append(node('li', s)));
      box.append(node('h4', 'Substitutions'), swaps);
      method.append(box);
    }
    const n = recipe.nutrition || {};
    const grams = value => value == null ? 'Unknown' : `${formatNumber(value)} g`;
    const facts = node('div', null, 'recipe-facts');
    facts.append(node('h4', 'Estimated nutrition'),
      figureLine(n.calories == null ? '—' : formatNumber(n.calories, 0), 'calories'),
      factsRows([['Protein', grams(n.protein_g)], ['Carbs', grams(n.carbs_g)], ['Fat', grams(n.fat_g)]]));
    layout.append(method, facts);
    body.append(layout);

    const sources = node('details');
    sources.append(node('summary', 'Ingredient sources'));
    recipe.foods.forEach(f => {
      try {
        const url = new URL(f.source_url);
        if (url.protocol !== 'https:') return;
        const link = node('a', f.food_name);
        link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
        const p = node('p'); p.append(link); sources.append(p);
      } catch (_) { /* Invalid sources remain blocked by backend validation. */ }
    });
    if (sources.querySelector('a')) body.append(sources);
    if (recipe.note) body.append(node('p', recipe.note, 'recipe-note'));
    return body;
  }

  function syncHeart() {
    const saved = savedFavorites.has(openRecipe?.id);
    const heart = el('meal-favorite');
    heart.setAttribute('aria-pressed', String(saved));
    heart.setAttribute('aria-label', saved ? 'Remove from favorites' : 'Save to favorites');
    heart.textContent = saved ? '♥' : '♡';
  }

  function showMeal(recipe, id, opener) {
    openRecipe = { recipe, id };
    mealOpener = opener;
    el('meal-title').textContent = recipe.title;
    el('meal-body').replaceChildren(recipeBody(recipe));
    el('meal-message').textContent = '';
    syncHeart();
    el('meal-dialog').showModal();
  }

  // Chat shows a compact card, and the full recipe opens in a popup.
  function recipeCard(recipe, id) {
    const a = node('article', null, 'almond-recipe');
    const calories = recipe.nutrition?.calories;
    const open = button('See recipe', b => showMeal(recipe, id, b));
    a.append(node('h3', recipe.title),
      node('p', `${recipe.foods.length} ${recipe.foods.length === 1 ? 'ingredient' : 'ingredients'}${calories == null ? '' : `, about ${formatNumber(calories, 0)} calories`}`), open);
    a.addEventListener('click', event => { if (event.target !== open) open.click(); });
    el('recipes').append(a);
    return a;
  }

  // Almond proposes a goal here, and only the Save button changes the profile.
  function goalRow(proposal) {
    if (liveGoalRow) retire(liveGoalRow);
    const row = node('div', null, 'almond-action');
    const question = node('p');
    question.append('Save ', node('strong', proposal.label), ' as your current goal?');
    const scope = node('p', `Now: ${GOAL_LABELS[proposal.current] || 'Not set'}. Applies to your Profile. Calorie and weight targets stay as you set them.`, 'hint');
    const status = node('p', null, 'hint');
    status.setAttribute('role', 'status');
    const actions = node('div', null, 'actions');
    const save = node('button', 'Save', 'button');
    const once = node('button', 'Just this conversation');
    save.type = once.type = 'button';
    const done = () => { save.textContent = 'Saved'; save.disabled = true; once.remove(); status.textContent = ''; liveGoalRow = null; };
    if (proposal.saved) done();
    save.addEventListener('click', async () => {
      save.disabled = once.disabled = true;
      save.textContent = 'Saving…';
      status.textContent = '';
      try {
        await sendJSON('/almond/goals/confirm', 'POST', { confirmed: true, request_id: proposal.request_id });
        done();
      } catch (e) {
        status.textContent = e.message;
        save.textContent = 'Retry';
        save.disabled = once.disabled = false;
      }
    });
    once.addEventListener('click', () => { retire(row); status.textContent = 'Kept to this conversation. Your Profile did not change.'; liveGoalRow = null; });
    actions.append(save, once);
    row.append(question, scope, actions, status);
    el('messages').append(row);
    el('messages').scrollTop = el('messages').scrollHeight;
    if (!proposal.saved) liveGoalRow = row;
    return row;
  }
  // A proposal that has been replaced stays visible but can no longer be saved.
  function retire(row) {
    row.classList.add('is-old');
    row.querySelectorAll('button').forEach(b => { b.disabled = true; });
  }

  function favoriteItem(f) {
    const item = node('details', null, 'favorite');
    const actions = node('div', null, 'actions');
    const card = node('div', null, 'almond-recipe');
    card.append(recipeBody(f.recipe));
    if (available && dietaryConfirmed) actions.append(button('Revisit with Almond', () => {
      favoriteId = f.favorite_id;
      el('question').value = `Revisit ${f.recipe.title}.`;
      el('question').focus();
    }));
    const remove = button('Remove', async () => { await sendJSON(`/almond/favorites/${f.favorite_id}`, 'DELETE'); await state(); }, 'text-button danger');
    remove.setAttribute('aria-label', `Remove ${f.recipe.title} from favorites`);
    actions.append(remove);
    item.append(node('summary', f.recipe.title), card, actions);
    return item;
  }

  function syncChatControls() {
    el('new').hidden = !chat().id;
    el('delete').hidden = !chat().id;
  }

  function fillHistory() {
    const here = conversations.filter(c => (c.mode || 'default') === mode);
    el('history').replaceChildren(new Option('New conversation', ''));
    here.forEach(c => el('history').append(new Option(c.title, c.conversation_id)));
    el('history').value = chat().id || '';
    el('chats').hidden = !here.length && !chat().id;
    syncChatControls();
  }

  // The chat stays covered until the account has an allergy answer, and nothing is sent before then.
  function syncLock() {
    el('gate').hidden = dietaryConfirmed;
    el('workspace').inert = !dietaryConfirmed;
    el('question').disabled = !dietaryConfirmed || !available;
    el('send').disabled = busy || !available || !dietaryConfirmed;
    el('form').hidden = !available;
    el('suggestions').hidden = !available;
    document.querySelectorAll('input[name="almond-mode"]').forEach(input => { input.disabled = busy; });
  }

  async function state() {
    const data = await sendJSON('/almond/state', 'GET');
    available = data.enabled;
    dietaryConfirmed = Boolean(data.dietary_confirmed);
    conversations = data.conversations;
    el('status').textContent = available ? 'Ready' : 'Not available yet';
    el('unavailable').hidden = available;
    syncLock();
    fillHistory();

    el('suggestions').replaceChildren();
    data.suggestions.forEach(s => el('suggestions').append(button(s.text, () => {
      if (s.kind === 'favorite') el('favorites').closest('details').open = true;
      else { el('question').value = s.text; el('question').focus(); }
    })));

    el('favorites').replaceChildren();
    if (!data.favorites.length) el('favorites').append(node('p', 'Save a meal here when you want to revisit it.'));
    data.favorites.forEach(f => el('favorites').append(favoriteItem(f)));

    const f = el('memory');
    f.elements.cuisines.value = data.memory.cuisines.join('\n');
    f.elements.cooking_minutes.value = data.memory.cooking_minutes ?? '';
    f.elements.food_budget.value = data.memory.food_budget ?? '';
  }

  /* Allergy question and dietary details */
  const dietDialog = el('diet-dialog'), dietForm = el('diet-form');
  let dietOpener = null;
  function lines(value) { return String(value || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean); }
  async function editDiet(opener, preset) {
    dietOpener = opener;
    const { profile: p } = await sendJSON('/profile-data', 'GET');
    const status = preset || (p.allergy_status === 'not_provided' ? 'listed' : p.allergy_status);
    dietForm.elements.allergy_status.value = status;
    dietForm.querySelectorAll('[name="allergens"]').forEach(box => { box.checked = (p.allergens || []).includes(box.value); });
    dietForm.elements.other_allergies.value = (p.other_allergies || []).join('\n');
    dietForm.elements.dietary_pattern.value = p.dietary_pattern || '';
    dietForm.elements.intolerances.value = (p.intolerances || []).join('\n');
    dietForm.elements.preferences.value = (p.preferences || []).join('\n');
    el('allergy-details').disabled = status !== 'listed';
    el('diet-error').hidden = true;
    dietDialog.showModal();
  }
  async function unlocked() {
    await state();
    if (!el('question').disabled) el('question').focus();
  }
  el('allergy-status').addEventListener('change', () => { el('allergy-details').disabled = el('allergy-status').value !== 'listed'; });
  el('gate-none').addEventListener('click', async event => {
    const b = event.currentTarget;
    b.disabled = true;
    el('gate-error').hidden = true;
    try {
      // The server merges this into the saved profile, so height, weight, goals and targets stay as they were.
      await sendJSON('/profile-data', 'POST', { allergy_status: 'none_reported' });
      await unlocked();
    } catch (e) { el('gate-error').textContent = e.message; el('gate-error').hidden = false; }
    finally { b.disabled = false; }
  });
  el('gate-list').addEventListener('click', event => editDiet(event.currentTarget, 'listed').catch(e => { el('gate-error').textContent = e.message; el('gate-error').hidden = false; }));
  el('edit-diet').addEventListener('click', event => editDiet(event.currentTarget).catch(e => error(e.message)));
  el('close-diet').addEventListener('click', () => dietDialog.close());
  dietDialog.addEventListener('close', () => { if (dietOpener?.offsetParent) dietOpener.focus(); });
  dietForm.addEventListener('submit', async e => {
    e.preventDefault();
    const submit = dietForm.querySelector('[type="submit"]');
    submit.disabled = true;
    el('diet-error').hidden = true;
    const status = dietForm.elements.allergy_status.value;
    try {
      await sendJSON('/profile-data', 'POST', {
        allergy_status: status,
        allergens: status === 'listed' ? [...dietForm.querySelectorAll('[name="allergens"]:checked')].map(x => x.value) : [],
        other_allergies: status === 'listed' ? lines(dietForm.elements.other_allergies.value) : [],
        dietary_pattern: dietForm.elements.dietary_pattern.value || null,
        intolerances: lines(dietForm.elements.intolerances.value),
        preferences: lines(dietForm.elements.preferences.value),
      });
      dietDialog.close();
      await unlocked();
    } catch (err) {
      el('diet-error').textContent = err.message;
      el('diet-error').hidden = false;
    } finally { submit.disabled = false; }
  });

  /* Meal popup */
  const mealDialog = el('meal-dialog');
  el('meal-close').addEventListener('click', () => mealDialog.close());
  mealDialog.addEventListener('close', () => { if (mealOpener?.isConnected) mealOpener.focus(); });
  // A click on the darkened area lands on the dialog itself, outside its box.
  mealDialog.addEventListener('click', event => {
    if (event.target !== mealDialog) return;
    const box = mealDialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) mealDialog.close();
  });
  el('meal-favorite').addEventListener('click', async event => {
    const heart = event.currentTarget, { id } = openRecipe;
    heart.disabled = true;
    el('meal-message').textContent = '';
    try {
      if (savedFavorites.has(id)) {
        await sendJSON(`/almond/favorites/${savedFavorites.get(id)}`, 'DELETE');
        savedFavorites.delete(id);
        el('meal-message').textContent = 'Removed from favorites.';
      } else {
        const { favorite_id: saved } = await sendJSON('/almond/favorites', 'POST', { recipe_id: id });
        savedFavorites.set(id, saved);
        el('meal-message').textContent = 'Saved to favorites. Not logged.';
      }
      syncHeart();
      await state().catch(e => error(e.message));
    } catch (e) { el('meal-message').textContent = e.message; }
    finally { heart.disabled = false; }
  });
  el('meal-log').addEventListener('click', async () => {
    try {
      const draft = await sendJSON(`/almond/recipes/${openRecipe.id}/draft`, 'GET');
      sessionStorage.setItem('almond-log-draft', JSON.stringify(draft));
      window.location.assign('/food');
    } catch (e) { el('meal-message').textContent = e.message; }
  });

  /* Conversations and modes */
  async function open(id) {
    chat().id = id ? Number(id) : null;
    favoriteId = null;
    liveGoalRow = null;
    el('messages').replaceChildren();
    el('recipes').replaceChildren();
    syncChatControls();
    if (!chat().id) return;
    const data = await sendJSON(`/almond/conversations/${chat().id}`, 'GET');
    data.messages.forEach(m => message(m.role, m.content));
    data.recipes.forEach(r => { if (r.recipe) recipeCard(r.recipe, r.recipe_id); else message('assistant', r.limitation); });
    // Newest first from the server, and only the newest can still be saved.
    [...(data.goal_actions || [])].reverse().forEach(goalRow);
  }

  document.querySelectorAll('input[name="almond-mode"]').forEach(input => input.addEventListener('change', () => {
    if (busy) return;
    chat().draft = el('question').value;
    mode = input.value;
    document.getElementById('almond').dataset.mode = mode;
    el('question').value = chat().draft;
    error('');
    fillHistory();
    open(chat().id).catch(e => error(e.message));
  }));

  el('history').addEventListener('change', () => open(el('history').value).catch(e => error(e.message)));
  el('new').addEventListener('click', () => { open(null); el('history').value = ''; error(''); el('question').focus(); });
  el('delete').addEventListener('click', () => {
    if (chat().id && window.confirm('Delete this conversation and its revisions? Saved favorites remain.')) {
      sendJSON(`/almond/conversations/${chat().id}`, 'DELETE').then(() => open(null)).then(state).catch(e => error(e.message));
    }
  });
  el('question').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      if (!el('send').disabled) el('form').requestSubmit();
    }
  });

  el('form').addEventListener('submit', async e => {
    e.preventDefault();
    const text = el('question').value.trim();
    // Without an allergy answer nothing leaves the page, however the form was submitted.
    if (busy || !text || !dietaryConfirmed || !available) return;
    busy = true;
    syncLock();
    error('');
    // Show the question right away. If the request fails, the text stays in the box to retry.
    const sent = message('user', text);
    const pending = loadingMessage();
    try {
      if (!chat().id) chat().id = (await sendJSON('/almond/conversations', 'POST', { mode })).conversation_id;
      const data = await sendJSON('/almond/messages', 'POST', {conversation_id: chat().id, text, request_id: crypto.randomUUID(), ...(favoriteId ? {favorite_id: favoriteId} : {})});
      pending.remove();
      message('assistant', data.reply);
      if (data.recipe) recipeCard(data.recipe, data.recipe_id).scrollIntoView({block: 'nearest'});
      if (data.goal_proposal) goalRow(data.goal_proposal);
      if (data.profile_url || data.memory_notice) el('messages').append(node('p', data.memory_notice || 'Confirm permanent restrictions in Profile.', 'almond-note'));
      el('question').value = '';
      favoriteId = null;
    } catch (err) {
      sent.remove();
      pending.remove();
      error(err.message);
    } finally {
      busy = false;
      syncLock(); // Ready for a retry before the refresh below finishes.
      await state().catch(err => error(err.message));
    }
  });

  async function saveMemory(clear) {
    const f = el('memory');
    await sendJSON('/almond/memory', 'POST', {
      confirmed: true,
      cuisines: clear ? [] : f.elements.cuisines.value.split('\n').map(s => s.trim()).filter(Boolean),
      cooking_minutes: clear || !f.elements.cooking_minutes.value ? null : Number(f.elements.cooking_minutes.value),
      food_budget: clear ? null : f.elements.food_budget.value.trim() || null,
    });
    await state();
    showNotice('Almond preferences saved.');
  }
  el('memory').addEventListener('submit', e => { e.preventDefault(); saveMemory(false).catch(err => error(err.message)); });
  el('clear-memory').addEventListener('click', () => saveMemory(true).catch(err => error(err.message)));

  state().catch(err => { el('status').textContent = 'Not available right now'; error(err.message); });
})();
