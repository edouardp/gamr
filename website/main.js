// Scroll reveal with IntersectionObserver
const reveals = document.querySelectorAll('.reveal');
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => entry.target.classList.add('visible'), i * 80);
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

reveals.forEach(el => observer.observe(el));

// Copy buttons
document.querySelectorAll('.copy-btn, .hero-install-copy').forEach(btn => {
  btn.addEventListener('click', () => {
    const code = btn.dataset.code || btn.closest('.code-block').querySelector('code').textContent;
    navigator.clipboard.writeText(code).then(() => {
      btn.textContent = 'Copied!';
      setTimeout(() => btn.textContent = 'Copy', 2000);
    });
  });
});

// === HERO BACKGROUND: drifting code-line rectangles =============================
//
// Concept: every rect has a continuous `depth` in [0, 1] where 0 = far back and
// 1 = foreground. Depth controls ALL of a rect's visual properties in a correlated
// way so the eye reads it as true parallax:
//     depth 0  →  slow, dim, short, gray, thin  (dense fog in the back)
//     depth 1  →  fast, bright, long, lime, thick  (sparse streaks up front)
//
// Two main knobs to tune the look:
//   1. RECT COUNT  — controlled by the LAYERS table (d, perRow) below
//   2. BRIGHTNESS  — controlled by the `alpha` formula inside makeRect()
//
// --------------------------------------------------------------------------------

