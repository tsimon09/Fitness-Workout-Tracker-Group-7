// Connects the 3D jar to a day of real food entries. Shared by Overview and Food.
window.FitNutDayJar = (host, savedProfile) => {
  const jar = FitNutNuts.mountJar(host);
  // The stones-or-nuts choice comes first, so nobody with a nut allergy sees nuts while it loads.
  const profile = (savedProfile || sendJSON('/profile-data', 'GET')).then(data => data.profile).catch(() => null);

  function drawLegend(avoid) {
    const list = document.getElementById('nut-legend');
    if (!list) return;
    list.replaceChildren(...FitNutNuts.legend(avoid).map(row => {
      const item = createElement('div');
      const icon = createElement('img');
      icon.src = `/static/nuts/${row.icon}.png`;
      icon.alt = '';
      item.append(icon, createElement('span', row.name), createElement('small', row.range));
      return item;
    }));
  }

  // The caller already has the day's summary, so this only reads the entries.
  return async function show(date, goals) {
    const { start, end } = dayRange(date);
    const [{ items }, saved] = await Promise.all([sendJSON('/food-logs', 'GET'), profile]);
    const avoid = FitNutNuts.avoidsNuts(saved);
    drawLegend(avoid);
    const foods = items.filter(item => {
      const when = new Date(item.logged_at);
      return when >= start && when < end;
    }).map(item => ({ id: item.food_log_id, name: item.food_name, cal: item.calories == null ? null : Number(item.calories) }));
    jar.setFoods(foods, goals.daily_calorie_target == null ? null : Number(goals.daily_calorie_target), avoid);
  };
};
