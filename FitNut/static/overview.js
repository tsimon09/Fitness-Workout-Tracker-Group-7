// Overview: reads the same endpoints as the Food, Activity, Sleep, and Profile pages.
// Each block loads on its own, so one failed request does not blank the whole page.
(() => {
  const now = new Date();
  const show = (id, text) => { document.getElementById(id).textContent = text; };
  const titleCase = code => code.charAt(0).toUpperCase() + code.slice(1).replaceAll('_', ' ');
  const SVG = 'http://www.w3.org/2000/svg';

  show('today-date', now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' }));

  function countUp(figure, value) {
    if (!value || matchMedia('(prefers-reduced-motion: reduce)').matches) { figure.textContent = formatNumber(value, 0); return; }
    const started = performance.now();
    const tick = time => {
      const progress = Math.min((time - started) / 1100, 1);
      figure.textContent = formatNumber(value * (1 - (1 - progress) ** 3), 0);
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // Food and the jar share one summary, and goals and the jar share one profile.
  const foodSummary = sendJSON(summaryPath('/food-logs', dayRange(now)), 'GET');
  const profileData = sendJSON('/profile-data', 'GET');

  async function loadFood() {
    const out = document.getElementById('today-totals');
    try {
      const { totals, goals } = await foodSummary;
      const eaten = totals.calories ?? 0;
      const target = goals.daily_calorie_target;
      const figure = createElement('p', '0', 'big-figure');
      const of = target == null ? 'calories, no target set'
        : `of ${formatNumber(target)} calories, ${formatNumber(Math.abs(target - eaten), 0)} ${eaten <= target ? 'left' : 'over'}`;
      const missing = totals.entries && ['calories', 'protein_g', 'carbs_g', 'fat_g'].some(key => totals[key + '_entered'] < totals.entries);
      out.replaceChildren(figure, createElement('p', of, 'of-target'), ...macroParts(totals));
      if (missing) out.append(createElement('p', 'Some entries have no nutrition, so these totals may be partial.', 'facts-note quiet'));
      countUp(figure, Number(eaten));
      const entries = totals.entries;
      show('food-status', entries ? `${entries} ${entries === 1 ? 'entry' : 'entries'} today` : 'Nothing logged today');
    } catch (error) {
      out.textContent = error.message;
      show('food-status', 'Totals unavailable');
    }
  }

  function drawRing(share) {
    const ring = document.getElementById('activity-ring');
    ring.replaceChildren();
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('viewBox', '0 0 80 80');
    svg.setAttribute('aria-hidden', 'true');
    for (const [cls, dash] of [['ring-back', '100 100'], ['ring-fill', `${share * 100} 100`]]) {
      const circle = document.createElementNS(SVG, 'circle');
      for (const [key, value] of Object.entries({ class: cls, cx: 40, cy: 40, r: 30, pathLength: 100, 'stroke-dasharray': dash, transform: 'rotate(-90 40 40)' })) circle.setAttribute(key, value);
      svg.append(circle);
    }
    ring.append(svg);
  }

  async function loadActivity() {
    try {
      const { totals, goals } = await sendJSON(summaryPath('/activity-logs', weekRange(now)), 'GET');
      const minutes = totals.duration_minutes ?? 0;
      const target = goals.weekly_activity_minutes;
      if (target != null) {
        const bar = document.getElementById('activity-progress');
        bar.max = target;
        bar.value = Math.min(minutes, target);
        show('activity-status', `${formatNumber(minutes, 0)} of ${formatNumber(target)} minutes this week`);
      } else show('activity-status', minutes ? `${formatNumber(minutes, 0)} minutes this week` : 'Nothing logged this week');
      drawRing(target ? Math.min(minutes / target, 1) : 0);
    } catch (error) { show('activity-status', 'Totals unavailable'); }
  }

  async function loadSleep() {
    try {
      const { items } = await sendJSON('/sleep-logs', 'GET');
      if (!items.length) { show('sleep-status', 'Nothing logged yet'); return; }
      const latest = items[0];
      const minutes = (new Date(latest.sleep_end) - new Date(latest.sleep_start)) / 60000;
      const ended = new Date(latest.sleep_end).toLocaleDateString([], { month: 'short', day: 'numeric' });
      show('sleep-status', `${formatDuration(minutes)} ending ${ended}${latest.sleep_quality ? `, quality ${latest.sleep_quality}/5` : ''}`);
    } catch (error) { show('sleep-status', 'Latest sleep unavailable'); }
  }

  async function loadGoals() {
    const list = document.getElementById('goal-summary');
    try {
      const { profile } = await profileData;
      // Most codes read correctly as words. These two match the labels in profiles.py GOALS.
      const goalLabels = { maintain: 'Maintain weight', gain_muscle: 'Build muscle' };
      const joined = values => values.length ? values.join(', ') : 'None listed';
      const allergies = {
        not_provided: 'Not provided',
        none_reported: 'None reported',
        listed: joined([...profile.allergens.map(titleCase), ...profile.other_allergies]),
      }[profile.allergy_status];
      const rows = [
        ['Fitness goal', profile.fitness_goal ? goalLabels[profile.fitness_goal] || titleCase(profile.fitness_goal) : 'Not set'],
        ['Daily calories', profile.daily_calorie_target == null ? 'Not set' : formatNumber(profile.daily_calorie_target)],
        ['Weekly activity', profile.weekly_activity_minutes == null ? 'Not set' : `${formatNumber(profile.weekly_activity_minutes)} minutes`],
        ['Allergies', allergies],
        ['Intolerances', joined(profile.intolerances)],
        ['Food preferences', joined(profile.preferences)],
      ];
      list.replaceChildren(...rows.map(([label, value]) => {
        const row = document.createElement('div');
        if (label === 'Allergies') row.className = 'restriction-key';
        row.append(createElement('dt', label), createElement('dd', value));
        return row;
      }));
    } catch (error) {
      const row = document.createElement('div');
      row.append(createElement('dt', 'Unavailable'), createElement('dd', error.message));
      list.replaceChildren(row);
    }
  }

  loadFood();
  loadActivity();
  loadSleep();
  loadGoals();
  const showJar = FitNutDayJar(document.getElementById('jar-stage'), profileData);
  foodSummary.then(({ goals }) => showJar(now, goals)).catch(() => {});
})();