(() => {
  const canvas = document.querySelector('.hero-bg');
  if (!canvas) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const ctx = canvas.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const css = getComputedStyle(document.documentElement);
  const COLOR_DIM = css.getPropertyValue('--text-dim').trim() || '#8a8a96';
  const COLOR_ACCENT = css.getPropertyValue('--accent').trim() || '#d4ff4a';
  const COLOR_HOVER = css.getPropertyValue('--purple').trim() || '#a855f7';

  // Linear-interpolate two #rrggbb colors as an `rgb(r,g,b)` string.
  const parseHex = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const lerpHex = (a, b, t) => {
    const ca = parseHex(a), cb = parseHex(b);
    return `rgb(${ca[0] + (cb[0] - ca[0]) * t | 0},${ca[1] + (cb[1] - ca[1]) * t | 0},${ca[2] + (cb[2] - ca[2]) * t | 0})`;
  };

  const ROW_H = 10;
  const HOVER_ALPHA = 0.4;     // alpha while a rect is under the mouse
  const TRANSITION_MS = 3000;  // time to fade back to default after mouse leaves
  let W = 0, H = 0;
  let rects = [];
  let running = true;
  let lastT = 0;
  let mouseX = -1, mouseY = -1, mouseOver = false;

  // Listen for mousemove on the whole hero section (not just the canvas) so the
  // hit test still works when the cursor is over foreground HTML inside .hero-content
  // (the GAMR logo, headlines, buttons, etc). The canvas sits at z-index 0 and would
  // otherwise never see those events. Hit testing is computed against canvas-relative
  // coordinates either way, so it doesn't matter what's on top visually.
  const hero = canvas.parentElement;
  hero.addEventListener('mousemove', (e) => {
    const r = canvas.getBoundingClientRect();
    mouseX = e.clientX - r.left;
    mouseY = e.clientY - r.top;
    mouseOver = true;
    canvas.style.cursor = 'pointer';
  });
  hero.addEventListener('mouseleave', () => {
    mouseOver = false;
    canvas.style.cursor = '';
  });

  function resize() {
    const r = canvas.getBoundingClientRect();
    W = r.width;
    H = r.height;
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    // Reset transform before applying DPR scale (avoids compounding on repeated resizes)
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    seed();
    ctx.clearRect(0, 0, W, H);
  }

  // === RECT COUNT ===============================================================
  // LAYERS defines the population. Each entry is one "stratum" at a base depth,
  // with a per-row spawn count. Total rects = sum(perRow) * numRows
  //   numRows = floor(H / ROW_H)
  //
  // Tweak `perRow` to make the back denser / sparser.
  // Tweak the `d` values to add/remove strata (keep them in [0, 1] and ordered).
  //
  // Current setup, for an 800px-tall hero (80 rows):
  //   1 + 1 + 1 + 1  = 4 rects per row
  //   4 * 80         = ~320 rects total  (one at each depth band)
  const LAYERS = [
    { d: 0.00, perRow: 1 },   // far back:    dim, slow, short, gray
    { d: 0.33, perRow: 1 },   // mid-back:
    { d: 0.67, perRow: 1 },   // mid-front:   switching to accent color
    { d: 1.00, perRow: 1 },   // foreground:  fastest, longest, brightest
  ];

  function makeRect(depth, row) {
    // === WIDTH (longer at front) =================================================
    // Mean width grows linearly from 30px (back) to 310px (front).
    // Variance also grows with depth, so foreground rects are more visually varied.
    const meanW = 30 + depth * 280;
    const varW = 25 + depth * 140;
    const w = Math.max(20, meanW + (Math.random() - 0.5) * varW);

    // === SPEED (faster at front) =================================================
    // 4 px/s in the back, ~60 px/s in the foreground. Foreground streaks whip past
    // while background fog barely crawls — that's the parallax illusion.
    const vx = 4 + depth * 56 + (Math.random() - 0.5) * 8;

    // === BRIGHTNESS / ALPHA ======================================================
    // THE place to tune overall brightness. Linear ramp from ~0.05 (back) to
    // ~0.19 (front) — max alpha cut by 20% from 0.24. Plus small per-rect jitter.
    //   depth=0.0  →  alpha ≈ 0.05   (very dim, barely visible)
    //   depth=0.5  →  alpha ≈ 0.121
    //   depth=1.0  →  alpha ≈ 0.19   (still the brightest, but more restrained)
    const alpha = Math.max(0.04, Math.min(0.25, 0.05 + depth * 0.14 + (Math.random() - 0.5) * 0.04));

    // === COLOR (gray at back, accent at front) ===================================
    // Hard threshold at depth 0.6. Could be made smooth by lerping RGB, but the
    // hard step reads as a clean "this is foreground" cue.
    const color = depth > 0.6 ? COLOR_ACCENT : COLOR_DIM;

    // === HEIGHT (thicker at front) ===============================================
    // 1.5px in the back, 3px in front. Small but adds to the depth read.
    const h = 1.5 + depth * 1.5;

    // === Y POSITION (with small jitter) ==========================================
    // Snapped to a 10px row grid + ±1px jitter so the field doesn't feel rigid.
    const y = row * ROW_H + ROW_H / 2 + (Math.random() - 0.5) * 2;

    return {
      x: Math.random() * (W + 200) - 200,  // staggered initial x so they don't enter in a wave
      y,
      w,
      h,
      vx,
      alpha,
      color,
      depth,
      hovered: false,       // true while the mouse is over this rect
      unhoverAt: 0,         // timestamp when the mouse last left (0 = no active transition)
    };
  }

  function seed() {
    rects = [];
    const rows = Math.max(8, Math.floor(H / ROW_H));
    for (const { d, perRow } of LAYERS) {
      for (let r = 0; r < rows; r++) {
        for (let k = 0; k < perRow; k++) {
          // Per-rect depth jitter (±0.05) so the spread feels continuous rather
          // than staircased across the layers. Clamped to keep it in [0, 1].
          const depth = Math.max(0, Math.min(1, d + (Math.random() - 0.5) * 0.1));
          rects.push(makeRect(depth, r));
        }
      }
    }
  }

  function step(now) {
    if (!running) return;
    const dt = Math.min(0.05, (now - lastT) / 1000) || 0;
    lastT = now;

    ctx.clearRect(0, 0, W, H);

    // Hit-test: find the topmost rect under the mouse, if any.
    // The hit box is inflated by HIT_SLOP px in every direction so the rect is
    // "live" within a small radius of the cursor, not just on top of it.
    // AABB check is fine — ~320 rects is trivial to scan each frame.
    const HIT_SLOP = 4;
    let hovered = null;
    if (mouseOver) {
      for (const r of rects) {
        if (mouseX >= r.x - HIT_SLOP && mouseX <= r.x + r.w + HIT_SLOP &&
            mouseY >= r.y - r.h / 2 - HIT_SLOP && mouseY <= r.y + r.h / 2 + HIT_SLOP) {
          hovered = r;
          break;
        }
      }
    }

    // Update hover state. On enter: instant. On leave: stamp unhoverAt so the
    // render loop knows when to start (and how far along) the fade-back.
    for (const r of rects) {
      if (r === hovered) {
        if (!r.hovered) { r.hovered = true; r.unhoverAt = 0; }
      } else if (r.hovered) {
        r.hovered = false;
        r.unhoverAt = now;
      }
    }

    for (const r of rects) {
      r.x += r.vx * dt;
      if (r.x > W + 50) {
        // Respawn off-screen left, re-randomize width for variety
        r.x = -r.w - Math.random() * 80;
        const meanW = 30 + r.depth * 280;
        const varW = 25 + r.depth * 140;
        r.w = Math.max(20, meanW + (Math.random() - 0.5) * varW);
      }

      // === Resolve color & alpha for this frame =============================
      // Hovered    → instant purple at HOVER_ALPHA
      // Transition → lerp from purple→default color and 0.4→r.alpha over 3s
      // Idle       → original color & alpha
      let color = r.color;
      let alpha = r.alpha;
      if (r.hovered) {
        color = COLOR_HOVER;
        alpha = HOVER_ALPHA;
      } else if (r.unhoverAt) {
        const elapsed = now - r.unhoverAt;
        if (elapsed < TRANSITION_MS) {
          const t = elapsed / TRANSITION_MS;
          color = lerpHex(COLOR_HOVER, r.color, t);
          alpha = HOVER_ALPHA + (r.alpha - HOVER_ALPHA) * t;
        } else {
          r.unhoverAt = 0;
        }
      }

      ctx.fillStyle = color;
      ctx.globalAlpha = alpha;
      ctx.fillRect(r.x, r.y - r.h / 2, r.w, r.h);

      // Leading marker on the brightest foreground rects (depth > 0.7).
      // Skip during hover/transition so the accent dot doesn't clash with purple.
      if (r.depth > 0.7 && !r.hovered && !r.unhoverAt) {
        ctx.fillStyle = COLOR_ACCENT;
        ctx.globalAlpha = Math.min(0.55, r.alpha * 1.6);
        ctx.fillRect(r.x + r.w + 4, r.y - 1, 3, 2);
      }
    }

    requestAnimationFrame(step);
  }

  // Pause when hero is off-screen
  const io = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) {
      if (!running) {
        running = true;
        lastT = performance.now();
        requestAnimationFrame(step);
      }
    } else {
      running = false;
    }
  }, { threshold: 0 });
  io.observe(canvas);

  let resizeT;
  window.addEventListener('resize', () => {
    clearTimeout(resizeT);
    resizeT = setTimeout(resize, 150);
  });

  resize();
  requestAnimationFrame(step);
})();
