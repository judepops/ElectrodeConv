// The judging deck. Data: ../dashboard/site/pipeline.js and harness.js, plus results.js (demo/make_data.py).
// config.js picks the rows. Each slide has steps ("builds"); the right arrow goes to the next build, then the next slide.
(() => {
  const D = window.PIPELINE, HZ = window.HARNESS, CFG = window.DEMO_CONFIG || {};
  if (!D) {
    document.body.insertAdjacentHTML("afterbegin", '<p style="padding:80px 20px">No data: build the team page first (python dashboard/build.py).</p>');
    return;
  }
  const P = D.prep, C = D.cnn, R = D.results || {}, S = D.spot, K = C.kernel, T = CFG.timing || {};
  const IMG = s => "../dashboard/site/" + s;                       // pipeline.js paths are relative to dashboard/site/

  // ---- helpers (as in dashboard/site/app.js) -------------------------------------------------------------------
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = t => { t = clamp(t); return t * t * (3 - 2 * t); };
  const pct = v => (100 * v).toFixed(0) + "%";
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SVGNS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs = {}) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const decode = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  const STOPS = [[68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], [38, 130, 142], [31, 158, 137],
    [53, 183, 121], [110, 206, 88], [181, 222, 43], [253, 231, 37]];
  const LUT = Array.from({ length: 256 }, (_, i) => {
    const x = i / 255 * (STOPS.length - 1), j = Math.min(STOPS.length - 2, Math.floor(x)), f = x - j;
    return STOPS[j].map((v, k) => Math.round(lerp(v, STOPS[j + 1][k], f)));
  });
  const lutCss = v => { const c = LUT[Math.round(clamp(v) * 255)]; return `rgb(${c[0]},${c[1]},${c[2]})`; };
  function gridCanvas(b64, size, colour) {
    const px = decode(b64), cv = document.createElement("canvas");
    cv.width = cv.height = size;
    const ctx = cv.getContext("2d"), img = ctx.createImageData(size, size);
    for (let i = 0; i < px.length; i++) {
      const c = colour ? LUT[px[i]] : [px[i], px[i], px[i]];
      img.data[4 * i] = c[0]; img.data[4 * i + 1] = c[1]; img.data[4 * i + 2] = c[2]; img.data[4 * i + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    return cv;
  }
  function fitCanvas(cv, w, h) {
    const dpr = window.devicePixelRatio || 1;
    cv.style.width = w + "px"; cv.style.height = h + "px";
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    return ctx;
  }
  const digits = (lo, hi) => Math.max(2, Math.min(4, Math.ceil(-Math.log10(Math.max(hi - lo, 1e-6))) + 1));
  const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(+v)) ? "–" : (+v).toFixed(d);
  const sgn = (v, d = 2) => (v > 0 ? "+" : "") + fmt(v, d);
  const bcol = b => `var(--c${b})`;
  const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const FL = R.feature_labels || {};
  const flab = f => FL[f] || f.replace(/_/g, " ");
  const mean = a => a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0;
  const chip = (label, value, cls = "") => `<span class="chip ${cls}">${label} <b>${value}</b></span>`;
  const DET = { bse: "BSE", inlens: "Inlens", se: "SE" };
  const tileName = `r${P.tiles.chosen.row} c${P.tiles.chosen.col}`;

  // ---- engine -------------------------------------------------------------------------------------------------
  const deck = $("#deck"), slides = [];
  let cur = { i: 0, b: 0 }, running = [], instant = false;
  function tween(ms, fn, done) {
    if (reduced || instant) { fn(1); done && done(); return () => {}; }
    let raf = 0; const t0 = performance.now();
    const tick = now => { const u = clamp((now - t0) / ms); fn(u); if (u < 1) raf = requestAnimationFrame(tick); else done && done(); };
    raf = requestAnimationFrame(tick);
    const cancel = () => cancelAnimationFrame(raf);
    running.push(cancel);
    return cancel;
  }
  const cancelAll = () => { running.forEach(c => c()); running = []; };
  function slide(id, def) { slides.push({ id, el: $("#" + id), builds: 1, ...def }); }
  const applyBuilds = (s, b) => $$(".b", s.el).forEach(e => e.classList.toggle("on", +e.dataset.b <= b));
  function goTo(i, b = 0) {
    i = clamp(i, 0, slides.length - 1);
    const s = slides[i]; b = clamp(b, 0, s.builds - 1);
    cancelAll();
    const prev = slides[cur.i], same = prev === s;
    if (!same) { prev.el.classList.remove("on"); prev.el.classList.add("out"); setTimeout(() => prev.el.classList.remove("out"), 500); }
    cur = { i, b };
    s.el.classList.add("on");
    if (!same) { s.layout && s.layout(); s.enter && s.enter(); }
    const was = instant;
    for (let k = 0; k <= b; k++) { instant = was || k < b; applyBuilds(s, k); s.build && s.build(k); }
    instant = was;
    $("#progress").style.width = (100 * (i + (b + 1) / s.builds) / slides.length) + "%";
    $("#counter").textContent = `${i + 1} / ${slides.length}`;
    history.replaceState(null, "", `#${i}.${b}`);
  }
  const next = () => cur.b + 1 < slides[cur.i].builds ? goTo(cur.i, cur.b + 1) : goTo(cur.i + 1, 0);
  const prev = () => cur.b > 0 ? goTo(cur.i, cur.b - 1) : cur.i > 0 ? goTo(cur.i - 1, slides[cur.i - 1].builds - 1) : null;
  const redraw = () => { const was = instant; instant = true; const s = slides[cur.i]; s.layout && s.layout(); goTo(cur.i, cur.b); instant = was; };
  window.addEventListener("keydown", e => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const k = e.key;
    if (k === "ArrowRight" || k === " " || k === "PageDown" || k === "n") { e.preventDefault(); next(); }
    else if (k === "ArrowLeft" || k === "PageUp" || k === "p") { e.preventDefault(); prev(); }
    else if (k === "Home") goTo(0, 0);
    else if (k === "End") goTo(slides.length - 1, 0);
    else if (k === "t") { const r = document.documentElement, dark = matchMedia("(prefers-color-scheme: dark)").matches; r.dataset.theme = (r.dataset.theme || (dark ? "dark" : "light")) === "dark" ? "light" : "dark"; redraw(); }
    else if (k === "f") { document.fullscreenElement ? document.exitFullscreen() : deck.requestFullscreen && deck.requestFullscreen(); }
  });
  deck.addEventListener("click", e => { if (e.target.closest("a, button")) return; (e.clientX - deck.getBoundingClientRect().left) / deck.clientWidth < 0.33 ? prev() : next(); });
  let tx = null;
  deck.addEventListener("touchstart", e => { tx = e.touches[0].clientX; }, { passive: true });
  deck.addEventListener("touchend", e => { if (tx === null) return; const dx = e.changedTouches[0].clientX - tx; tx = null; if (dx < -40) next(); else if (dx > 40) prev(); });
  let roFirst = true;
  new ResizeObserver(() => { if (roFirst) { roFirst = false; return; } if (slides.length) redraw(); }).observe(deck);
  window.DEMO = { go: goTo, next, prev, finish: () => redraw(), slides };

  // ==============================================================================================================
  // 0  title
  // ==============================================================================================================
  $("#title-h1").textContent = CFG.title || "losslarp";
  $("#title-lede").textContent = CFG.subtitle || "";
  $("#title-team").textContent = CFG.team || "";
  $("#title-strip").innerHTML = ["bse", "inlens", "se"].map(d => `<img src="${IMG(P.tiles.chosen.planes[d])}" alt="${DET[d]} plane of the walkthrough tile">`).join("");
  slide("title", { builds: 1 });

  // ==============================================================================================================
  // lanes: the 31 training spots as crops of 13 long images, in order along each image (window.LANES)
  // ==============================================================================================================
  {
    const LN = window.LANES, rows = $("#lanes-rows");
    if (LN) {
      const bs = LN.batch_sizes;
      $("#lanes-sub").textContent = `each row is one long SEM image cut into spots; colour = the batch folder each spot was given in`;
      rows.innerHTML = LN.lanes.map(l => `<div class="lane"><span class="ln">${l.id}</span>` + l.spots.map(s =>
        `<img src="${IMG(s.img)}" alt="${s.id}" data-a="${s.aspect}" class="${s.touches_next ? "touch" : ""}" style="border-color:${bcol(s.batch)}">`).join("") + `</div>`).join("");
      $("#lanes-chips").innerHTML = chip("training spots", LN.n_spots) + chip("images", LN.lanes.length) +
        chip("lanes with more than one batch", LN.lanes.filter(l => new Set(l.spots.map(s => s.batch)).size > 1).length) +
        `<span class="chip"><i class="sw" style="background:var(--c1)"></i>Batch_1 ${bs[1]} <i class="sw" style="background:var(--c2)"></i>Batch_2 ${bs[2]} <i class="sw" style="background:var(--c3)"></i>Batch_3 ${bs[3]}</span>`;
    }
    slide("lanes", {
      builds: 1,
      layout() {                                                  // one row height for all lanes, so the widest lane fits
        if (!LN) return;
        const W = rows.clientWidth - 40, H = rows.clientHeight / LN.lanes.length - 4;
        const widest = Math.max(...LN.lanes.map(l => l.spots.reduce((a, s) => a + 1 / s.aspect, 0)));
        rows.style.setProperty("--rh", Math.floor(Math.min(H, W / widest)) + "px");
      },
      build() { const r = $$("#lanes-rows .lane"); r.forEach(e => e.classList.remove("on")); r.forEach((e, i) => setTimeout(() => e.classList.add("on"), instant ? 0 : 80 * i)); },
    });
  }

  // ==============================================================================================================
  // 1  preprocessing: crop -> anchor -> noise -> rank -> segment -> tiles, before / after on the real spot
  // ==============================================================================================================
  {
    const crop = P.crop, win = P.window, chosen = P.tiles.chosen;
    const frames = $("#prep-frames"), cropSvgs = [];
    const FR = ["bse", "inlens"];
    FR.forEach(d => {
      const f = document.createElement("div"); f.className = "frame";
      f.innerHTML = `<img src="${IMG(P.raw.img[d])}" alt="raw ${DET[d]}"><span class="tag">${DET[d]} · raw</span>`;
      const W = P.raw.w, H = P.raw.h;
      const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none" });
      svg.appendChild(svgEl("path", { "fill-rule": "evenodd", fill: "var(--shade)", d: `M0 0H${W}V${H}H0Z M${crop.c0} ${crop.r0}H${crop.c1}V${crop.r1}H${crop.c0}Z` }));
      svg.appendChild(svgEl("rect", { x: crop.c0, y: crop.r0, width: crop.c1 - crop.c0, height: crop.r1 - crop.r0, fill: "none", stroke: "var(--accent)", "stroke-width": 3, "vector-effect": "non-scaling-stroke" }));
      f.appendChild(svg); frames.appendChild(f); cropSvgs.push(svg);
    });
    const STEPS = ["raw", "crop", "anchor", "noise", "rank", "segment", "tiles"];
    $("#prep-steps").innerHTML = STEPS.map(s => `<span>${s}</span>`).join("");
    const pairWin = (a, b, lab) => `<div class="win"><img src="${IMG(a)}" alt=""><img class="over" src="${IMG(b)}" alt=""><span class="tag">${lab}</span></div>`;
    const tileRects = P.tiles.grid.map(([r, c, y, x]) => `<rect x="${x}" y="${y}" width="${P.tiles.size}" height="${P.tiles.size}" vector-effect="non-scaling-stroke" class="${r === chosen.row && c === chosen.col ? "chosen" : ""}"/>`).join("");
    $("#prep-panels").innerHTML =
      `<div class="panel" data-p="0 1"><div class="win"><img src="${IMG(win.img.bse_raw)}" alt=""><span class="tag">BSE · kept window</span></div></div>` +
      `<div class="panel" data-p="2">${pairWin(win.img.bse_raw, win.img.bse, "BSE · grey levels → graphite units")}</div>` +
      `<div class="panel" data-p="3"><div class="pair">${pairWin(P.noise.before, P.noise.before, "before")}${pairWin(P.noise.before, P.noise.after, "after · noise topped up")}</div></div>` +
      `<div class="panel" data-p="4"><div class="pair">${pairWin(win.img.inlens_raw, win.img.inlens, "Inlens · rank")}${pairWin(win.img.se_raw, win.img.se, "SE · rank")}</div></div>` +
      `<div class="panel" data-p="5 6"><div class="win"><img src="${IMG(win.img.bse)}" alt=""><img class="over" src="${IMG(win.img.overlay)}" alt=""><svg viewBox="0 0 ${win.w} ${win.h}" preserveAspectRatio="none">${tileRects}</svg><span class="tag" id="prep-seg-tag">pores · Si-like</span></div>` +
      `<div class="planes b" data-b="6">${["bse", "inlens", "se", "void", "bright"].map(k => `<figure><img src="${IMG(chosen.planes[k])}" alt=""><figcaption>${{ bse: "BSE", inlens: "Inlens", se: "SE", void: "pores", bright: "Si-like" }[k]}</figcaption></figure>`).join("")}</div></div>`;
    const panels = $$("#prep-panels .panel"), rects = $$("#prep-panels svg rect");
    const chips = [
      chip("pixel", `${S.pixel_um * 1000} nm`),
      chip("kept", `${win.h} × ${win.w} px`),
      "",
      chip("noise σ", P.noise.bse_target),
      "",
      chip("porosity", pct(P.seg.porosity)) + chip("Si-like", pct(P.seg.bright_frac)),
      chip("tiles", P.tiles.grid.length) + chip("tile", `${P.tiles.um} µm`),
    ];
    slide("prep", {
      builds: 7,
      layout() {   // the stacked 3:1 frames must fit the body height
        const body = $("#prep .body"), gap = body.clientHeight * 0.02;
        frames.style.width = Math.max(100, Math.min(body.clientWidth * 0.53, (body.clientHeight - gap) / FR.length * P.raw.w / P.raw.h)) + "px";
      },
      build(b) {
        $$("#prep-steps span").forEach((e, i) => { e.classList.toggle("on", i === b); e.classList.toggle("done", i < b); });
        $("#prep-chips").innerHTML = chips[b];
        cropSvgs.forEach(s => s.classList.toggle("on", b >= 1));
        $$("#prep-frames .tag").forEach((t, i) => t.textContent = `${DET[FR[i]]} · ${b === 0 ? "raw" : "same window"}`);
        panels.forEach(p => p.classList.toggle("on", p.dataset.p.split(" ").includes(String(b))));
        const p = panels.find(p => p.dataset.p.split(" ").includes(String(b)));
        const overs = $$("img.over", p);
        if (b >= 2 && b <= 4) tween(1400, u => overs.forEach(o => o.style.opacity = smooth((u - 0.25) / 0.6)));
        if (b === 5) { tween(900, u => overs[0].style.opacity = smooth(u)); rects.forEach(r => r.classList.remove("on")); $("#prep-seg-tag").textContent = "pores (blue) · Si-like (amber)"; }
        if (b === 6) {
          overs[0].style.opacity = 0.15; $("#prep-seg-tag").textContent = `${P.tiles.grid.length} tiles · tile ${tileName} continues`;
          tween(1400, u => { const n = Math.floor(smooth(u) * rects.length + 0.001); rects.forEach((r, i) => r.classList.toggle("on", i < n)); });
        }
      },
    });
  }

  // ==============================================================================================================
  // shared: the kernel sweep over the walkthrough tile (layer-1 kernel of the page's run), the z bars, matrices
  // ==============================================================================================================
  const G = K.grid, KS = K.k, KH = Math.floor(KS / 2), SRC = K.display / G;
  const kOff = {}; K.planes.forEach(d => { kOff[d] = gridCanvas(K.input[d], K.display, false); });
  kOff.fmap = gridCanvas(K.fmap, K.display, true);
  const outOf = pos => { const s = K.samples[pos]; return s[s.length - 1]; };
  function drawInputs(ctxs, size, pos, done) {
    const gy = Math.floor(pos / G), gx = pos % G, cell = size / G;
    Object.entries(ctxs).forEach(([d, ctx]) => {
      ctx.drawImage(kOff[d], 0, 0, size, size);
      if (done) return;
      const x = (gx - KH) * cell, y = (gy - KH) * cell, col = css("--" + d);
      ctx.fillStyle = col + "44"; ctx.fillRect(x, y, KS * cell, KS * cell);
      ctx.strokeStyle = col; ctx.lineWidth = 1;
      for (let j = 1; j < KS; j++) { ctx.beginPath(); ctx.moveTo(x + j * cell, y); ctx.lineTo(x + j * cell, y + KS * cell); ctx.stroke(); ctx.beginPath(); ctx.moveTo(x, y + j * cell); ctx.lineTo(x + KS * cell, y + j * cell); ctx.stroke(); }
      ctx.lineWidth = 2.5; ctx.strokeRect(x, y, KS * cell, KS * cell);
    });
  }
  function drawFmap(ctx, size, pos, done) {
    const gy = Math.floor(pos / G), gx = pos % G, cell = size / G;
    ctx.fillStyle = css("--line"); ctx.fillRect(0, 0, size, size);
    if (done) { ctx.drawImage(kOff.fmap, 0, 0, size, size); return; }
    if (gy > 0) ctx.drawImage(kOff.fmap, 0, 0, K.display, gy * SRC, 0, 0, size, gy * cell);
    ctx.drawImage(kOff.fmap, 0, gy * SRC, (gx + 1) * SRC, SRC, 0, gy * cell, (gx + 1) * cell, cell);
    ctx.strokeStyle = css("--accent"); ctx.lineWidth = 2.5; ctx.strokeRect(gx * cell, gy * cell, cell, cell);
  }
  function drawZ(cv, z, col, t) {
    const W = cv.clientWidth, H = cv.clientHeight, ctx = fitCanvas(cv, W, H), mid = H / 2;
    const m = Math.max(...z.map(Math.abs)) || 1, bw = W / z.length;
    ctx.fillStyle = css("--line"); ctx.fillRect(0, mid - 0.5, W, 1);
    ctx.fillStyle = col;
    z.forEach((v, i) => { const h = v / m * (mid - 2) * t; ctx.fillRect(i * bw + 0.5, h > 0 ? mid - h : mid, Math.max(1, bw - 1), Math.abs(h)); });
  }
  const square = el => Math.floor(Math.min(el.clientWidth, el.clientHeight));

  // ==============================================================================================================
  // 2  V1: kernel sweep -> BSE z and Inlens z -> the 8 x 8 cross-detector matrix (C.v1)
  // ==============================================================================================================
  {
    const V1 = C.v1, M = V1 && V1.matrix;
    const ins = $("#v1-ins");
    ins.innerHTML = ["bse", "inlens"].map(d => `<div class="cwrap"><canvas data-plane="${d}"></canvas><span class="tag bl">${DET[d]}</span></div>`).join("");
    $("#v1-z").innerHTML = ["bse", "inlens"].map(d => `<div class="zrow"><span class="zl" style="color:var(--${d})">${DET[d]}</span><canvas data-z="${d}"></canvas></div>`).join("");
    let cin = 100, cv = 200, mx = 300, ctxIn = {}, ctxFm, ctxMx, thumbs = [];
    if (M) thumbs = M.tiles.map(t => ({ bse: gridCanvas(t.thumb.bse, M.thumb_size, false), inlens: gridCanvas(t.thumb.inlens, M.thumb_size, false) }));
    function layout() {
      const scan = $("#v1 .scan"); cin = Math.floor(Math.min((scan.clientWidth - 20) / 2, scan.clientHeight * 0.36));
      $$("canvas", ins).forEach(c => { ctxIn[c.dataset.plane] = fitCanvas(c, cin, cin); });
      cv = Math.min(square($("#v1 .fmwrap")), scan.clientHeight - cin - 30); ctxFm = fitCanvas($("#v1-fm"), cv, cv);
      const w = $("#v1 .mxwrap"); mx = Math.floor(Math.min(w.clientWidth, w.clientHeight)); ctxMx = fitCanvas($("#v1-mx"), mx, mx);
    }
    function drawMatrix(shown, dots) {
      const Sm = M.trained.sim, N = Sm.length, flat = Sm.flat(), lo = Math.min(...flat), hi = Math.max(...flat), dg = digits(lo, hi);
      const fs = Math.max(10, mx * 0.03), th = Math.max(16, Math.min(48, mx * 0.09)), pad = fs + th + 10, cell = (mx - pad) / N, ctx = ctxMx;
      ctx.clearRect(0, 0, mx, mx);
      for (let i = 0; i < N; i++) {
        const ts = Math.min(th, cell - 4), o = pad + i * cell + (cell - ts) / 2;
        ctx.drawImage(thumbs[i].inlens, o, fs + 4, ts, ts); ctx.drawImage(thumbs[i].bse, fs + 4, o, ts, ts);
      }
      ctx.font = `600 ${fs}px system-ui, sans-serif`; ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.fillStyle = css("--inlens"); ctx.fillText("Inlens tiles", pad, 0);
      ctx.save(); ctx.translate(0, pad + N * cell); ctx.rotate(-Math.PI / 2); ctx.fillStyle = css("--bse"); ctx.fillText("BSE tiles", 0, 0); ctx.restore();
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.font = `${Math.max(9, Math.min(13, cell / 4))}px system-ui, sans-serif`;
      for (let k = 0; k < N * N; k++) {
        const i = Math.floor(k / N), j = k % N, x = pad + j * cell, y = pad + i * cell;
        if (k >= shown) { ctx.strokeStyle = css("--line"); ctx.lineWidth = 1; ctx.strokeRect(x + 1, y + 1, cell - 2, cell - 2); continue; }
        const v = (Sm[i][j] - lo) / (hi - lo || 1);
        ctx.fillStyle = lutCss(v); ctx.fillRect(x + 1, y + 1, cell - 2, cell - 2);
        if (cell > 30) { ctx.fillStyle = v > 0.6 ? "#111" : "#fff"; ctx.fillText(Sm[i][j].toFixed(dg), x + cell / 2, y + cell / 2); }
      }
      if (dots) {
        ctx.strokeStyle = css("--ink"); ctx.lineWidth = 2;
        for (let i = 0; i < N; i++) ctx.strokeRect(pad + i * cell + 1.5, pad + i * cell + 1.5, cell - 3, cell - 3);
        for (let i = 0; i < N; i++) {
          const j = Sm[i].indexOf(Math.max(...Sm[i]));
          ctx.fillStyle = css(j === i ? "--good" : "--bad"); ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(pad + j * cell + cell - 8, pad + i * cell + 8, 5, 0, 7); ctx.fill(); ctx.stroke();
        }
      }
    }
    slide("v1", {
      builds: M ? 3 : 1, layout,
      build(b) {
        if (b === 0) {
          $("#v1-chips").innerHTML = chip("kernel", `${KS} × ${KS}`) + chip("tile", `${P.tiles.size} px`);
          tween(T.sweepMs || 6000, u => { const pos = Math.min(G * G - 1, Math.floor(u * G * G)), done = u >= 1; drawInputs(ctxIn, cin, pos, done); drawFmap(ctxFm, cv, pos, done); $("#v1-fm-lab").textContent = done ? "feature map" : `feature map · ${outOf(pos).toFixed(2)}`; });
        }
        if (b === 1 && V1) {
          $("#v1-chips").innerHTML = chip("embedding size", V1.z.bse.length) + chip("cosine, same tile", V1.z_cos.toFixed(3));
          tween(900, u => ["bse", "inlens"].forEach(d => drawZ($(`#v1-z canvas[data-z="${d}"]`), V1.z[d], css("--" + d), smooth(u))));
        }
        if (b === 2 && M) {
          const N = M.tiles.length;
          $("#v1-chips").innerHTML = chip("best match is the same tile", `${Math.round(M.trained.retrieval * N)} / ${N}`, "ok") + chip("chance", `1 / ${N}`);
          tween(T.matrixMs || 2200, u => drawMatrix(Math.max(1, Math.ceil(smooth(u) * N * N)), u >= 1));
        }
      },
    });
  }

  // ==============================================================================================================
  // 3  V2: three planes in -> one z -> the batch contrast matrix (C.contrast)
  // ==============================================================================================================
  {
    const CT = C.contrast, N = CT ? CT.tiles.length : 0, REL = CT ? CT.relation : [];
    const stack = $("#v2-stack");
    stack.innerHTML = K.planes.map(d => `<div class="cwrap"><canvas data-plane="${d}"></canvas><span class="tag bl">${DET[d]}</span></div>`).join("");
    $("#v2-z").innerHTML = `<div class="zrow"><span class="zl" style="color:var(--accent)">embedding</span><canvas data-z="fused"></canvas></div>`;
    $("#v2-key").innerHTML = `<span><i class="sw" style="background:var(--c1)"></i>Batch_1 <i class="sw" style="background:var(--c2)"></i>Batch_2 <i class="sw" style="background:var(--c3)"></i>Batch_3</span>` +
      `<span><b class="kbox spot"></b>same spot, ignored</span>`;
    let cin = 100, mx = 300, ctxIn = {}, ctxMx, thumbs = [];
    if (CT) thumbs = CT.tiles.map(t => gridCanvas(t.thumb, CT.thumb_size, false));
    const bnum = t => +t.batch.slice(-1);
    const BW = 72;
    function layout() {
      const scan = $("#v2 .scan"); cin = Math.floor(Math.min((scan.clientWidth - 30) / 3, scan.clientHeight * 0.6));
      $$("canvas", stack).forEach(c => { ctxIn[c.dataset.plane] = fitCanvas(c, cin, cin); ctxIn[c.dataset.plane].drawImage(kOff[c.dataset.plane], 0, 0, cin, cin); });
      const w = $("#v2 .mxwrap"); mx = Math.floor(Math.min(w.clientWidth - BW, w.clientHeight)); ctxMx = fitCanvas($("#v2-mx"), mx + BW, mx);
    }
    function drawContrast(t, rowOnly, bars) {              // t: 0 = untrained similarities, 1 = trained
      const A = CT.untrained.sim, B = CT.trained.sim, flatB = B.flat(), lo = Math.min(...flatB), hi = Math.max(...flatB);
      const sim = (i, j) => lerp(A[i][j], B[i][j], t);
      const ctx = ctxMx, th = Math.max(12, Math.min(36, mx * 0.07)), pad = th + 8, cell = (mx - pad) / N, line = css("--line"), ink = css("--ink");
      ctx.clearRect(0, 0, mx + BW, mx);
      for (let i = 0; i < N; i++) {
        const ts = Math.min(th, cell - 3), o = pad + i * cell + (cell - ts) / 2, col = css(`--c${bnum(CT.tiles[i])}`);
        ctx.drawImage(thumbs[i], o, 2, ts, ts); ctx.fillStyle = col; ctx.fillRect(o, 2 + ts + 1, ts, 3);
        ctx.drawImage(thumbs[i], 2, o, ts, ts); ctx.fillRect(2 + ts + 1, o, 3, ts);
      }
      for (let k = 0; k < N * N; k++) {
        const i = Math.floor(k / N), j = k % N, x = pad + j * cell, y = pad + i * cell, rel = REL[i][j];
        if (rowOnly && i !== 0) { ctx.strokeStyle = line; ctx.lineWidth = 1; ctx.strokeRect(x + 1, y + 1, cell - 2, cell - 2); continue; }
        const v = (sim(i, j) - lo) / (hi - lo || 1);
        ctx.fillStyle = rel === "self" ? css("--surface") : lutCss(v); ctx.fillRect(x + 1, y + 1, cell - 2, cell - 2);
        if (rel === "spot") {
          ctx.save(); ctx.beginPath(); ctx.rect(x + 1, y + 1, cell - 2, cell - 2); ctx.clip(); ctx.strokeStyle = "rgba(128,128,128,.8)"; ctx.lineWidth = 1.5;
          for (let q = -cell; q < cell * 2; q += 6) { ctx.beginPath(); ctx.moveTo(x + q, y); ctx.lineTo(x + q + cell, y + cell); ctx.stroke(); }
          ctx.restore();
        }
      }
      let start = 0;                                      // batch blocks
      for (let i = 1; i <= N; i++) {
        if (i < N && bnum(CT.tiles[i]) === bnum(CT.tiles[start])) continue;
        const x = pad + start * cell, w = (i - start) * cell;
        ctx.strokeStyle = css(`--c${bnum(CT.tiles[start])}`); ctx.lineWidth = 3; ctx.globalAlpha = rowOnly ? 0.5 : 1; ctx.strokeRect(x + 1, x + 1, w - 2, w - 2); ctx.globalAlpha = 1;
        start = i;
      }
      if (rowOnly) {
        ctx.strokeStyle = ink; ctx.lineWidth = 2.5; ctx.strokeRect(pad + 1, pad + 1, cell - 2, cell - 2);
        for (let j = 1; j < N; j++) if (REL[0][j] === "pos") { ctx.strokeStyle = css(`--c${bnum(CT.tiles[0])}`); ctx.lineWidth = 3; ctx.strokeRect(pad + j * cell + 2, pad + 2, cell - 4, cell - 4); }
      }
      if (bars) {
        const d = CT.trained;
        for (let i = 0; i < N; i++) {
          const y = pad + i * cell, bx = mx + 8, bw = BW - 14;
          ctx.fillStyle = line; ctx.fillRect(bx, y + cell * 0.3, bw, cell * 0.4);
          ctx.fillStyle = css("--accent"); ctx.fillRect(bx, y + cell * 0.3, bw * d.pos_share[i] * bars, cell * 0.4);
          ctx.fillStyle = ink; ctx.fillRect(bx + bw * CT.chance_share[i] - 0.75, y + cell * 0.18, 1.5, cell * 0.64);
        }
        ctx.fillStyle = css("--muted"); ctx.font = `600 ${Math.max(9, mx * 0.025)}px system-ui, sans-serif`; ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
        ctx.fillText("same", mx + 8, pad - 16); ctx.fillText("batch", mx + 8, pad - 4);
      }
    }
    slide("v2", {
      builds: CT ? 4 : 2, layout,
      build(b) {
        if (b === 0) { stack.classList.remove("on"); $("#v2-chips").innerHTML = chip("detectors", K.planes.length) + chip("tile", `${P.tiles.size} px`); setTimeout(() => stack.classList.add("on"), instant ? 0 : 250); }
        if (b === 1) { $("#v2-chips").innerHTML = chip("embedding size", C.z.fused.length); tween(900, u => drawZ($("#v2-z canvas"), C.z.fused, css("--accent"), smooth(u))); }
        if (b === 2 && CT) {
          const n = r => REL[0].filter(x => x === r).length;
          $("#v2-chips").innerHTML = chip("positives", n("pos"), "ok") + chip("negatives", n("neg"), "bad") + chip("ignored", n("spot"));
          drawContrast(1, true, 0);
        }
        if (b === 3 && CT) {
          const d = CT.trained, u0 = CT.untrained;
          $("#v2-chips").innerHTML = chip("same batch, other spot", d.within.toFixed(2), "ok") + chip("other batch", d.across.toFixed(2), "bad") + chip("weight on same-batch pairs", `${pct(mean(u0.pos_share))} → ${pct(mean(d.pos_share))}`);
          tween(T.contrastMs || 2600, u => drawContrast(smooth(u / 0.7), false, clamp((u - 0.7) / 0.3)));
        }
      },
    });
  }

  // ==============================================================================================================
  // 3b  how V1 and V2 are combined: late fusion (confusion.js -> fusion)
  // ==============================================================================================================
  {
    const FU = window.DEMO_CONFUSION && window.DEMO_CONFUSION.fusion;
    if (!FU) $("#fuse").remove();
    else {
      const n = FU.members.length;
      const box = (cls, title, sub, step) => `<div class="fbox ${cls} b" data-b="${step}"><b>${title}</b><small>${sub}</small></div>`;
      const arrow = step => `<div class="farrow b" data-b="${step}">→</div>`;
      $("#fuse-flow").innerHTML =
        `<div class="frow">${box("in", "one spot", "26 tiles · BSE, Inlens, SE", 0)}${arrow(0)}` +
          box("v1", "V1 encoder", "trained alone, never sees a label: describes the material", 0) + arrow(0) +
          box("vec v1", `${FU.v1_dims} numbers`, "mean over the tiles", 0) + `</div>` +
        `<div class="frow">${box("in", "the same spot", "the same 26 tiles", 0)}${arrow(0)}` +
          box("v2", `V2 encoder × ${n}`, "trained alone on the batch labels, one run per seed", 0) + arrow(0) +
          box("vec v2", `${FU.v2_dims} numbers each`, "mean over the tiles", 0) + `</div>` +
        `<div class="frow join">${box("op", "side by side", `each block standardised and scaled to equal weight, so ${FU.v1_dims} numbers do not drown ${FU.v2_dims}`, 1)}${arrow(1)}` +
          box("op", "logistic regression", "fitted on the 31 labelled spots", 1) + arrow(1) +
          box("op", `average over the ${n} V2 runs`, "P(Batch_1), P(Batch_2), P(Batch_3)", 1) + `</div>` +
        `<div class="fcompare b" data-b="2"><h4>Why join them at the end instead of training one network with both losses?</h4>` +
          `<div class="bars">` +
          [["V1 alone", FU.v1, "ref"], ["one network, both losses, from scratch", FU.joint_scratch, "ref"],
           ["one network, both losses, started from trained V1 + V2", FU.joint_warm, "ref"], ["V1 and V2 trained apart, joined at the decision", FU.late, "me"]]
            .filter(r => r[1] !== undefined)
            .map(([l, v, c]) => `<div class="brow ${c}"><span class="bl">${esc(l)}</span><span class="bt go"><i style="--w:${(100 * v).toFixed(1)}%"></i><em style="left:33.3%"></em></span><span class="bv num">${fmt(v)}</span></div>`).join("") +
          `</div><p class="cmnote">balanced accuracy on held-out spots, same folds, chance 0.33. Trained together, the two views pull towards each other ` +
          `and the batch signal of V2 is lost; kept apart, each keeps what it is good at: V1 the material in general, V2 what separates the batches.</p></div>`;
      slide("fuse", {
        builds: 3,
        build(b) {
          $("#fuse .fcompare").style.display = b === 2 ? "" : "none";
          $$("#fuse .frow").forEach(r => r.style.display = b === 2 ? "none" : "");
          $("#fuse-chips").innerHTML = b === 0 ? chip("V1", `${FU.v1_dims} numbers`) + chip("V2 runs", `${n} × ${FU.v2_dims} numbers`)
            : b === 1 ? chip("classifier", "logistic regression") + chip("fitted on", "31 spots")
            : chip("joined at the decision", fmt(FU.late), "ok") + chip("best single network", fmt(Math.max(FU.joint_scratch || 0, FU.joint_warm || 0)));
        },
      });
    }
  }

  // ==============================================================================================================
  // 4  held-out accuracy (results.js), then the test spots against Polaron's answers
  // ==============================================================================================================
  const DR = window.DEMO_RESULTS;
  const pick = key => {                                           // "name*" matches by prefix (seed count can change)
    if (!DR) return null;
    const k = key.endsWith("*") ? Object.keys(DR.models).find(k => k.startsWith(key.slice(0, -1))) : key;
    return k && DR.models[k] ? DR.models[k] : null;
  };
  const barRow = (label, sub, d, cls = "") => d
    ? `<div class="brow ${cls}"><span class="bl">${esc(label)}<small>${esc(sub || "")}</small></span>` +
      `<span class="bt"><i style="--w:${(100 * d.bacc).toFixed(1)}%"></i><em style="left:33.3%"></em>` +
      (d.ci90 ? `<span class="ci" style="left:${(100 * d.ci90.lo).toFixed(1)}%;width:${(100 * (d.ci90.hi - d.ci90.lo)).toFixed(1)}%"></span>` : "") +
      `</span><span class="bv num">${fmt(d.bacc)}<small>${d.ci90 ? `[${fmt(d.ci90.lo)}, ${fmt(d.ci90.hi)}]` : ""}</small></span></div>`
    : "";
  const axis = mid => `<div class="axis"><span></span><div><span style="left:0">0</span><span style="left:${mid}%">chance</span><span style="left:100%">1</span></div><span></span></div>`;
  const growBars = sel => { $$(sel + " .bt").forEach(b => b.classList.remove("go")); setTimeout(() => $$(sel + " .bt").forEach(b => b.classList.add("go")), instant ? 0 : 150); };
  {
    const nf = DR ? DR.folds.split(" ")[0] : "";
    $("#perf-sub").textContent = `balanced accuracy over ${nf} folds of held-out spots, chance 0.33, 90 % intervals; right: where the calls go, then the 3 test spots and the 6 eval spots`;
    $("#perf-bars").innerHTML = (CFG.models || []).map(m => barRow(m.label, m.sub, pick(m.key), m.final ? "me" : "")).join("") + axis(33.3);
    const truth = CFG.truth || {}, T3 = DR && DR.test, one = T3 && T3.one_per_batch;
    let own = 0, joint = 0;
    $("#perf-test").innerHTML = T3 ? T3.spots.map(s => {
      const t = truth[s.sample_id], call = +s.call.slice(-1), j = one ? +one.assignment[s.sample_id].slice(-1) : null;
      own += call === t; joint += j === t;
      const mark = ok => `<span class="mark ${ok ? "ok" : "bad"}">${ok ? "✓" : "✗"}</span>`;
      return `<div class="tcard"><h4>${esc(s.sample_id)}<small>answer <span class="truth" style="color:${bcol(t)}">Batch_${t}</span></small></h4>` +
        `<div class="trow"><span class="who">own call</span><div><div class="pb">${s.p.map((v, i) => `<i class="${i + 1 === call ? "call" : ""}" style="--w:${(100 * v).toFixed(1)}%;background:${bcol(i + 1)}"></i>`).join("")}</div>` +
        `<small>Batch_${call} · ${pct(Math.max(...s.p))}</small></div>${mark(call === t)}</div>` +
        (one ? `<div class="trow best"><span class="who">one per batch</span><small>Batch_${j}</small>${mark(j === t)}</div>` : "") + `</div>`;
    }).join("") : "<p>no test calls</p>";
    // eval spots: what we submitted (2 per batch rule) and how it was marked; the model's own call next to it
    const EV = DR && DR.eval, sub = EV && EV.per_batch_assignment, wrong = new Set(CFG.evalWrong || []);
    let evOk = 0, evOwn = 0;
    $("#perf-eval").innerHTML = EV && sub ? EV.spots.map(s => {
      const id = s.sample_id, call = +s.call.slice(-1), j = +sub.assignment[id].slice(-1), ok = !wrong.has(id), ownOk = ok && call === j;
      evOk += ok; evOwn += ownOk;
      const mark = v => `<span class="mark ${v ? "ok" : "bad"}">${v ? "✓" : "✗"}</span>`;
      return `<div class="tcard"><h4>${esc(id)}<small>${ok ? "marked right" : "marked wrong"}</small></h4>` +
        `<div class="trow"><span class="who">own call</span><div><div class="pb">${s.p.map((v, i) => `<i class="${i + 1 === call ? "call" : ""}" style="--w:${(100 * v).toFixed(1)}%;background:${bcol(i + 1)}"></i>`).join("")}</div>` +
        `<small>Batch_${call} · ${pct(Math.max(...s.p))}</small></div>${mark(ownOk)}</div>` +
        `<div class="trow best"><span class="who">submitted</span><small style="color:${bcol(j)}">Batch_${j}</small>${mark(ok)}</div></div>`;
    }).join("") : "<p>no eval calls</p>";
    // held-out confusion matrices (confusion.js): rows = true batch, columns = called batch
    const CM = window.DEMO_CONFUSION;
    const cmGrid = (name, d, cls) => {
      const mx = Math.max(...d.n);
      return `<div class="cm ${cls}"><h4>${esc(name)}</h4><div class="cmg">` +
        `<span></span>${[1, 2, 3].map(j => `<span class="ch" style="color:${bcol(j)}">B${j}</span>`).join("")}<span class="ch">recall</span>` +
        d.confusion.map((row, i) => `<span class="rh" style="color:${bcol(i + 1)}">B${i + 1}</span>` +
          row.map((v, j) => `<span class="cell ${i === j ? "diag" : ""}" style="--a:${(v / d.n[i]).toFixed(2)}">${v}</span>`).join("") +
          `<span class="rec">${pct(d.recall[i])}</span>`).join("") + `</div></div>`;
    };
    if (CM) $("#perf-cm").innerHTML = cmGrid("V1 alone", CM["V1"], "ref") + cmGrid("V1 + V2", CM["V1 + V2"], "me") +
      `<p class="cmnote">rows = true batch · columns = the model's call · every spot called by a model that never saw it. ` +
      `Adding V2 moves Batch_2 from ${CM["V1"].confusion[1][1]} to ${CM["V1 + V2"].confusion[1][1]} of ${CM["V1"].n[1]} right; Batch_1 stays at ${CM["V1 + V2"].confusion[0][0]} of ${CM["V1"].n[0]}.</p>`;
    slide("perf", {
      builds: EV ? 4 : 3,
      build(b) {
        $("#perf-cm-wrap").style.display = b >= 2 ? "none" : "";
        $("#perf-test-wrap").style.display = b === 2 ? "" : "none";
        $("#perf-eval-wrap").style.display = b === 3 ? "" : "none";
        if (b === 0) { $("#perf-chips").innerHTML = chip("training spots", R.baselines ? R.baselines.n_spots : 31); growBars("#perf-bars"); }
        if (b === 1 && CM) $("#perf-chips").innerHTML = chip("Batch_2 recall", `${pct(CM["V1"].recall[1])} → ${pct(CM["V1 + V2"].recall[1])}`, "ok") +
          chip("Batch_1 recall", pct(CM["V1 + V2"].recall[0])) + chip("Batch_3 recall", pct(CM["V1 + V2"].recall[2]));
        if (b === 2 && T3) $("#perf-chips").innerHTML = chip("own call", `${own} / ${T3.spots.length}`) +
          (one ? chip("one per batch", `${joint} / ${T3.spots.length}`, "ok") + chip("confidence", `${pct(one.confidence)} (next best ${pct(one.runner_up_confidence)})`) : "");
        if (b === 3 && EV) $("#perf-chips").innerHTML = chip("eval spots, submitted", `${evOk} / ${EV.spots.length} right`, "ok") +
          chip("own call", `${evOwn} / ${EV.spots.length}`) + chip("rule", "2 spots per batch");
      },
    });
  }

  // ==============================================================================================================
  // 5  seed ensemble: single V2 seeds next to V1, then the average
  // ==============================================================================================================
  {
    const rows = (CFG.seeds || []).map(m => barRow(m.label, m.final ? "probabilities averaged" : "one V2 run", pick(m.key), m.final ? "me" : "")).join("");
    $("#seed-bars").innerHTML = barRow("V1 alone", "reference", pick("V1 (label-free)"), "ref") + rows + axis(33.3);
    const single = (CFG.seeds || []).filter(m => !m.final).map(m => pick(m.key)).filter(Boolean).map(d => d.bacc);
    const avg = (CFG.seeds || []).filter(m => m.final).map(m => pick(m.key)).find(Boolean);
    if (single.length > 1 && avg) $("#seed-sub").textContent = `the same model retrained with a new random seed scores anywhere from ${fmt(Math.min(...single))} to ${fmt(Math.max(...single))}, ` +
      `so one lucky run is not the score; averaging the ${single.length} runs gives ${fmt(avg.bacc)}, above ${single.filter(v => v < avg.bacc).length} of them and their mean ${fmt(single.reduce((a, b) => a + b, 0) / single.length)}`;
    const VS = (DR && DR.v2_seeds) || {};
    slide("seeds", {
      builds: 1,
      build() {
        $("#seed-chips").innerHTML = Object.entries(VS).filter(([, v]) => v).map(([k, v], i) => chip(`V2 alone, seed ${i}`, fmt(v.bacc))).join("");
        growBars("#seed-bars");
      },
    });
  }

  // ==============================================================================================================
  // 6  feature research: papers -> ledger -> plug-in features -> tests (window.HARNESS)
  // ==============================================================================================================
  {
    if (HZ) {
      const Lg = HZ.ledger, IX = HZ.index || {}, n0 = v => (v ?? 0).toLocaleString("en");
      const nIdx = (IX.amass ? IX.amass.papers : 0) + (IX.paperclip ? IX.paperclip.papers : 0);
      const nCols = Object.values(HZ.plugins || {}).reduce((a, c) => a + c.length, 0), nPlug = Object.keys(HZ.plugins || {}).length;
      const steps = [[n0(nIdx), "papers indexed"], [Lg.n, "ideas in the ledger", `${Lg.papers} papers cited`],
        [nCols, "plug-in features", `from ${nPlug} modules`], [(HZ.tests || []).length, "tests on the spots", "Batch_3 vs the rest"]];
      $("#hz-flow").innerHTML = steps.map(([n, t, s]) => `<div class="fstep"><b>${n}</b><span>${t}</span>${s ? `<small>${s}</small>` : ""}</div>`).join('<i class="farrow">→</i>');
      $("#hz-chips").innerHTML = chip("built", (Lg.status.implemented || 0) + (Lg.status.v1_only || 0)) + chip("dropped after testing", Lg.status.rejected || 0) + chip("citations checked", `${Lg.verified} / ${Lg.papers}`);
    }
    slide("harness", {
      builds: 1,
      build() { const s = $$("#hz-flow .fstep"); s.forEach(e => e.classList.remove("on")); s.forEach((e, i) => setTimeout(() => e.classList.add("on"), instant ? 0 : 150 + 350 * i)); },
    });
  }

  // ==============================================================================================================
  // 7  hand-built features: the top harness tests by AUC, with a 90 % Hanley-McNeil interval
  // ==============================================================================================================
  {
    const fc = CFG.features || {}, n1 = fc.nB3 || 17, n2 = fc.nRest || 14, FQ = R.feature_quality || {};
    const tests = (HZ && HZ.tests ? HZ.tests.slice() : []).filter(t => t.auc3 !== undefined).sort((a, b) => b.auc3 - a.auc3).slice(0, fc.n || 6);
    const se = A => { const q1 = A / (2 - A), q2 = 2 * A * A / (1 + A); return Math.sqrt((A * (1 - A) + (n1 - 1) * (q1 - A * A) + (n2 - 1) * (q2 - A * A)) / (n1 * n2)); };
    $("#feat-bars").innerHTML = tests.map(t => {
      const A = Math.max(t.auc3, 1 - t.auc3), s = se(A), lo = clamp(A - 1.645 * s), hi = clamp(A + 1.645 * s), weak = t.p3 >= 0.05, q = FQ[t.column];
      return `<div class="brow ${weak ? "weak" : ""}"><span class="bl">${esc(flab(t.column))}${q ? `<span class="trust">trust ${esc(q.trust)}</span>` : ""}<small>${esc(t.entry.replace(/_/g, " "))}</small></span>` +
        `<span class="bt"><i style="--w:${(100 * A).toFixed(1)}%"></i><em style="left:50%"></em><span class="ci" style="left:${(100 * lo).toFixed(1)}%;width:${(100 * (hi - lo)).toFixed(1)}%"></span></span>` +
        `<span class="bv num">${fmt(A)}<small>p ${fmt(t.p3, 3)}</small></span></div>`;
    }).join("") + axis(50);
    slide("feat", {
      builds: 1,
      build() {
        $("#feat-chips").innerHTML = chip("features tested", HZ && HZ.tests ? HZ.tests.length : 0) + chip("spots", n1 + n2);
        growBars("#feat-bars");
      },
    });
  }

  // ==============================================================================================================
  // 8  features to outcomes: literature features against the embedding's batch axes, and what papers say they do
  //    (window.PCA.interpret, from cnn/interpret_features.py; Jude's embedding map section)
  // ==============================================================================================================
  {
    const I = window.PCA && window.PCA.interpret, axes = I ? I.axes : [];
    $("#outc-body").innerHTML = axes.map((a, k) => `<div class="oaxis b" data-b="${k}"><h4>${esc(a.what)}<small>${esc(a.check)}</small></h4>` +
      `<div class="orow ohead"><span>feature</span><span>link</span><span>inside sessions</span><span>papers: more of it means</span></div>` +
      a.top.map(t => `<div class="orow"><span>${esc(flab(t.feature))}</span><span class="num">${sgn(t.rho)}</span><span class="num">${t.rho_session === null ? "–" : sgn(t.rho_session)}</span><span>` +
        ((t.outcomes || []).map(o => `<i class="oc ${o.good ? "good" : "bad"}">${o.more ? "▲" : "▼"} ${esc(o.label)} <small>${o.n}</small></i>`).join("") || `<small class="none">no agreed effect yet</small>`) + `</span></div>`).join("") + `</div>`).join("") || "<p>no pca.js</p>";
    $("#outc-sub").textContent = "link = Spearman over the 31 spots; chips = what papers say more of the feature does (number of papers)";
    slide("outc", {
      builds: Math.max(1, axes.length),
      build(b) { $$("#outc-body .oaxis").forEach(e => e.style.display = +e.dataset.b === b ? "" : "none"); $("#outc-chips").innerHTML = I ? chip("literature features", I.n_features) : ""; },
    });
  }

  // start where the hash says
  const m = location.hash.match(/^#(\d+)(?:\.(\d+))?$/);
  const s0 = m ? +m[1] : 0, b0 = m ? +(m[2] || 0) : 0;
  slides[0].el.classList.add("on");
  goTo(s0, b0);
})();
