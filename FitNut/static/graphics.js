// The Activity climb and the Sleep dial, drawn from saved entries.
// Every figure here also appears as text in the entry list on the same page.
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const draw = (tag, attrs, parent, text) => {
    const el = document.createElementNS(NS, tag);
    for (const key in attrs) el.setAttribute(key, attrs[key]);
    if (text != null) el.textContent = text;
    if (parent) parent.append(el);
    return el;
  };
  const records = JSON.parse(document.getElementById('record-data')?.textContent || '[]');

  /* Activity: the weekly target is the summit, and each session moves you up the trail. */
  const ridgeHost = document.getElementById('ridge');
  if (ridgeHost) {
    const week = weekRange(new Date());
    const sessions = records.filter(item => {
      const when = new Date(item.performed_at);
      return when >= week.start && when < week.end;
    }).map(item => ({ name: item.activity_name, minutes: Number(item.duration_minutes) })).reverse();
    let target = null, total = sessions.reduce((sum, item) => sum + item.minutes, 0), drawnOnce = false;

    const render = () => {
      const w = Math.max(ridgeHost.clientWidth, 280), narrow = w < 620, h = narrow ? 300 : 400;
      const goal = target || Math.max(total, 150);
      ridgeHost.replaceChildren();
      const svg = draw('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img',
        'aria-label': `Mountain trail. ${target ? `The summit is your ${formatNumber(target)} minute weekly target.` : 'No weekly target is set.'} You have climbed ${formatNumber(total, 0)} minutes this week.` }, ridgeHost);
      const gradient = draw('linearGradient', { id: 'hill', x1: 0, y1: 0, x2: 0, y2: 1 }, draw('defs', {}, svg));
      draw('stop', { offset: 0, 'stop-color': '#a0632c' }, gradient);
      draw('stop', { offset: 1, 'stop-color': '#6b3c16' }, gradient);
      let seed = 41;
      const random = () => (seed = seed * 16807 % 2147483647) / 2147483647;
      const hills = (base, amp, n) => {
        let d = `M0 ${base}`;
        for (let i = 1; i <= n; i++) {
          const x = w * i / n, y = base + (random() - .5) * amp * 2;
          d += `Q${x - w / n / 2} ${y - amp * .5} ${x} ${y}`;
        }
        return `${d}V${h}H0Z`;
      };
      draw('path', { d: hills(h * .55, h * .09, 7), class: 'hill-far' }, svg);
      draw('path', { d: hills(h * .7, h * .07, 6), class: 'hill-near' }, svg);
      const peak = [w * .84, h * .15];
      draw('path', { d: `M-20 ${h}L${w * .2} ${h * .74}L${w * .36} ${h * .8}L${w * .58} ${h * .44}L${w * .66} ${h * .52}L${peak[0]} ${peak[1]}L${w + 20} ${h * .66}V${h}Z`, fill: 'url(#hill)' }, svg);
      const route = `M${w * .03} ${h * .97}C${w * .2} ${h * .92} ${w * .24} ${h * .86} ${w * .36} ${h * .88}S${w * .5} ${h * .68} ${w * .58} ${h * .6}S${w * .72} ${h * .5} ${w * .74} ${h * .38}S${w * .81} ${h * .26} ${peak[0]} ${peak[1]}`;
      draw('path', { d: route, class: 'trail-ahead' }, svg);
      const walked = draw('path', { d: route, class: 'trail-done' }, svg);
      const length = walked.getTotalLength(), done = length * Math.min(total / goal, 1);
      walked.setAttribute('stroke-dasharray', `${done} ${length + 10}`);
      if (!still && !drawnOnce) walked.animate([{ strokeDasharray: `0 ${length + 10}` }, { strokeDasharray: `${done} ${length + 10}` }], { duration: 1300, easing: 'ease-out' });
      const size = narrow ? 13 : 17;
      let at = 0;
      sessions.slice(0, -1).slice(-6).forEach((session, _, shown) => {
        at = sessions.slice(0, sessions.indexOf(session) + 1).reduce((sum, item) => sum + item.minutes, 0);
        if (at >= goal) return;
        const point = walked.getPointAtLength(length * at / goal);
        draw('circle', { cx: point.x, cy: point.y, r: 6, class: 'trail-stop' }, svg);
        if (!narrow || shown.length < 4) draw('text', { x: point.x, y: point.y + 26, 'text-anchor': 'middle', 'font-size': size, class: 'trail-label' }, svg, `${session.name.slice(0, 14)} ${formatNumber(session.minutes, 0)}`);
      });
      const me = walked.getPointAtLength(done);
      const marker = draw('circle', { cx: me.x, cy: me.y, r: 13, class: 'trail-me' }, svg);
      if (!still && !drawnOnce) {
        const from = walked.getPointAtLength(0);
        marker.animate([{ transform: `translate(${from.x - me.x}px, ${from.y - me.y}px)` }, { transform: 'none' }], { duration: 1300, easing: 'ease-out' });
      }
      draw('text', { x: Math.max(me.x - 22, narrow ? 104 : 150), y: Math.max(me.y - 26, 34), 'text-anchor': 'end', 'font-size': narrow ? 24 : 38, class: 'trail-now' }, svg, `${formatNumber(total, 0)} min`);
      if (target) {
        draw('path', { d: `M${peak[0]} ${peak[1]}V${peak[1] - 40}L${peak[0] + 28} ${peak[1] - 30}L${peak[0]} ${peak[1] - 20}`, class: 'trail-flag' }, svg);
        draw('text', { x: peak[0] - 10, y: peak[1] - 18, 'text-anchor': 'end', 'font-size': size + 6, class: 'trail-now' }, svg, formatNumber(target));
        const reached = total >= target, key = `fitnut-summit-${week.start.toISOString().slice(0, 10)}`;
        if (reached && !still && !drawnOnce && !sessionStorage.getItem(key)) {
          sessionStorage.setItem(key, '1');
          for (let i = 0; i < 26; i++) {
            const angle = Math.random() * Math.PI * 2, distance = 50 + Math.random() * 110;
            const petal = draw('ellipse', { cx: peak[0], cy: peak[1], rx: 7, ry: 4, class: i % 2 ? 'petal-a' : 'petal-b' }, svg);
            petal.animate([{ transform: 'translate(0,0)', opacity: 1 }, { transform: `translate(${Math.cos(angle) * distance}px, ${Math.sin(angle) * distance + 60}px) rotate(${Math.random() * 400}deg)`, opacity: 0 }],
              { duration: 1500 + Math.random() * 600, delay: 900, easing: 'ease-out', fill: 'both' });
          }
        }
      }
      drawnOnce = true;
    };
    render();
    sendJSON(summaryPath('/activity-logs', week), 'GET').then(({ totals, goals }) => {
      target = goals.weekly_activity_minutes == null ? null : Number(goals.weekly_activity_minutes);
      total = Number(totals.duration_minutes ?? total);
      drawnOnce = false;
      render();
    }).catch(() => {});
    let width = innerWidth;
    addEventListener('resize', () => { if (innerWidth !== width) { width = innerWidth; render(); } });
  }

  /* Sleep: up to 14 nights as rings on a 24-hour clock, with the latest on the outside. */
  const dialHost = document.getElementById('sleep-dial');
  if (dialHost) {
    const nights = records.map(night => {
      const start = new Date(night.sleep_start), end = new Date(night.sleep_end);
      const hour = start.getHours() + start.getMinutes() / 60;
      return { begin: hour > 12 ? hour - 24 : hour, length: (end - start) / 3600000, minutes: (end - start) / 60000, quality: night.sleep_quality, ended: end };
    }).filter(night => night.length > 0 && night.length < 24).slice(0, 14).reverse();
    if (nights.length) {
      const S = 560, C = S / 2;
      const svg = draw('svg', { viewBox: '-70 -4 700 568', role: 'img', 'aria-label': `${nights.length} recent ${nights.length === 1 ? 'night' : 'nights'} drawn as rings on a 24 hour clock. The latest was ${formatDuration(nights[nights.length - 1].minutes)}. Every night is also listed under Your entries.` }, dialHost);
      const at = (hour, r) => {
        const angle = hour / 24 * Math.PI * 2 - Math.PI / 2;
        return [C + Math.cos(angle) * r, C + Math.sin(angle) * r];
      };
      [[0, '12 AM'], [6, '6 AM'], [12, '12 PM'], [18, '6 PM']].forEach(([hour, label]) => {
        const [x, y] = at(hour, 256);
        draw('text', { x, y: y + 7, 'text-anchor': 'middle', 'font-size': 21, class: 'dial-hour' }, svg, label);
      });
      draw('circle', { cx: C, cy: C, r: 228, class: 'dial-rim' }, svg);
      const big = draw('text', { x: C, y: C + 6, 'text-anchor': 'middle', 'font-size': 50, class: 'dial-big' }, svg);
      const small = draw('text', { x: C, y: C + 36, 'text-anchor': 'middle', 'font-size': 21, class: 'dial-small' }, svg);
      const latest = nights[nights.length - 1];
      let picked = latest;
      const show = night => {
        big.textContent = formatDuration(night.minutes).replace(' min', '');
        small.textContent = night === latest ? 'latest night' : night.ended.toLocaleDateString([], { month: 'short', day: 'numeric' });
      };
      const step = 136 / Math.max(nights.length - 1, 13);
      nights.forEach((night, i) => {
        const r = 228 - 11 - (nights.length - 1 - i) * step * .98;
        const [x1, y1] = at(night.begin, r), [x2, y2] = at(night.begin + night.length, r);
        const arc = draw('path', { class: `ring${night === latest ? ' latest' : ''}`, d: `M${x1} ${y1}A${r} ${r} 0 ${night.length > 12 ? 1 : 0} 1 ${x2} ${y2}`, pathLength: 1 }, svg);
        arc.style.opacity = night.quality ? .3 + night.quality * .14 : .55;
        arc.addEventListener('pointerenter', () => show(night));
        arc.addEventListener('click', () => { picked = night; show(night); });
        if (!still) {
          arc.setAttribute('stroke-dasharray', '1 1');
          arc.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: 700, delay: i * 40, easing: 'ease-out', fill: 'backwards' });
        }
      });
      svg.addEventListener('pointerleave', () => show(picked));
      show(latest);
    }
  }
})();
