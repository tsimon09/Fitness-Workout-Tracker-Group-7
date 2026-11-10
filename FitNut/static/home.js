// Home: Almond floats in the sky. The page still reads normally without WebGL.
(() => {
  const canvas = document.getElementById('almond-canvas');
  if (!canvas || !FitNutNuts.mountAlmond(canvas)) {
    if (canvas) canvas.hidden = true;
    document.getElementById('almond-hint')?.setAttribute('hidden', '');
  }
})();
