// Tap tiles for the log forms. The original fields stay in the form and remain the source of truth,
// so saving, editing, and drafts work exactly as they did.
(() => {
  const form = document.getElementById('log-form');
  if (!form) return;
  const stroke = 'fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"';
  const ICONS = {
    breakfast: `<path d="M6 34h36M24 8v6M9 15l4 4M39 15l-4 4" ${stroke}/><path d="M12 34a12 12 0 0 1 24 0Z" fill="currentColor"/>`,
    lunch: `<circle cx="24" cy="24" r="10" fill="currentColor"/><path d="M24 4v6M24 38v6M4 24h6M38 24h6M10 10l4 4M34 34l4 4M38 10l-4 4M14 34l-4 4" ${stroke}/>`,
    dinner: '<path d="M34 32A16 16 0 0 1 20 7a18 18 0 1 0 21 21 16 16 0 0 1-7 4Z" fill="currentColor"/>',
    snack: `<path d="M24 15c-5-5-16-3-16 10 0 10 7 18 11 18 2 0 3-1 5-1s3 1 5 1c4 0 11-8 11-18 0-13-11-15-16-10Z" fill="currentColor"/><path d="M24 14c0-5 3-8 8-9" ${stroke}/>`,
    Running: `<circle cx="30" cy="9" r="5" fill="currentColor"/><path d="M12 22l10-5 7 7 8 2M22 17l-3 13-9 9M24 28l8 7-2 9" ${stroke}/>`,
    Cycling: `<circle cx="11" cy="33" r="8" ${stroke}/><circle cx="37" cy="33" r="8" ${stroke}/><path d="M11 33l9-15h12l5 15M20 18l5 15H11M30 11h5" ${stroke}/>`,
    Walking: `<circle cx="24" cy="8" r="5" fill="currentColor"/><path d="M24 17v13l-6 13M24 30l7 13M15 25l9-8 9 6" ${stroke}/>`,
    Swimming: `<circle cx="33" cy="13" r="5" fill="currentColor"/><path d="M8 26l12-8 8 7M4 36c5-4 8-4 13 0s8 4 13 0 8-4 13 0" ${stroke}/>`,
  };
  const moon = 'M28 28A14 14 0 0 1 15 6a16 16 0 1 0 19 19 14 14 0 0 1-6 3Z';

  function group(label) {
    const box = createElement('div', null, 'tiles');
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', label);
    return box;
  }
  function tile(text, icon) {
    const button = createElement('button', null, 'tile');
    button.type = 'button';
    button.setAttribute('aria-pressed', 'false');
    if (icon) button.insertAdjacentHTML('afterbegin', `<svg viewBox="0 0 48 48" aria-hidden="true">${icon}</svg>`);
    button.append(createElement('span', text));
    return button;
  }

  // Tiles standing in for a select. The select keeps the value and stays for assistive tools and tests.
  function selectTiles(name, label) {
    const select = form.elements[name];
    if (!select) return;
    const box = group(label);
    const tiles = [...select.options].filter(option => option.value).map(option => {
      const button = tile(option.textContent, ICONS[option.value]);
      button.dataset.value = option.value;
      button.addEventListener('click', () => {
        select.value = select.value === option.value && !select.required ? '' : option.value;
        select.dispatchEvent(new Event('input', { bubbles: true }));
        select.dispatchEvent(new Event('change', { bubbles: true }));
        sync();
      });
      return button;
    });
    box.append(...tiles);
    const sync = () => tiles.forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.value === select.value));
      button.disabled = select.disabled;
    });
    select.classList.add('picked-by-tiles');
    select.tabIndex = -1;
    select.closest('label').after(box);
    new MutationObserver(sync).observe(select, { attributes: true, attributeFilter: ['disabled'] });
    for (const type of ['change', 'log-edit', 'log-reset']) form.addEventListener(type, () => requestAnimationFrame(sync));
    form.addEventListener('reset', () => requestAnimationFrame(sync));
    sync();
  }

  selectTiles('meal_type', 'Meal');
  selectTiles('intensity', 'Intensity');

  // Activity keeps its free text box, so the tiles only fill in the common names.
  const activity = form.elements.activity_name;
  if (activity) {
    const box = group('Common activities');
    const tiles = ['Walking', 'Running', 'Cycling', 'Swimming'].map(name => {
      const button = tile(name, ICONS[name]);
      button.addEventListener('click', () => {
        activity.value = name;
        activity.dispatchEvent(new Event('input', { bubbles: true }));
        sync();
      });
      return button;
    });
    const sync = () => tiles.forEach(button => button.setAttribute('aria-pressed', String(button.textContent === activity.value)));
    box.append(...tiles);
    activity.closest('.field-pair').before(box);
    for (const type of ['input', 'log-edit', 'log-reset']) form.addEventListener(type, sync);
    sync();
  }

  // Sleep quality as five moons.
  const quality = form.elements.sleep_quality;
  if (quality) {
    const box = createElement('div', null, 'moons');
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', 'Sleep quality');
    const moons = [1, 2, 3, 4, 5].map(score => {
      const button = createElement('button', null, 'moon');
      button.type = 'button';
      button.setAttribute('aria-label', `${score} of 5, ${quality.options[score].textContent.split(', ')[1]}`);
      button.insertAdjacentHTML('afterbegin', `<svg viewBox="0 0 40 40" aria-hidden="true"><path d="${moon}"/></svg>`);
      button.addEventListener('click', () => {
        quality.value = quality.value === String(score) ? '' : String(score);
        quality.dispatchEvent(new Event('input', { bubbles: true }));
        sync();
      });
      return button;
    });
    const sync = () => moons.forEach((button, i) => {
      button.classList.toggle('lit', Number(quality.value) > i);
      button.setAttribute('aria-pressed', String(Number(quality.value) === i + 1));
    });
    box.append(...moons);
    quality.classList.add('picked-by-tiles');
    quality.tabIndex = -1;
    quality.closest('label').after(box);
    for (const type of ['log-edit', 'log-reset', 'change']) form.addEventListener(type, sync);
    form.addEventListener('reset', () => requestAnimationFrame(sync));
    sync();
  }

  // Open the folded meal details when an edit needs them.
  const more = document.getElementById('meal-more');
  if (more) {
    form.addEventListener('log-edit', () => { more.open = true; });
    form.elements.eating_event_id.addEventListener('change', () => { more.open = true; });
  }
})();
