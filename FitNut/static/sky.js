// The live blossom sky behind every page. It turns to night on Sleep.
// Decorative only: without WebGL the page keeps its plain background.
(() => {
  const canvas = document.getElementById('sky');
  const gl = canvas?.getContext('webgl', { antialias: false, powerPreference: 'low-power' });
  if (!gl) return;
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const night = document.body.classList.contains('night') ? 1 : 0;

  const shader = (type, source) => {
    const compiled = gl.createShader(type);
    gl.shaderSource(compiled, source);
    gl.compileShader(compiled);
    return compiled;
  };
  const program = gl.createProgram();
  gl.attachShader(program, shader(gl.VERTEX_SHADER, 'attribute vec2 p; varying vec2 v; void main(){ v = p*.5+.5; gl_Position = vec4(p,0.,1.); }'));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, `
    precision mediump float; varying vec2 v; uniform float t, night; uniform vec2 res;
    float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float n(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.-2.*f);
      return mix(mix(h(i), h(i+vec2(1,0)), f.x), mix(h(i+vec2(0,1)), h(i+vec2(1,1)), f.x), f.y); }
    float fbm(vec2 p){ float a=.5, s=0.; for(int i=0;i<5;i++){ s+=a*n(p); p=p*2.03+vec2(11.,7.); a*=.5; } return s; }
    void main(){
      vec2 p = v * vec2(res.x/res.y, 1.);
      float q = fbm(p*1.6 + vec2(t*.012, t*.004));
      float c = smoothstep(.42, .78, fbm(p*2.4 + q*1.6 + vec2(t*.02, 0.)));
      vec3 day = mix(vec3(.973,.914,.894), vec3(.925,.745,.75), pow(v.y, 1.5));
      day = mix(day, vec3(1.,.97,.95), c*.85);
      vec3 dusk = mix(vec3(.30,.16,.07), vec3(.11,.06,.03), v.y);
      dusk = mix(dusk, vec3(.42,.25,.18), c*.35);
      vec2 g = p*70.; vec2 id = floor(g);
      float star = step(.965, h(id)) * smoothstep(.13, .03, length(fract(g)-.5)) * (.6 + .4*sin(t*2. + h(id)*40.)) * v.y;
      gl_FragColor = vec4(mix(day, dusk + star*.9, night), 1.);
    }`));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, 'p');
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  const uniform = name => gl.getUniformLocation(program, name);
  gl.uniform1f(uniform('night'), night);

  const draw = time => {
    gl.uniform1f(uniform('t'), time / 1000);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };
  const fit = () => {
    canvas.width = Math.round(innerWidth * .8);
    canvas.height = Math.round(innerHeight * .8);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(uniform('res'), innerWidth, innerHeight);
    draw(performance.now());
  };
  addEventListener('resize', fit);
  fit();
  if (still) return;
  let last = 0;
  const frame = time => {
    if (time - last >= 40) { last = time; draw(time); } // About 25 frames a second is plenty for clouds.
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})();
