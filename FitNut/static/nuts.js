// FitNut's 3D objects: Almond, the nuts, and the jar that fills with the day's food.
// The models are generated here, so there are no downloaded assets to license.
// Pages keep working without WebGL, because the numbers and lists around these are plain HTML.
window.FitNutNuts = (() => {
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const make = (tag, props = {}, parent) => {
    const el = Object.assign(document.createElement(tag), props);
    if (parent) parent.append(el);
    return el;
  };
  const fmt = n => Math.round(n).toLocaleString();
  const webgl = typeof THREE !== 'undefined' && (() => {
    try { return !!document.createElement('canvas').getContext('webgl'); } catch (_) { return false; }
  })();

  // Calorie bands choose the nut. Size within a band still follows the exact calories.
  const BANDS = [[100, 'pistachio', 'Pistachio', 'under 100'], [200, 'hazelnut', 'Hazelnut', '100 to 199'], [400, 'acorn', 'Acorn', '200 to 399'],
    [600, 'walnut', 'Walnut', '400 to 599'], [Infinity, 'pecan', 'Pecan', '600 and up']];
  const PEBBLES = ['Tiny pebble', 'Small pebble', 'Pebble', 'Big pebble', 'Boulder'];
  const PEBBLE_TINTS = ['#d6cfc8', '#c0b7ae', '#a79c92', '#8b7f75', '#6f645b'];

  // Decoration only: anyone who lists peanuts, tree nuts or a named nut sees stones instead.
  // A profile that could not be read counts as avoiding nuts.
  const NUT_WORDS = /\b(pea)?nuts?\b|almond|pecan|cashew|pistachio|macadamia|brazil|hazel|walnut|pine ?nut|coconut|acorn|chestnut/i;
  const avoidsNuts = profile => !profile || (profile.allergens || []).some(code => code === 'peanut' || code === 'tree_nuts')
    || (profile.other_allergies || []).some(item => NUT_WORDS.test(item));
  const speciesOf = (cal, avoid) => {
    if (cal == null) return 'ghost';
    const i = BANDS.findIndex(band => cal < band[0]);
    return avoid ? `pebble${i}` : BANDS[i][1];
  };
  const legend = avoid => BANDS.map((band, i) => ({ icon: avoid ? `pebble${i}` : band[1], name: avoid ? PEBBLES[i] : band[2], range: band[3] }));

  const hash = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };
  function noise(x, y, z) {
    const ix = Math.floor(x), iy = Math.floor(y), iz = Math.floor(z);
    const fx = x - ix, fy = y - iy, fz = z - iz;
    const u = fx * fx * (3 - 2 * fx), v = fy * fy * (3 - 2 * fy), w = fz * fz * (3 - 2 * fz);
    const lerp = (a, b, t) => a + (b - a) * t;
    return lerp(
      lerp(lerp(hash(ix, iy, iz), hash(ix + 1, iy, iz), u), lerp(hash(ix, iy + 1, iz), hash(ix + 1, iy + 1, iz), u), v),
      lerp(lerp(hash(ix, iy, iz + 1), hash(ix + 1, iy, iz + 1), u), lerp(hash(ix, iy + 1, iz + 1), hash(ix + 1, iy + 1, iz + 1), u), v), w);
  }
  const fbm = (x, y, z) => noise(x, y, z) * .55 + noise(x * 2.1, y * 2.1, z * 2.1) * .3 + noise(x * 4.3, y * 4.3, z * 4.3) * .15;
  const lin = hex => new THREE.Color(hex).convertSRGBToLinear();

  // Bends a sphere with a function that returns its new position and colour.
  function sculpt(fn, w = 72, h = 54, args = []) {
    const geo = new THREE.SphereGeometry(1, w, h, ...args);
    const pos = geo.attributes.position, colors = new Float32Array(pos.count * 3);
    const v = new THREE.Vector3();
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i);
      const { p, c } = fn(v.clone());
      pos.setXYZ(i, p.x, p.y, p.z);
      colors.set([c.r, c.g, c.b], i * 3);
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    return geo;
  }
  const mix = (a, b, t) => a.clone().lerp(b, Math.min(Math.max(t, 0), 1));
  const paint = (geo, roughness, extra = {}) => new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness, metalness: 0, ...extra }));
  const kit = {};
  function buildKit() {
    const walnutD = lin('#6f4a26'), walnutL = lin('#c59a64');
    kit.walnut = sculpt(q => {
      const ridge = 1 - Math.abs(fbm(q.x * 3 + 5, q.y * 3, q.z * 3) * 2 - 1);
      const seam = Math.exp(-((q.x / .05) ** 2));
      const r = .9 + ridge * .1 - seam * .1 + seam * .03 * Math.sin(q.y * 40);
      return { p: q.multiplyScalar(r), c: mix(walnutD, walnutL, ridge * ridge - seam) };
    }, 110, 80);
    const hazelD = lin('#6a3a18'), hazelL = lin('#a4622c'), hazelB = lin('#e5c79c');
    kit.hazelnut = sculpt(q => {
      const lon = Math.atan2(q.x, q.z), base = q.y < -.52 + fbm(q.x * 4, 0, q.z * 4) * .12;
      const stripe = .5 + .5 * Math.sin(lon * 34 + fbm(q.x * 2, q.y * 2, q.z * 2) * 7);
      const r = 1 + .16 * Math.max(q.y, 0) ** 7;
      const c = base ? hazelB : mix(hazelD, hazelL, stripe);
      return { p: new THREE.Vector3(q.x * .92, q.y * r * .95 - .03, q.z * .92), c };
    });
    const pistaL = lin('#e4cfa3'), pistaD = lin('#a5824f'), pistaIn = lin('#6c7d3a');
    kit.pistachio = sculpt(q => {
      const open = Math.max(q.y - .15, 0) * Math.exp(-((q.x / .12) ** 2));
      const fleck = noise(q.x * 14, q.y * 14, q.z * 14);
      const p = new THREE.Vector3(q.x * .68 * (1 - open * .5), q.y, q.z * .68 * (1 - open * .9));
      return { p, c: open > .12 ? pistaIn : mix(pistaD, pistaL, .55 + fleck * .6) };
    });
    const acornD = lin('#6d3d17'), acornL = lin('#a96d32');
    kit.acornBody = sculpt(q => {
      const down = Math.max(-q.y, 0);
      const taper = 1 - .32 * down ** 3;
      const streak = fbm(Math.atan2(q.x, q.z) * 7, q.y * .6, 3);
      return { p: new THREE.Vector3(q.x * .68 * taper, q.y * .82 - .16 - (down ** 6) * .08, q.z * .68 * taper), c: mix(acornD, acornL, streak * 1.3) };
    });
    const capD = lin('#4c3219'), capL = lin('#8e6b3f');
    kit.acornCap = sculpt(q => {
      const lon = Math.atan2(q.x, q.z), lat = Math.acos(q.y);
      const scale = Math.abs(Math.sin(lon * 11 + Math.floor(lat * 7) * 1.5) * Math.sin(lat * 22));
      return { p: new THREE.Vector3(q.x * .76 * (1 + scale * .05), q.y * .5 + .2, q.z * .76 * (1 + scale * .05)), c: mix(capD, capL, scale) };
    }, 72, 40, [0, Math.PI * 2, 0, Math.PI * .56]);
    const pecanD = lin('#3b2110'), pecanL = lin('#b5793c');
    kit.pecan = sculpt(q => {
      const lon = Math.atan2(q.x, q.z);
      const streak = fbm(lon * 3.2, q.y * 1.3 + 4, 2) * 1.5 + .5 * Math.sin(lon * 5 + q.y * 2);
      const taper = 1 - .3 * Math.abs(q.y) ** 3;
      return { p: new THREE.Vector3(q.x * .6 * taper, q.y * (1 + .05 * Math.abs(q.y) ** 8), q.z * .6 * taper), c: mix(pecanD, pecanL, streak - .15) };
    }, 90, 70);
    kit.ghost = new THREE.SphereGeometry(.8, 32, 24);
    kit.pebble = sculpt(q => {
      const lump = fbm(q.x * 1.4 + 3, q.y * 1.4, q.z * 1.4), fleck = noise(q.x * 26, q.y * 26, q.z * 26);
      const r = .9 + lump * .12;
      return { p: new THREE.Vector3(q.x * r * 1.04, q.y * r * .72, q.z * r), c: new THREE.Color().setScalar(.74 + fleck * .26 + lump * .12) };
    });
  }
  function makeNut(species) {
    const group = new THREE.Group();
    const add = mesh => { mesh.castShadow = mesh.receiveShadow = true; group.add(mesh); return mesh; };
    if (species.startsWith('pebble')) add(paint(kit.pebble, .55, { color: lin(PEBBLE_TINTS[Number(species.slice(6))]) }));
    if (species === 'walnut') add(paint(kit.walnut, .78));
    if (species === 'hazelnut') add(paint(kit.hazelnut, .32));
    if (species === 'pistachio') add(paint(kit.pistachio, .6));
    if (species === 'pecan') add(paint(kit.pecan, .38));
    if (species === 'acorn') {
      add(paint(kit.acornBody, .28)); add(paint(kit.acornCap, .85));
      const stem = add(new THREE.Mesh(new THREE.CylinderGeometry(.045, .08, .24, 12), new THREE.MeshStandardMaterial({ color: lin('#4c3219'), roughness: .9 })));
      stem.position.y = .8;
    }
    if (species === 'ghost') {
      group.add(new THREE.Mesh(kit.ghost, new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: .42, roughness: .2 })));
      group.add(new THREE.Mesh(kit.ghost, new THREE.MeshBasicMaterial({ color: lin('#5f3514'), wireframe: true, transparent: true, opacity: .22 })));
    }
    return group;
  }
  function lights(scene) {
    scene.add(new THREE.HemisphereLight(lin('#fff5f0'), lin('#d9a08f'), .85));
    const key = new THREE.DirectionalLight(lin('#fff4e8'), 1.25);
    key.position.set(-.55, 1, 1.1);
    scene.add(key);
    const rim = new THREE.DirectionalLight(lin('#ffd9d6'), .35);
    rim.position.set(1, -.2, .6);
    scene.add(rim);
    return key;
  }
  function renderer(canvas, opts = {}) {
    const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, ...opts });
    r.outputEncoding = THREE.sRGBEncoding;
    r.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    return r;
  }

  function almondParts() {
    const pts = [];
    for (let i = 0; i <= 48; i++) {
      const t = i / 48 * Math.PI;
      pts.push(new THREE.Vector2(Math.max(.86 * Math.sin(t) * Math.sin(t / 2) ** .62, .0001), Math.cos(t)));
    }
    const geo = new THREE.LatheGeometry(pts, 96);
    const canvas = make('canvas', { width: 1024, height: 512 });
    const c = canvas.getContext('2d');
    const grad = c.createLinearGradient(0, 0, 0, 512);
    grad.addColorStop(0, '#9c5f2a'); grad.addColorStop(.5, '#a9692f'); grad.addColorStop(1, '#8a4f1f');
    c.fillStyle = grad; c.fillRect(0, 0, 1024, 512);
    let seed = 11; const rnd = () => (seed = seed * 16807 % 2147483647) / 2147483647;
    for (let i = 0; i < 900; i++) {
      const x = rnd() * 1024, y = rnd() * 512, len = 30 + rnd() * 110;
      c.strokeStyle = rnd() > .5 ? `rgba(70,35,10,${.12 + rnd() * .25})` : `rgba(215,160,105,${.08 + rnd() * .2})`;
      c.lineWidth = .7 + rnd() * 2.6;
      c.beginPath(); c.moveTo(x, y); c.quadraticCurveTo(x + (rnd() - .5) * 8, y + len / 2, x + (rnd() - .5) * 6, y + len); c.stroke();
    }
    const map = new THREE.CanvasTexture(canvas);
    map.encoding = THREE.sRGBEncoding; map.wrapS = THREE.RepeatWrapping;
    const bump = new THREE.CanvasTexture(canvas); bump.wrapS = THREE.RepeatWrapping;
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map, bumpMap: bump, bumpScale: .035, roughness: .62 }));
    return mesh;
  }
  function makeAlmond() {
    const group = new THREE.Group();
    const body = almondParts();
    body.scale.set(1, 1, .68);
    body.castShadow = true;
    group.add(body);
    const white = new THREE.MeshStandardMaterial({ color: lin('#fff8f2'), roughness: .25 });
    const dark = new THREE.MeshStandardMaterial({ color: lin('#20130a'), roughness: .1 });
    const eyes = [-.25, .25].map(x => {
      const eye = new THREE.Group();
      const ball = new THREE.Mesh(new THREE.SphereGeometry(.135, 32, 24), white);
      ball.scale.z = .45;
      const pupil = new THREE.Mesh(new THREE.SphereGeometry(.068, 24, 18), dark);
      pupil.position.z = .05; pupil.scale.z = .5;
      eye.add(ball, pupil);
      eye.position.set(x, .08, .56);
      eye.rotation.y = x * .9;
      eye.userData.pupil = pupil;
      group.add(eye);
      return eye;
    });
    const smile = new THREE.Mesh(new THREE.TorusGeometry(.12, .017, 10, 28, Math.PI), dark);
    smile.rotation.z = Math.PI; smile.position.set(0, -.14, .585);
    group.add(smile);
    group.userData = { eyes, smile };
    return group;
  }

  let kitBuilt = false;
  function ensureKit() { if (!kitBuilt) { buildKit(); kitBuilt = true; } }

  function mountAlmond(canvas) {
    if (!webgl) return false;
    ensureKit();
    const r = renderer(canvas);
    const scene = new THREE.Scene();
    lights(scene);
    const camera = new THREE.PerspectiveCamera(32, 1, .1, 50);
    const almond = makeAlmond();
    scene.add(almond);
    const orbiters = BANDS.flatMap((band, i) => [0, 1].map(k => {
      const nut = makeNut(band[1]);
      const o = { nut, radius: 1.45 + (i % 3) * .28 + k * .2, speed: (.18 + i * .03) * (k ? -1 : 1), phase: i * 1.4 + k * 3, tilt: .35 + i * .12, size: .1 + [0, .03, .05, .07, .11][i] };
      nut.scale.setScalar(o.size);
      scene.add(nut);
      return o;
    }));
    let spin = -.35, velocity = 0, hop = 0, dragging = false, lastX = 0, moved = 0, look = [0, 0], lastDraw = 0;
    const fit = () => {
      const b = canvas.getBoundingClientRect();
      r.setSize(b.width, b.height, false);
      camera.aspect = b.width / b.height;
      camera.position.z = camera.aspect < 1 ? 8.6 : 7.2;
      camera.updateProjectionMatrix();
    };
    fit();
    addEventListener('resize', fit);
    canvas.addEventListener('pointerdown', e => { dragging = true; lastX = e.clientX; moved = 0; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', e => {
      if (!dragging) return;
      const d = e.clientX - lastX; lastX = e.clientX; moved += Math.abs(d);
      spin += d * .012; velocity = d * .012;
    });
    const up = () => { if (dragging && moved < 5) { hop = 1; velocity = .34; } dragging = false; };
    canvas.addEventListener('pointerup', up);
    canvas.addEventListener('pointercancel', () => { dragging = false; });
    addEventListener('pointermove', e => {
      const b = canvas.getBoundingClientRect();
      look = [Math.max(-1, Math.min(1, (e.clientX - b.left - b.width / 2) / b.width * 2)), Math.max(-1, Math.min(1, -(e.clientY - b.top - b.height / 2) / b.height * 2))];
    });
    const tick = time => {
      if (!canvas.isConnected) return;
      {
        if (still && !dragging && time - lastDraw < 200) return;
        lastDraw = time;
        const t = time / 1000;
        if (!dragging) { spin += velocity; velocity *= .95; if (!still) spin += (Math.sin(t * .6) * .22 - .1 - spin % (Math.PI * 2)) * .012; }
        hop *= .93;
        almond.rotation.y = spin;
        almond.rotation.x = -look[1] * .12;
        almond.position.y = (still ? 0 : Math.sin(t * 1.3) * .05) + Math.sin(hop * Math.PI) * .32;
        almond.userData.eyes.forEach(eye => {
          eye.userData.pupil.position.x = look[0] * .05;
          eye.userData.pupil.position.y = look[1] * .05;
          const closing = !still && (t % 4.2) < .12;
          eye.scale.y += ((closing ? .08 : 1) - eye.scale.y) * .5;
        });
        for (const o of orbiters) {
          const a = o.phase + (still ? 0 : t * o.speed);
          o.nut.position.set(Math.cos(a) * o.radius * .86, Math.sin(a) * o.radius * Math.sin(o.tilt) + .05, Math.sin(a) * o.radius * Math.cos(o.tilt));
          o.nut.rotation.set(t * .5 + o.phase, t * .4, 0);
        }
        r.render(scene, camera);
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    return true;
  }

  function mountJar(host) {
    const canvas = make('canvas', { id: 'jar' }, host);
    canvas.setAttribute('role', 'img');
    const tip = make('div', { className: 'tip', hidden: true }, host);
    const hint = make('p', { className: 'hint jar-hint', textContent: 'Grab one and throw it.' }, host);
    const data = { foods: [], target: null, avoid: true };
    const view = { setFoods() {} };
    const jarLabel = () => {
      const named = data.foods.slice(0, 12).map(f => f.cal == null ? `${f.name}, no calories entered` : `${f.name}, ${fmt(f.cal)} calories`).join('; ');
      return `Glass jar holding ${data.foods.length} ${data.avoid ? 'pebbles' : 'nuts'}, one per food. The jar is full at your calorie target. ${named}`;
    };
    if (!webgl) { canvas.hidden = true; hint.hidden = true; return view; }
    ensureKit();
    const r = renderer(canvas);
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
    const scene = new THREE.Scene();
    const key = lights(scene);
    key.castShadow = true; key.shadow.mapSize.set(1024, 1024);
    const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, -2000, 2000);
    cam.position.z = 800;
    let W = 0, H = 0, poly = [], jarW = 0, jarTop = 0, jarBottom = 0, glass = null;
    const bodies = new Map();
    let held = null, pointer = null, idle = 0;
    const MAX_SPEED = 13, MAX_HELD = 11;

    function buildJar() {
      if (glass) { scene.remove(glass); glass.traverse(o => o.geometry && o.geometry.dispose()); }
      glass = new THREE.Group();
      const corner = jarW * .22;
      const profile = [];
      for (let i = 0; i <= 10; i++) {
        const a = i / 10 * Math.PI / 2;
        profile.push(new THREE.Vector2(jarW - corner + Math.sin(a) * corner, -(jarBottom - corner + Math.cos(a) * corner)));
      }
      profile.unshift(new THREE.Vector2(.01, -jarBottom));
      for (let i = 1; i <= 6; i++) profile.push(new THREE.Vector2(jarW, -(jarBottom - corner - (jarBottom - corner - jarTop) * i / 6)));
      const shell = new THREE.Mesh(new THREE.LatheGeometry(profile, 64), new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: .2, roughness: .06, side: THREE.BackSide, depthWrite: false }));
      shell.renderOrder = -1;
      glass.add(shell);
      const outline = [...profile].reverse().map(p => new THREE.Vector3(p.x, p.y, 0)).concat(profile.map(p => new THREE.Vector3(-p.x, p.y, 0)));
      const tube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(outline, false, 'centripetal'), 200, 3, 8, false), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: .9 }));
      tube.renderOrder = 3;
      glass.add(tube);
      const lip = new THREE.Mesh(new THREE.CylinderGeometry(jarW + 11, jarW + 11, 17, 64), new THREE.MeshStandardMaterial({ color: lin('#8a4f1f'), roughness: .5 }));
      lip.position.y = -jarTop - 2; lip.renderOrder = 3;
      glass.add(lip);
      for (const [x, w, o] of [[-jarW * .72, 12, .2], [-jarW * .54, 4, .13]]) {
        const shine = new THREE.Mesh(new THREE.PlaneGeometry(w, (jarBottom - jarTop) * .68), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: o, depthTest: false }));
        shine.position.set(x, -(jarTop + (jarBottom - jarTop) * .45), 300); shine.renderOrder = 4;
        glass.add(shine);
      }
      scene.add(glass);
    }

    function layout() {
      const b = canvas.getBoundingClientRect();
      if (!b.width || !b.height) return false;
      if (b.width === W && b.height === H) return true;
      const dx = (b.width - W) / 2;
      W = b.width; H = b.height;
      r.setSize(W, H, false);
      cam.left = -W / 2; cam.right = W / 2; cam.top = H / 2; cam.bottom = -H / 2;
      cam.position.y = -H / 2; cam.updateProjectionMatrix();
      key.target.position.set(0, -H / 2, 0); key.position.set(-W * .4, H * .2, 700); scene.add(key.target);
      Object.assign(key.shadow.camera, { left: -W, right: W, top: H, bottom: -H, near: 1, far: 3000 });
      key.shadow.camera.updateProjectionMatrix();
      jarW = Math.min(W * .42, 180); jarTop = 62; jarBottom = H - 14;
      const corner = jarW * .22, pts = [[-jarW, -6000], [jarW, -6000]];
      for (let i = 0; i <= 8; i++) { const a = i / 8 * Math.PI / 2; pts.push([jarW - corner + Math.cos(a) * corner, jarBottom - corner + Math.sin(a) * corner]); }
      for (let i = 0; i <= 8; i++) { const a = i / 8 * Math.PI / 2; pts.push([-(jarW - corner) - Math.sin(a) * corner, jarBottom - corner + Math.cos(a) * corner]); }
      poly = pts.map((p, i) => {
        const q = pts[(i + 1) % pts.length];
        let nx = -(q[1] - p[1]), ny = q[0] - p[0];
        const len = Math.hypot(nx, ny) || 1; nx /= len; ny /= len;
        if ((0 - p[0]) * nx + (H / 2 - p[1]) * ny < 0) { nx = -nx; ny = -ny; }
        return [p[0], p[1], nx, ny];
      });
      buildJar();
      idle = 0;
      return true;
    }

    function radius(food) {
      const area = 2 * jarW * (jarBottom - jarTop);
      const target = data.target || 2200; // Only sets the scale when no target is saved.
      if (food.cal == null) return Math.max(18, jarW * .15);
      return Math.max(13, Math.min(jarW * .8, Math.sqrt(food.cal * .62 * area / target / Math.PI)));
    }

    function step() {
      for (const b of bodies.values()) {
        b.hit = false;
        if (b === held && pointer) {
          // A held nut follows the pointer at a limited speed and stays inside the jar.
          const tx = Math.max(-(jarW - b.r), Math.min(jarW - b.r, pointer[0]));
          const ty = Math.max(b.r, Math.min(jarBottom - b.r, pointer[1]));
          const dx = tx - b.x, dy = ty - b.y, d = Math.hypot(dx, dy) || 1, move = Math.min(d * .35, MAX_HELD);
          b.px = b.x; b.py = b.y;
          b.x += dx / d * move; b.y += dy / d * move;
        } else {
          const vx = (b.x - b.px) * .99, vy = (b.y - b.py) * .99;
          b.px = b.x; b.py = b.y;
          b.x += vx; b.y += vy + .42;
        }
      }
      const list = [...bodies.values()];
      for (let pass = 0; pass < 5; pass++) {
        for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
          const a = list[i], b = list[j];
          const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || .01, gap = a.r + b.r - d;
          if (gap > 0) {
            const nx = dx / d, ny = dy / d;
            // The held nut mostly pushes, so the pile moves aside instead of squeezing it back and forth.
            const wa = a === held ? .12 : b === held ? .88 : .5, wb = 1 - wa;
            a.x -= nx * gap * wa; a.y -= ny * gap * wa; b.x += nx * gap * wb; b.y += ny * gap * wb;
            a.hit = b.hit = true;
          }
        }
        for (const b of list) for (const [px, py, nx, ny] of poly) {
          const d = (b.x - px) * nx + (b.y - py) * ny;
          if (d < b.r) { b.x += nx * (b.r - d); b.y += ny * (b.r - d); b.hit = true; }
        }
      }
      let energy = 0;
      for (const b of list) {
        // An invisible ceiling keeps a thrown nut on screen. New nuts fall in from above it.
        if (b.y >= b.r) b.entered = true;
        if (b.entered && b.y < b.r) { b.y = b.r; b.py = b.y; }
        // Corrections become velocity here, so cap them and lose energy on contact.
        let vx = b.x - b.px, vy = b.y - b.py;
        const speed = Math.hypot(vx, vy);
        const cap = b === held ? MAX_HELD : b.entered ? MAX_SPEED : 30;
        if (speed > cap) { vx *= cap / speed; vy *= cap / speed; b.x = b.px + vx; b.y = b.py + vy; }
        if (b.hit) { vx *= .82; vy *= .82; }
        if (b.hit && Math.hypot(vx, vy) < .06) { vx = 0; vy = 0; }
        b.px = b.x - vx; b.py = b.y - vy;
        energy += Math.abs(vx) + Math.abs(vy);
        b.spin *= .97;
        const roll = Math.max(-.12, Math.min(.12, vx / b.r * .8));
        b.mesh.rotation.z -= roll;
        b.mesh.rotation.x += b.spin + Math.max(-.05, Math.min(.05, vy / b.r * .2));
        b.mesh.rotation.y += b.spin * .6;
        b.r += (b.goal - b.r) * .12;
        b.mesh.scale.setScalar(b.r);
        b.mesh.position.set(b.x, -b.y, 0);
        if (window.__jar && b.entered && b.lastX != null) window.__jar.peak = Math.max(window.__jar.peak || 0, Math.hypot(b.x - b.lastX, b.y - b.lastY));
        b.lastX = b.x; b.lastY = b.y;
      }
      return energy;
    }

    view.sync = (fresh = true) => {
      if (!layout()) return;
      const ids = new Set(data.foods.map(f => f.id));
      for (const [id, b] of bodies) if (!ids.has(id)) { scene.remove(b.mesh); bodies.delete(id); }
      let queued = 0;
      for (const food of data.foods) {
        const existing = bodies.get(food.id);
        const goal = radius(food);
        if (existing) { existing.goal = goal; continue; }
        const mesh = makeNut(speciesOf(food.cal, data.avoid));
        mesh.rotation.set(Math.random() * 6, Math.random() * 6, Math.random() * 6);
        scene.add(mesh);
        const x = (Math.random() - .5) * Math.max(jarW - goal, 10);
        const y = -goal - queued * 130 - 30;
        queued++;
        bodies.set(food.id, { food, mesh, r: goal, goal, x, y, px: x, py: y - 2, spin: fresh ? .06 * (Math.random() - .5) : 0 });
      }
      idle = 0;
      canvas.setAttribute('aria-label', jarLabel());
      if (still) { for (let i = 0; i < 1500; i++) step(); r.render(scene, cam); }
    };
    view.redrop = () => { for (const b of bodies.values()) scene.remove(b.mesh); bodies.clear(); view.sync(); };
    view.resize = () => { view.sync(false); };
    view.tick = () => {
      if (W === 0) { if (!layout()) return; view.sync(); }
      if (idle > 90 && !held) return;
      const e = step() + step();
      idle = e < .05 * Math.max(bodies.size, 1) ? idle + 1 : 0;
      r.render(scene, cam);
    };
    // Only the browser tests switch this on.
    if (window.__fitnutJarTest) window.__jar = {
      bodies: () => [...bodies.values()].map(b => ({ id: b.food.id, x: b.x, y: b.y, px: b.px, py: b.py, r: b.r, rz: b.mesh.rotation.z })),
      size: () => ({ W, H, jarW, jarTop, jarBottom })
    };
    const local = e => { const b = canvas.getBoundingClientRect(); return [e.clientX - b.left - b.width / 2, e.clientY - b.top]; };
    const nearest = p => {
      let hit = null, best = Infinity;
      for (const b of bodies.values()) { const d = Math.hypot(b.x - p[0], b.y - p[1]); if (d < b.r + 6 && d < best) { best = d; hit = b; } }
      return hit;
    };
    const label = b => b.food.cal == null ? `${b.food.name}, no calories entered` : `${b.food.name}, ${fmt(b.food.cal)} calories`;
    const showTip = (b, p) => { tip.hidden = !b; if (b) { tip.textContent = label(b); tip.style.left = `${Math.max(90, Math.min(W - 90, p[0] + W / 2))}px`; tip.style.top = `${Math.max(36, p[1])}px`; } };
    canvas.addEventListener('pointerdown', e => {
      const p = local(e), hit = nearest(p);
      if (hit) { held = hit; pointer = p; canvas.setPointerCapture(e.pointerId); idle = 0; showTip(hit, p); }
    });
    canvas.addEventListener('pointermove', e => {
      const p = local(e);
      if (held) { pointer = p; showTip(held, p); idle = 0; } else showTip(nearest(p), p);
    });
    const drop = () => { held = null; pointer = null; idle = 0; tip.hidden = true; };
    canvas.addEventListener('pointerup', drop);
    canvas.addEventListener('pointercancel', drop);
    canvas.addEventListener('pointerleave', () => { if (!held) tip.hidden = true; });
    // On a phone, touching a nut grabs it. Touching the empty jar still scrolls the page.
    canvas.addEventListener('touchstart', e => { if (nearest(local(e.touches[0]))) e.preventDefault(); }, { passive: false });
    view.setFoods = (foods, target, avoid) => {
      const swapped = avoid !== data.avoid;
      Object.assign(data, { foods, target, avoid });
      if (swapped) view.redrop(); else view.sync();
    };
    // The empty jar shows straight away, and the nuts drop in once the food has loaded.
    const loop = time => {
      view.tick(time);
      if (canvas.isConnected) requestAnimationFrame(loop);
    };
    if (!still) requestAnimationFrame(loop);
    new ResizeObserver(() => view.resize()).observe(canvas);
    return view;
  }

  // Used by scripts/render_nut_icons.cjs to draw the small icons in static/nuts.
  function renderIcon(species) {
    ensureKit();
    const canvas = make('canvas');
    const r = renderer(canvas, { preserveDrawingBuffer: true });
    r.setPixelRatio(1); r.setSize(144, 144, false);
    const object = species === 'almond' ? makeAlmond() : makeNut(species);
    object.rotation.set(species === 'almond' ? 0 : .25, species === 'almond' ? -.2 : -.5, species === 'almond' ? 0 : .22);
    const scene = new THREE.Scene(); lights(scene); scene.add(object);
    const zoom = species === 'almond' ? 1.15 : 1.25;
    const cam = new THREE.OrthographicCamera(-zoom, zoom, zoom, -zoom, -5, 5);
    cam.position.set(0, 0, 3);
    r.render(scene, cam);
    return canvas.toDataURL('image/png');
  }

  return { webgl, avoidsNuts, speciesOf, legend, mountAlmond, mountJar, renderIcon };
})();
