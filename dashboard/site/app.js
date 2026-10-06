// The pipeline page. Every number and picture comes from pipeline.js (written by dashboard/build.py).
//
// Each .scrolly section is a tall block with a sticky viewport. Scroll position is the single source of truth:
// progress p (0..1) through the block drives the visuals, and `starts` says where each step begins. Prev / Next,
// the step pills, the pipeline map and the keyboard all just scroll to a step's finished state; Play auto-scrolls.
(() => {
  "use strict";
  const D = window.PIPELINE;
  if (!D) {
    document.body.insertAdjacentHTML("afterbegin",
      '<p style="padding:80px 20px">No data: run <code>python dashboard/build.py</code> first.</p>');
    return;
  }
  const P = D.prep, C = D.cnn;
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = t => { t = clamp(t); return t * t * (3 - 2 * t); };
  const pct = v => (100 * v).toFixed(1) + "%";
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SVGNS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs = {}) => {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };
  const decode = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

  // viridis-like ramp, readable in light and dark (each cell carries its own contrast)
  const STOPS = [[68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], [38, 130, 142], [31, 158, 137],
    [53, 183, 121], [110, 206, 88], [181, 222, 43], [253, 231, 37]];
  const LUT = Array.from({ length: 256 }, (_, i) => {
    const x = i / 255 * (STOPS.length - 1), j = Math.min(STOPS.length - 2, Math.floor(x)), f = x - j;
    return STOPS[j].map((v, k) => Math.round(lerp(v, STOPS[j + 1][k], f)));
  });
  const lutCss = v => { const c = LUT[Math.round(clamp(v) * 255)]; return `rgb(${c[0]},${c[1]},${c[2]})`; };

  // an offscreen canvas from a base64 uint8 grid (grey, or through the colour ramp)
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

  // ==========================================================================================================
  // sections, steps, navigation
  // ==========================================================================================================
  const sections = [];
  const stepOf = (sec, p) => { let k = 0; while (k + 1 < sec.starts.length && p >= sec.starts[k + 1]) k++; return k; };
  const stepEnd = (sec, k) => k + 1 < sec.starts.length ? sec.starts[k + 1] : 1;
  const restP = (sec, k) => sec.starts[k] + 0.9 * (stepEnd(sec, k) - sec.starts[k]);   // the step's finished state
  const yAt = (sec, p) => sec.el.offsetTop + (sec.el.offsetHeight - window.innerHeight) * p;
  const pOf = sec => clamp((window.scrollY - sec.el.offsetTop) / ((sec.el.offsetHeight - window.innerHeight) || 1));

  function register(id, { starts, steps, update, layout }) {
    const el = document.getElementById(id);
    el.style.setProperty("--steps", starts.length);
    const sec = { id, el, starts, steps, update, layout, p: undefined, step: -1 };
    sections.push(sec);
    buildCard(sec);
    return sec;
  }

  function buildCard(sec) {
    const card = $(`#${sec.id}-card`);
    $(".card-main", card).innerHTML =
      `<div class="k"><span class="stepno"></span></div>` +
      `<ol class="pills">${sec.steps.map((s, i) => `<li><button type="button" data-k="${i}">${i + 1} ${s.k}</button></li>`).join("")}</ol>` +
      `<div class="caps">${sec.steps.map(s =>
        `<div class="cap"><h3>${s.h}</h3><p>${s.p}</p>${s.stat ? `<span class="stat">${s.stat}</span>` : ""}</div>`).join("")}</div>`;
    $(".card-foot", card).innerHTML =
      `<div class="controls"><button type="button" class="prev">← Prev</button>` +
      `<button type="button" class="play" aria-pressed="false">▶ Play</button>` +
      `<button type="button" class="next">Next →</button></div>` +
      `<p class="hint-small">scroll <span aria-hidden="true">↓</span> or press <kbd>→</kbd> for the next step</p>`;
    $$(".pills button", card).forEach(b => b.addEventListener("click", () => goToStep(sec, +b.dataset.k)));
    $(".prev", card).addEventListener("click", () => goToStep(sec, sec.step - 1));
    $(".next", card).addEventListener("click", () => goToStep(sec, sec.step + 1));
    $(".play", card).addEventListener("click", () => play(sec));
  }

  // Section titles for the pitch: the stage name and the current step ("Preprocessing: Crop"), with the step's short
  // heading as the subtitle. The step cards are hidden (style.css, pitch layout), so this is where a step is named.
  const TITLE = { lanes: "Lanes", prep: "Preprocessing", kernel: "Embedding", match: "Contrastive learning",
    batch: "Baselines", verdict: "Decision", sliders: "Battery sliders", why: "Interpretation", papers: "Interpretation" };

  function setStep(sec, k) {
    if (sec.step === k) return;
    sec.step = k;
    const h2 = $(`#${sec.id} .sec-head h2`), sub = $(`#${sec.id} .sec-head p`);
    if (h2 && TITLE[sec.id]) h2.textContent = `${TITLE[sec.id]}: ${sec.steps[k].k}`;
    if (sub && TITLE[sec.id]) sub.textContent = sec.steps[k].h;
    const card = $(`#${sec.id}-card`);
    $(".stepno", card).textContent = `Step ${k + 1} of ${sec.steps.length} · ${sec.steps[k].k}`;
    $$(".cap", card).forEach((e, i) => e.classList.toggle("on", i === k));
    $$(".pills button", card).forEach((b, i) => { b.classList.toggle("on", i === k); b.classList.toggle("done", i < k); });
  }

  // scroll to step k of a section (past either end: the neighbouring section, or the hero / footer)
  // `target` is where the last goToStep is heading until the scroll settles there, so quick repeated key presses
  // build on it instead of re-reading the step the page has not reached yet; a wheel or touch clears it.
  let target = null;
  function goToStep(sec, k) {
    stopPlay();
    const i = sections.indexOf(sec), behavior = reduced ? "auto" : "smooth";
    if (k < 0) {
      if (i === 0) { target = null; return window.scrollTo({ top: 0, behavior }); }
      sec = sections[i - 1]; k = sec.starts.length - 1;
    } else if (k >= sec.starts.length) {
      if (i === sections.length - 1) { target = null; return window.scrollTo({ top: $("#next").offsetTop - 60, behavior }); }
      sec = sections[i + 1]; k = 0;
    }
    target = { sec, k };
    window.scrollTo({ top: yAt(sec, restP(sec, k)), behavior });
  }

  // Play: auto-scroll through the current step (or the next one if this one is already finished)
  let playing = null;
  function stopPlay() {
    if (!playing) return;
    cancelAnimationFrame(playing.raf);
    playing = null;
    document.documentElement.style.scrollBehavior = "";
    $$(".card .play").forEach(b => { b.textContent = "▶ Play"; b.setAttribute("aria-pressed", "false"); });
  }
  function play(sec) {
    if (playing) return stopPlay();
    let p = pOf(sec), k = stepOf(sec, p), y0 = window.scrollY;
    if (p >= restP(sec, k) - 0.02) {
      k++;
      if (k >= sec.starts.length) {
        const i = sections.indexOf(sec);
        if (i + 1 >= sections.length) return;
        sec = sections[i + 1]; k = 0;
      }
      y0 = yAt(sec, sec.starts[k]);
    }
    const y1 = yAt(sec, restP(sec, k));
    const dur = reduced ? 0 : 6000 * (stepEnd(sec, k) - sec.starts[k]) * sec.starts.length;   // ~6 s for an average step
    document.documentElement.style.scrollBehavior = "auto";
    const btn = $(`#${sec.id}-card .play`);
    btn.textContent = "❚❚ Pause"; btn.setAttribute("aria-pressed", "true");
    const t0 = performance.now();
    playing = { raf: 0 };
    const tick = now => {
      const u = dur ? clamp((now - t0) / dur) : 1;
      window.scrollTo(0, lerp(y0, y1, u));
      if (u < 1) playing.raf = requestAnimationFrame(tick); else stopPlay();
    };
    playing.raf = requestAnimationFrame(tick);
  }
  const userScrolls = () => { stopPlay(); target = null; };
  window.addEventListener("wheel", userScrolls, { passive: true });
  window.addEventListener("touchmove", userScrolls, { passive: true });

  // ==========================================================================================================
  // 00  where the data comes from: the lanes  (present when dashboard/lanes.py has written lanes.js)
  // ==========================================================================================================
  const LN = window.LANES;
  const firstNodes = [], firstThumbs = [];
  if (!LN) $("#lanes").remove();
  else {
    const bs = LN.batch_sizes, ev = LN.evidence, nl = LN.lanes.length;
    const spots = LN.lanes.flatMap((l, li) => l.spots.map(s => ({ ...s, lane: l.id, li, mixed: l.mixed })));
    const byId = Object.fromEntries(spots.map(s => [s.id, s]));
    const mixed = LN.lanes.filter(l => l.mixed);
    const nBatches = l => new Set(l.spots.map(s => s.batch)).size;
    const nCross = l => l.spots.filter(s => s.join === "cross").length;
    const showLane = LN.lanes.reduce((a, l) => nCross(l) > nCross(a) ? l : a);      // the lane with the most joins across batch folders
    const toUm = px => Math.round(px * D.spot.pixel_um), seamUm = toUm(LN.seam_side_px);
    const hMin = Math.min(...LN.lanes.map(l => l.session_px)), hMax = Math.max(...LN.lanes.map(l => l.session_px));   // image heights, in rows
    const canvas = $("#lanes-canvas"), stage = $("#lanes-stage");

    // ---- the spots (one picture each) and the things drawn around them -----------------------------------------
    const add = (cls, html = "") => { const e = document.createElement("div"); e.className = cls; e.innerHTML = html; canvas.appendChild(e); return e; };
    const folders = [1, 2, 3].map(b => ({ b, box: add(`lfurn lfold b${b}`), head: add(`lfurn lhead b${b}`, `<b>Batch_${b}</b><small>${bs[b]} spots</small>`) }));
    spots.forEach(s => {
      s.el = add(`lspot b${s.batch}${s.mixed ? " mixed" : ""}`,
        `<img src="${s.img}" alt="" draggable="false"><span class="bb">B${s.batch}</span><span class="sid">${s.id}</span>${s.edge ? `<i class="lcap ${s.edge === "left" ? "l" : "r"}"></i>` : ""}`);
      s.el.title = `${s.id} · Batch_${s.batch} · lane ${s.lane}`;
    });
    const bits = LN.lanes.map(l => {
      const m = l.mixed ? " mixed" : "";
      return { label: add(`lfurn llabel${m}`, `Lane ${l.id}<small>${l.session_px} rows</small>`),
        gaps: l.spots.slice(0, -1).filter(s => !s.touches_next).map(() => add(`lfurn lgap${m}`, "…")),
        dias: l.spots.slice(0, -1).filter(s => s.join === "cross").map(() => add(`lfurn ldia${m}`)) };
    });

    // ---- where everything sits: as three folders, and as 13 lanes -----------------------------------------------
    let G = null;
    function layoutLanes() {
      const W = stage.clientWidth, H = stage.clientHeight;
      if (!W || !H) return;
      const LW = 64, GX = 6, GY = Math.round(clamp(H / 90, 4, 9)), GG = 30, HEAD = 40, GAPW = 0.28, R = 7;
      const cols = [1, 2, 3].map(b => Math.ceil(bs[b] / R)), nCols = cols.reduce((a, b) => a + b, 0);
      const maxAsp = Math.max(...spots.map(s => s.aspect));
      const laneAsp = LN.lanes.map(l => Math.max(...l.spots.map(s => s.aspect)));
      const units = LN.lanes.map(l => l.spots.length + GAPW * l.spots.slice(0, -1).filter(s => !s.touches_next).length);
      // one spot size for both layouts, the largest that fits the stage in each
      const bw = Math.floor(clamp(Math.min(
        (W - LW - 8) / Math.max(...units),
        (H - 4 - GY * (nl - 1)) / laneAsp.reduce((a, b) => a + b, 0),
        (W - 8 - GX * (nCols - 3) - GG * 2) / nCols,
        (H - HEAD - 8 - GY * (R - 1)) / (R * maxAsp)), 34, 260));
      const laneH = laneAsp.map(a => Math.round(a * bw));
      spots.forEach(s => { s.el.style.width = bw + "px"; s.el.style.height = laneH[s.li] + "px"; });

      // three folders: a tidy grid each, the spots in file-name order (which says nothing about where they came from)
      const pitch = maxAsp * bw + GY, gridW = nCols * bw + (nCols - 3) * GX + 2 * GG, gridH = HEAD + R * pitch - GY;
      let x = Math.max(8, (W - gridW) / 2);
      const y0 = Math.max(6, (H - gridH) / 2);
      folders.forEach((f, i) => {
        const w = cols[i] * bw + (cols[i] - 1) * GX;
        spots.filter(s => s.batch === f.b).sort((a, c) => a.id < c.id ? -1 : 1)
          .forEach((s, j) => { s.A = { x: x + Math.floor(j / R) * (bw + GX), y: y0 + HEAD + (j % R) * pitch }; });
        Object.assign(f.box.style, { left: x - 9 + "px", top: y0 - 6 + "px", width: w + 18 + "px", height: gridH + 12 + "px" });
        Object.assign(f.head.style, { left: x + 2 + "px", top: y0 + 2 + "px" });
        x += w + GG;
      });

      // the lanes: one row each, spots in order along it; neighbours that touch are drawn touching
      const total = laneH.reduce((a, b) => a + b, 0) + GY * (nl - 1), x0 = 4;
      let y = Math.max(0, (H - total) / 2);
      LN.lanes.forEach((l, i) => {
        let cx = x0 + LW, gi = 0, di = 0;
        const put = (el, left, top, w, h) => Object.assign(el.style, { left: left + "px", top: top + "px", width: w ? w + "px" : "", height: h ? h + "px" : "" });
        put(bits[i].label, x0, y, LW - 6, laneH[i]);
        l.spots.forEach((sp, k) => {
          byId[sp.id].B = { x: cx, y };
          cx += bw;
          if (k === l.spots.length - 1) return;
          if (!sp.touches_next) { put(bits[i].gaps[gi++], cx, y, GAPW * bw, laneH[i]); cx += GAPW * bw; }
          else if (sp.join === "cross") put(bits[i].dias[di++], cx, y + laneH[i] / 2 - 6);
        });
        y += laneH[i] + GY;
      });
      bits.forEach(b => b.label.classList.toggle("tight", Math.min(...laneH) < 30));
      const laneW = LW + Math.max(...units) * bw + 8, askW = Math.min(0.36 * W, 310);
      stage.dataset.narrow = W < 640 ? "1" : "";
      G = { s4: W < 640 ? 1 : clamp((W - askW - 24) / laneW, 0.45, 1) };
    }

    // ---- scroll progress -> picture -----------------------------------------------------------------------------
    const E0 = 0.34, E1 = 0.30;                          // the spots move while p runs from E0 to E0 + E1
    function paintLanes(p, step) {
      stage.dataset.step = step;
      $$(".layer", stage).forEach(l => l.classList.toggle("on", l.dataset.show.split(" ").includes(String(step))));
      if (!G) return;
      const E = clamp((p - E0) / E1), tLane = [];
      LN.lanes.forEach((l, i) => { tLane[i] = smooth((E - 0.45 * i / (nl - 1)) / 0.55); });     // lane after lane, top to bottom
      spots.forEach(s => {
        const t = tLane[s.li];
        s.el.style.transform = `translate(${lerp(s.A.x, s.B.x, t).toFixed(1)}px,${lerp(s.A.y, s.B.y, t).toFixed(1)}px)`;
      });
      folders.forEach(f => { const o = 1 - smooth(E / 0.25); f.box.style.opacity = o; f.head.style.opacity = o; });
      bits.forEach((b, i) => {
        const o = smooth((tLane[i] - 0.85) / 0.15);
        [b.label, ...b.gaps, ...b.dias].forEach(e => { e.style.opacity = o; });
      });
      canvas.style.transform = `scale(${lerp(1, G.s4, smooth((p - 0.85) / 0.08)).toFixed(3)})`;   // make room for the question
    }

    // ---- the seam examples ---------------------------------------------------------------------------------------
    const tag = (s, cls = "") => `<span class="tag ${cls}" style="--bc:var(--c${s.batch})">Batch_${s.batch}<span class="sid-t"> · ${s.id}</span></span>`;
    $("#lanes-seams").innerHTML =
      `<div class="sstrip-row">${showLane.spots.map(s => `<figure class="b${s.batch}"><img src="${s.img}" alt="Spot ${s.id}, Batch_${s.batch}">${tag(s)}</figure>`).join("")}` +
      showLane.spots.map((s, i) => s.join === "cross" ? `<i class="sdia" style="left:${(100 * (i + 1) / showLane.spots.length).toFixed(2)}%"></i>` : "").join("") + `</div>` +
      `<div class="seam-grid">${LN.seams.map(sm =>
        `<figure class="sclose"><img src="${sm.img}" alt="Joint between spots ${sm.left} and ${sm.right}"><span class="sline"></span>` +
        `${tag({ batch: sm.left_batch, id: sm.left })}${tag({ batch: sm.right_batch, id: sm.right }, "r")}<figcaption>edge match ${sm.score.toFixed(2)}</figcaption></figure>`).join("")}</div>` +
      `<p class="seam-note">Top: lane ${showLane.id}, three spots in a row, from ${nBatches(showLane)} different batch folders. Below: the ${LN.seams.length} joins that cross a folder, ${seamUm} µm either side (BSE, display contrast only). Yellow line: where one image ends and the next begins. Edge match: how well the two touching pixel columns agree (1 = identical).</p>`;

    // ---- the story ------------------------------------------------------------------------------------------------
    const nMixed = mixed.length, nMixedSpots = mixed.reduce((a, l) => a + l.spots.length, 0), allThree = LN.lanes.filter(l => nBatches(l) === 3);
    register("lanes", {
      starts: [0, 0.17, E0, E0 + E1 + 0.06, 0.85],
      steps: [
        { k: "Folders", h: `${LN.n_spots} spots in three batch folders`,
          p: `This is how the data arrives: <b>${bs[1]}</b> spots in Batch_1, <b>${bs[2]}</b> in Batch_2 and <b>${bs[3]}</b> in Batch_3 (the baseline). A <b>spot</b> is one imaged place: a picture of the electrode material about ${toUm(D.prep.raw.w)} × ${toUm(hMin)}–${toUm(hMax)} µm, taken by three detectors at once (Polaron calls it a crop). Polaron's own in-house model decided which folder each spot goes in; we are trying to rediscover how.`,
          stat: `${LN.n_spots} spots · 3 batches` },
        { k: "Seams", h: "Some spots turn out to be neighbours",
          p: `The right edge of one spot picks up where the left edge of another begins, even when the two sit in different batch folders (red ◆). The texture runs straight across the yellow line.`,
          stat: `edge match ${ev.cross_min.toFixed(2)}–${ev.cross_max.toFixed(2)} on the ${ev.cross} folder-crossing joins · unrelated spots: ${ev.random_mean.toFixed(2)} on average, ${ev.random_max.toFixed(2)} at most` },
        { k: "Grouping", h: `The spots fall into ${nl} lanes`,
          p: `Follow the joins and group spots by image height, and every spot lands on one of <b>${nl}</b> long lines of material, each imaged in one session (the sections below say "session"). Polaron confirmed ${nl} lanes, all cut from one huge line made of blocks, which would explain the edges in some source images (▌).`,
          stat: `${LN.n_spots} spots · ${nl} lanes · ${ev.joins} joins` },
        { k: "Mixed", h: "A lane holds several batches",
          p: `<b>${nMixed} of ${nl}</b> lanes hold more than one batch${allThree.length ? `, lane ${allThree.map(l => l.id).join(" and ")} all three` : ""}. Spots sit side by side along a lane; nothing is stacked. So a batch is <i>variation within a lane</i>, not a place or a delivery, and a bad batch can come from the same lane as a good one. That is by design.`,
          stat: `${nMixedSpots} of ${LN.n_spots} spots sit in a mixed lane` },
        { k: "Which lane?", h: "A new spot has no lane label",
          p: `We do not know which lane a new spot came from, and Polaron's model sorts batches by rules we cannot see. We rediscover them from the images, with features we can explain and check against the battery literature. A model that merely recognises the lane would fail on a lane it has not seen, so the main score below holds out a whole lane.`,
          stat: `new spot → lane ? → batch ?` },
      ],
      layout: layoutLanes,
      update: paintLanes,
    });

    firstNodes.push({ label: "Lanes", line: `${LN.n_spots} spots, ${nl} lanes, batches vary within a lane`, sec: "lanes", steps: [0, 1, 2, 3, 4] });
    firstThumbs.push((() => {
      const c = document.createElement("canvas"), g = c.getContext("2d"), rh = 72 / nl;
      c.width = 128; c.height = 72;
      LN.lanes.forEach((l, i) => {
        let x = 6;
        l.spots.forEach(s => { g.fillStyle = ["", "#4f5bd5", "#d9622b", "#12937f"][s.batch]; g.fillRect(x, i * rh + 0.5, 26, rh - 1); x += 26 + (s.touches_next ? 0 : 5); });
      });
      return c.toDataURL();
    })());
  }

  // ==========================================================================================================
  // 01  preprocessing
  // ==========================================================================================================
  const S = D.spot, crop = P.crop, win = P.window, chosen = P.tiles.chosen;
  const heights = P.anchor.spots.map(s => s.height);
  const tileName = `r${chosen.row} c${chosen.col}`;
  const heroSpot = $("#hero-spot");                       // index.html no longer has a lede; _shot.html still does
  if (heroSpot) heroSpot.textContent = `${S.batch} / ${S.sample_id}`;

  // raw frames with the crop overlay
  const frames = $("#frames"), frameStates = [];
  [["bse", "BSE"], ["inlens", "Inlens"], ["se", "SE"]].forEach(([d, label]) => {
    const f = document.createElement("div");
    f.className = "frame";
    f.innerHTML = `<img src="${P.raw.img[d]}" alt="Raw ${label} image"><span class="tag">${label} <em class="state"></em></span>`;
    frameStates.push($(".state", f));
    const W = P.raw.w, H = P.raw.h;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", class: "crop-ov" });
    const pat = svgEl("pattern", { id: "hatch-" + d, patternUnits: "userSpaceOnUse", width: 70, height: 70, patternTransform: "rotate(45)" });
    pat.appendChild(svgEl("rect", { width: 30, height: 70, fill: "var(--hatch)" }));
    svg.appendChild(pat);
    svg.appendChild(svgEl("path", { "fill-rule": "evenodd", fill: "var(--shade)",
      d: `M0 0H${W}V${H}H0Z M${crop.c0} ${crop.r0}H${crop.c1}V${crop.r1}H${crop.c0}Z` }));
    svg.appendChild(svgEl("rect", { x: 0, y: 0, width: W, height: crop.top, fill: `url(#hatch-${d})` }));
    svg.appendChild(svgEl("rect", { x: 0, y: H - crop.bottom, width: W, height: crop.bottom, fill: `url(#hatch-${d})` }));
    svg.appendChild(svgEl("rect", { x: crop.c0, y: crop.r0, width: crop.c1 - crop.c0, height: crop.r1 - crop.r0,
      fill: "none", stroke: "var(--accent)", "stroke-width": 2.5, "vector-effect": "non-scaling-stroke" }));
    f.appendChild(svg);
    frames.appendChild(f);
  });

  // anchoring images + histogram morph
  $("#anchor-raw").src = win.img.bse_raw;
  $("#anchor-done").src = win.img.bse;
  const spotColours = ["--c1", "--c2", "--c3"];
  $("#anchor-legend").innerHTML = P.anchor.spots.map((s, i) =>
    `<span><i style="background:var(${spotColours[i]})"></i>${s.label} · ${s.height} rows</span>`).join("");
  function drawAnchor(t) {
    const svg = $("#anchor-svg"), W = Math.max(300, svg.clientWidth), H = Math.max(120, svg.clientHeight);
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.innerHTML = "";
    const base = H - 26, top = 8;
    const [r0, r1] = P.anchor.raw_range, [u0, u1] = P.anchor.unit_range;
    const xr = g => (g - r0) / (r1 - r0) * W, xu = u => (u - u0) / (u1 - u0) * W;
    const ax = svgEl("g", { class: "axis" });
    ax.appendChild(svgEl("line", { x1: 0, x2: W, y1: base, y2: base }));
    const tick = (x, label, op) => {
      if (op < 0.02 || x < -1 || x > W + 1) return;
      ax.appendChild(svgEl("line", { x1: x, x2: x, y1: base, y2: base + 5, opacity: op }));
      const tx = svgEl("text", { x, y: base + 20, "text-anchor": "middle", opacity: op, style: "font-size:12px" });
      tx.textContent = label;
      ax.appendChild(tx);
    };
    [0, 50, 100, 150, 200, 250].forEach(g => tick(xr(g), g, 1 - t));
    [0, 1, 2, 3].forEach(u => tick(xu(u), u === 0 ? "0 black" : u === 1 ? "1 graphite" : u, t));
    const unitLabel = svgEl("text", { x: W, y: top + 10, "text-anchor": "end", style: "font-size:12px;font-weight:600" });
    unitLabel.textContent = t < 0.5 ? "BEFORE · raw grey level (0–255)" : "AFTER · graphite units";
    ax.appendChild(unitLabel);
    svg.appendChild(ax);
    const clip = svgEl("clipPath", { id: "anchor-clip" });
    clip.appendChild(svgEl("rect", { x: 0, y: 0, width: W, height: base + 1 }));
    svg.appendChild(clip);
    const plot = svgEl("g", { "clip-path": "url(#anchor-clip)" });
    svg.appendChild(plot);
    P.anchor.spots.forEach((s, i) => {
      const col = `var(${spotColours[i]})`, span = s.graphite - s.black;
      const X = g => lerp(xr(g), xu((g - s.black) / span), t);
      const pts = s.hist.map((h, g) => `${X(g).toFixed(1)},${(base - h * (base - top - 14)).toFixed(1)}`);
      plot.appendChild(svgEl("path", { d: `M${X(0)},${base}L${pts.join("L")}L${X(255)},${base}Z`, fill: col, opacity: 0.12 }));
      plot.appendChild(svgEl("path", { d: "M" + pts.join("L"), fill: "none", stroke: col, "stroke-width": 2 }));
      [s.black, s.graphite].forEach(g => plot.appendChild(svgEl("line", {
        x1: X(g), x2: X(g), y1: top + 14, y2: base, stroke: col, "stroke-width": 1.5, "stroke-dasharray": "4 4", opacity: 0.8 })));
    });
  }

  // noise
  $("#noise-before").src = P.noise.before;
  $("#noise-after").src = P.noise.after;
  const um = (P.noise.size * S.pixel_um).toFixed(0);
  $("#noise-before-cap").innerHTML = `noise σ <b>${P.noise.bse_sigma.toFixed(3)}</b>`;
  $("#noise-after-cap").innerHTML = `noise σ <b>${P.noise.bse_target}</b> (+${P.noise.bse_added.toFixed(3)} added)<br><small>${P.noise.size} × ${P.noise.size} px (${um} µm) zoom inside tile ${tileName}</small>`;

  // rank
  $("#rank-inl-raw").src = win.img.inlens_raw; $("#rank-inl").src = win.img.inlens;
  $("#rank-se-raw").src = win.img.se_raw; $("#rank-se").src = win.img.se;
  function histPaths(svg, raw, ranked) {
    const area = h => {
      const n = h.length;
      return `M0,80` + h.map((v, i) => `L${(i / (n - 1) * 200).toFixed(1)},${(80 - v * 74).toFixed(1)}`).join("") + "L200,80Z";
    };
    svg.innerHTML = "";
    const a = svgEl("path", { d: area(raw), fill: "var(--muted)" }), b = svgEl("path", { d: area(ranked), fill: "var(--accent)" });
    svg.append(a, b);
    return [a, b];
  }
  const rankHist = [histPaths($("#rank-inl-hist"), P.rank.inlens_raw, P.rank.inlens),
    histPaths($("#rank-se-hist"), P.rank.se_raw, P.rank.se)];

  // segment + tiles
  $("#seg-bse").src = win.img.bse;
  $("#seg-overlay").src = win.img.overlay;
  $("#seg-legend").innerHTML =
    `<span><i style="background:var(--pore)"></i>pores <b>${pct(P.seg.porosity)}</b> (threshold ${P.seg.t_void.toFixed(2)})</span>` +
    `<span><i style="background:var(--si)"></i>Si-like <b>${pct(P.seg.bright_frac)}</b> (threshold ${P.seg.t_bright.toFixed(2)})</span>`;
  const gsvg = $("#grid-svg");
  gsvg.setAttribute("viewBox", `0 0 ${win.w} ${win.h}`);
  const tileRects = P.tiles.grid.map(([r, c, y, x]) => {
    const rect = svgEl("rect", { x, y, width: P.tiles.size, height: P.tiles.size, "vector-effect": "non-scaling-stroke" });
    if (r === chosen.row && c === chosen.col) rect.classList.add("chosen");
    gsvg.appendChild(rect);
    return rect;
  });
  $("#planes").innerHTML = [["bse", "BSE"], ["inlens", "Inlens"], ["se", "SE"], ["void", "pores"], ["bright", "Si-like"]]
    .map(([k, l]) => `<figure><img src="${chosen.planes[k]}" alt="${l} plane of tile ${tileName}"><figcaption>${l}</figcaption></figure>`).join("");

  const N_PREP = 7;
  register("prep", {
    starts: Array.from({ length: N_PREP }, (_, i) => i / N_PREP),
    steps: [
      { k: "Raw", h: "Three detectors, one place",
        p: `Each spot is imaged by three detectors at once: <b>BSE</b> (composition: heavier atoms look brighter), <b>Inlens</b> and <b>SE</b> (surface and edges). ${P.raw.w} × ${P.raw.h} px at ${S.pixel_um * 1000} nm per pixel.`,
        stat: `image height ${P.raw.h} rows: on its own it reveals which microscope session took it` },
      { k: "Crop", h: "Same window for every image",
        p: `Drop the top ${crop.top} rows (frame artefact, hatched) and the bottom ${crop.bottom} (current-collector band), then keep the central ${crop.height} rows. Every spot now covers exactly the same area, so image size can no longer leak the session.`,
        stat: `heights ${[...new Set(heights)].join(", ")} … → all ${win.h} × ${win.w} px` },
      { k: "Anchor", h: "Put BSE on a physical scale",
        p: `Grey levels are rescaled so that 0 is the image's own black level and 1 is its graphite peak. Three spots from three sessions start out shifted and stretched; after anchoring their histograms line up.`,
        stat: `this spot: black ${P.anchor.spots[0].black} → 0 · graphite ${P.anchor.spots[0].graphite} → 1` },
      { k: "Noise", h: "Same noise level everywhere",
        p: `Gaussian noise is added until every image reaches the same noise level, so images from quiet sessions don't look cleaner, and edge or particle counts aren't biased by the session.`,
        stat: `BSE noise σ ${P.noise.bse_sigma.toFixed(3)} + ${P.noise.bse_added.toFixed(3)} added → ${P.noise.bse_target}` },
      { k: "Rank", h: "Inlens and SE: keep only the order",
        p: `These detectors have no physical grey scale, so each pixel is replaced by its rank (0 = darkest, 1 = brightest). The histogram becomes flat, and any brightness or contrast setting is gone.`,
        stat: "histogram: lumpy → flat" },
      { k: "Segment", h: "Find pores and the silicon phase",
        p: `Pores (blue) are darker than an Otsu threshold between the pore and graphite peaks. Si-like particles (amber) are brighter than the midpoint between graphite and the image's own Si peak. Both thresholds come from the image itself.`,
        stat: `porosity ${pct(P.seg.porosity)} · Si-like ${pct(P.seg.bright_frac)}` },
      { k: "Tile", h: `Cut into ${P.tiles.grid.length} tiles`,
        p: `The window is cut into a centred grid of ${P.tiles.size} × ${P.tiles.size} px tiles (${P.tiles.um} µm), each with five planes. Tile <b>${tileName}</b> (outlined) continues into the CNN.`,
        stat: `tile ${tileName}: porosity ${pct(chosen.porosity)} · Si-like ${pct(chosen.bright_frac)}` },
    ],
    layout() {   // three stacked 3:1 frames must fit the stage height
      const stage = $("#prep-stage");
      frames.style.width = Math.max(160, Math.min(stage.clientWidth, (stage.clientHeight - 20) * P.raw.w / P.raw.h / 3)) + "px";
    },
    update(p, step) {
      const t = clamp(p * N_PREP - step);
      const stage = $("#prep-stage");
      stage.dataset.step = step;
      $$(".layer", stage).forEach(l => l.classList.toggle("on", l.dataset.show.split(" ").includes(String(step))));
      if (step <= 1) frameStates.forEach(e => e.textContent = step === 0 ? `· raw · ${P.raw.h} rows` : `· same window · ${win.h} rows kept`);
      if (step === 2) {
        const m = smooth((t - 0.08) / 0.6);
        drawAnchor(m);
        $("#anchor-done").style.opacity = m;
        $("#tag-anchor").textContent = m < 0.5 ? "BEFORE · BSE, raw grey levels" : "AFTER · BSE in graphite units";
      }
      if (step === 4) {
        const m = smooth((t - 0.1) / 0.55);
        $("#rank-inl").style.opacity = m; $("#rank-se").style.opacity = m;
        rankHist.forEach(([a, b]) => { a.style.opacity = 0.55 * (1 - m); b.style.opacity = 0.85 * m; });
        const lab = m < 0.5 ? "BEFORE · raw" : "AFTER · rank-normalised";
        $("#tag-inl").textContent = `Inlens · ${lab}`; $("#tag-se").textContent = `SE · ${lab}`;
      }
      if (step === 5 || step === 6) {
        $("#seg-overlay").style.opacity = step === 5 ? smooth(t / 0.45) : lerp(1, 0.15, smooth(t / 0.3));
        $("#seg-legend").style.display = step === 5 ? "" : "none";
        const shown = step === 6 ? Math.floor(smooth(t / 0.55) * tileRects.length + 0.001) : 0;
        tileRects.forEach((r, i) => r.classList.toggle("on", i < shown));
        $("#planes").classList.toggle("on", step === 6 && t > 0.5);
        $("#tag-seg").textContent = step === 5 ? "BSE + overlay · pores (blue) · Si-like (amber)" : `${P.tiles.grid.length} tiles · tile ${tileName} outlined`;
      }
    },
  });

  // ==========================================================================================================
  // 02  the kernel  (MaterialNet: one shared kernel over BSE and Inlens separately; FusionNet: one 3-plane kernel)
  // ==========================================================================================================
  const K = C.kernel, G = K.grid, FUSION = C.fusion === "early", run = C.run;
  const DET_LABEL = { bse: "BSE", inlens: "Inlens", se: "SE" };
  const PLANES = FUSION ? K.planes : ["bse", "inlens"];          // input planes shown
  const DETS = FUSION ? ["fused"] : ["bse", "inlens"];           // encoder outputs shown (one column each)
  const KS = K.k || 3, KK = KS * KS, KH = Math.floor(KS / 2);    // kernel side, pixels under it, half width
  const KCELL = FUSION ? (KS > 3 ? 8 : 14) : (KS > 3 ? 11 : 20); // px per cell in the arithmetic grids
  const SCAN_END = 0.42;                                         // p at which the kernel has swept the whole tile
  const minmax = a => { let lo = Infinity, hi = -Infinity; for (const v of a) { if (v < lo) lo = v; if (v > hi) hi = v; } return { lo, hi }; };
  const sampleOf = (pos, d, i) => FUSION ? K.samples[pos].slice(i * KK, (i + 1) * KK) : K.samples[d][pos].slice(0, KK);
  const outOf = (pos, d) => { const s = FUSION ? K.samples[pos] : K.samples[d][pos]; return s[s.length - 1]; };
  const weightsOf = d => FUSION ? K.weights[d] : K.weights;
  const fmapRange = d => FUSION ? K.fmap_range : K.fmap_range[d];
  const kOff = {}, kAll = {};
  PLANES.forEach((d, i) => {
    kOff[d] = { input: gridCanvas(K.input[d], K.display, false) };
    kAll[d] = minmax((FUSION ? K.samples : K.samples[d]).flatMap((_, pos) => sampleOf(pos, d, i)));
  });
  DETS.forEach(d => { kOff[d] = { ...(kOff[d] || {}), fmap: gridCanvas(FUSION ? K.fmap : K.fmap[d], K.display, true) }; });
  const wMax = Math.max(...PLANES.flatMap(d => weightsOf(d).map(Math.abs)));
  $("#kernel-h2").textContent = FUSION ? "One tile, three detectors in, one kernel" : "One tile, two detectors, one kernel";
  $("#kernel-sub").textContent = FUSION
    ? `one learned ${KS}×${KS}×3 kernel (channel ${K.channel} of ${K.n_channels} in layer 1) reads the BSE, Inlens and SE planes of tile ${tileName} at once`
    : `the same learned ${KS}×${KS} kernel (channel ${K.channel} of ${K.n_channels} in layer 1) slides over the BSE and the Inlens image of tile ${tileName}`;
  const heroHow = $("#hero-how");
  if (heroHow) heroHow.textContent = FUSION
    ? "a CNN reads the three detector images of a tile at once and learns to pull tiles of the same batch together and push the other batches apart."
    : "a CNN learns what the material looks like by matching what two different detectors see of the same tile.";

  const st = C.stages, last = st[st.length - 1];
  const wtGrid = (cls, d) => `<div class="g3 ${cls}" data-plane="${d}" style="--cell:${KCELL}px;grid-template-columns:repeat(${KS},var(--cell))">${"<span></span>".repeat(KK)}</div>`;
  if (FUSION) {
    // rebuild the stage for early fusion: three inputs in, one map out
    const kg = $(".kernel-grid");
    kg.classList.add("fusion");
    kg.innerHTML =
      `<div class="det" data-det="in"><h3>${PLANES.map(d => `<i class="sw ${d}"></i>`).join("")}Three detectors in <small>one 3-plane image of the same tile</small></h3>` +
      `<div class="scan3">${PLANES.map(d => `<div class="cwrap"><canvas class="in" data-plane="${d}"></canvas><span class="tag">${DET_LABEL[d]}</span></div>`).join("")}</div>` +
      `<div class="math math3">${PLANES.map((d, i) => `<div class="mrow"><span class="lbl" style="color:var(--${d})">${DET_LABEL[d]}</span>${wtGrid("px", d)}<span class="op">×</span>${wtGrid("wt", d)}<span class="op">${i < PLANES.length - 1 ? "+" : "="}</span></div>`).join("")}` +
      `<div class="mrow"><span class="lbl">pixels under the kernel × that plane's weights, summed over the three planes → one map pixel</span><span class="out num">0</span></div></div></div>` +
      `<div class="det" data-det="fused"><h3><i class="sw fused"></i>One kernel, one map <small>channel ${K.channel} of ${K.n_channels} in layer 1</small></h3>` +
      `<div class="scan"><div class="cwrap"><canvas class="fm"></canvas><span class="tag tag-fm">feature map · ch ${K.channel}</span></div></div>` +
      `<div class="stages"></div><div class="zwrap"><span class="zlab"></span><canvas class="zbar"></canvas></div></div>`;
  }
  const inCol = FUSION ? $('.det[data-det="in"]') : null;
  const kin = {}, kd = {};
  PLANES.forEach(d => {
    const root = FUSION ? inCol : $(`.det[data-det="${d}"]`);
    if (!FUSION) {
      $(".math", root).innerHTML =
        `<div><span class="lbl">pixels under the kernel</span>${wtGrid("px", d)}</div><span class="op">×</span>` +
        `<div><span class="lbl">kernel weights</span>${wtGrid("wt", d)}</div><span class="op">=</span>` +
        `<div><span class="lbl">sum → map pixel</span><span class="out num">0</span></div>`;
      $(".tag-in", root).textContent = `input · ${DET_LABEL[d]} tile`;
    }
    const w = weightsOf(d);
    $$(`.wt[data-plane="${d}"] span`, root).forEach((s, i) => {
      s.style.background = `color-mix(in srgb, var(${w[i] >= 0 ? "--good" : "--bad"}) ${Math.round(18 + 82 * Math.abs(w[i]) / wMax)}%, transparent)`;
      s.title = `weight ${w[i]}`;
    });
    kin[d] = { in: FUSION ? $(`canvas.in[data-plane="${d}"]`, root) : $(".in", root), px: $$(`.px[data-plane="${d}"] span`, root) };
  });
  DETS.forEach(d => {
    const root = $(`.det[data-det="${d}"]`);
    $(".stages", root).innerHTML = st.map(s =>
      `<figure><canvas></canvas><figcaption>stage ${s.stage}<br>${s.res}² · ${s.channels} ch</figcaption></figure>`).join("");
    if (!FUSION) $(".tag-fm", root).textContent = `feature map · ch ${K.channel}`;
    $(".zlab", root).textContent = FUSION ? `z · ${C.z.fused.length} numbers · the whole tile` : `z · ${C.z[d].length} numbers · ${DET_LABEL[d]}`;
    kd[d] = { root, fm: $(".fm", root), out: $(".out", FUSION ? inCol : root),
      stageCvs: $$(".stages canvas", root), stageFigs: $$(".stages figure", root), zbar: $(".zbar", root), zlab: $(".zlab", root),
      stageOff: st.map(s => gridCanvas(s.maps[d], s.size, true)) };
  });

  let cv = 220, cin = 220;
  function layoutKernel() {
    const grid = $(".kernel-grid"), narrow = window.innerWidth <= 760;
    const colW = narrow ? grid.clientWidth : (grid.clientWidth - 24) / 2;
    const availH = grid.clientHeight;
    if (FUSION) {
      // input column: heading + three inputs in a row + four arithmetic rows; output column: map + stage maps + z bar
      cin = Math.max(70, Math.floor(Math.min((colW - 16) / 3, availH * (narrow ? 0.22 : 0.34))));
      cv = Math.max(90, Math.floor(Math.min(colW - 40, narrow ? availH * 0.3 : (availH - 230) / 1.42)));
    } else {
      // column = heading + scan (cv) + arithmetic + stage maps (0.42 cv) + embedding bars
      cv = narrow ? Math.min((colW - 40) / 2, (availH / 2 - 70) / 1.3) : Math.min((colW - 40) / 2, (availH - 230) / 1.42);
      cv = Math.max(90, Math.floor(cv));
      cin = cv;
    }
    PLANES.forEach(d => { kin[d].ctx = fitCanvas(kin[d].in, cin, cin); });
    DETS.forEach(d => {
      const k = kd[d];
      k.fmCtx = fitCanvas(k.fm, cv, cv);
      const scales = narrow ? [0.3, 0.24, 0.18, 0.13] : [0.42, 0.33, 0.25, 0.18];
      const sc = i => scales[i] ?? 0.13;
      k.stageCtx = k.stageCvs.map((c, i) => fitCanvas(c, Math.round(cv * sc(i)), Math.round(cv * sc(i))));
      k.stageCvs.forEach((c, i) => k.stageCtx[i].drawImage(k.stageOff[i], 0, 0, cv * sc(i), cv * sc(i)));
      k.zCtx = fitCanvas(k.zbar, k.zbar.parentElement.clientWidth, narrow ? 30 : 52);
    });
  }

  function drawKernel(p) {
    const tScan = clamp(p / SCAN_END), pos = Math.min(G * G - 1, Math.floor(tScan * G * G)), done = tScan >= 1;
    const gy = Math.floor(pos / G), gx = pos % G, src = K.display / G;
    const accent = css("--accent");
    // inputs + kernel box, and the real pixels under the kernel in each plane
    PLANES.forEach((d, i) => {
      const k = kin[d], col = css("--" + d), cell = cin / G, ctx = k.ctx;
      ctx.drawImage(kOff[d].input, 0, 0, cin, cin);
      if (!done) {
        const x = (gx - KH) * cell, y = (gy - KH) * cell;
        ctx.fillStyle = col + "33";
        ctx.fillRect(x, y, KS * cell, KS * cell);
        ctx.strokeStyle = col; ctx.lineWidth = 1;
        for (let j = 1; j < KS; j++) {
          ctx.beginPath(); ctx.moveTo(x + j * cell, y); ctx.lineTo(x + j * cell, y + KS * cell); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(x, y + j * cell); ctx.lineTo(x + KS * cell, y + j * cell); ctx.stroke();
        }
        ctx.lineWidth = 2; ctx.strokeRect(x, y, KS * cell, KS * cell);
      }
      const s = sampleOf(pos, d, i), rng = kAll[d];
      k.px.forEach((e, j) => {
        const g = Math.round(255 * clamp((s[j] - rng.lo) / (rng.hi - rng.lo || 1)));
        e.style.background = `rgb(${g},${g},${g})`;
        e.title = `pixel ${s[j]}`;
      });
    });
    // feature map painted up to the kernel's position, the real output, deeper stages, embedding
    DETS.forEach(d => {
      const k = kd[d], col = css(FUSION ? "--accent" : "--" + d), cell = cv / G;
      k.fmCtx.clearRect(0, 0, cv, cv);
      k.fmCtx.fillStyle = css("--line");
      k.fmCtx.fillRect(0, 0, cv, cv);
      if (done) k.fmCtx.drawImage(kOff[d].fmap, 0, 0, cv, cv);
      else {
        if (gy > 0) k.fmCtx.drawImage(kOff[d].fmap, 0, 0, K.display, gy * src, 0, 0, cv, gy * cell);
        k.fmCtx.drawImage(kOff[d].fmap, 0, gy * src, (gx + 1) * src, src, 0, gy * cell, (gx + 1) * cell, cell);
        k.fmCtx.strokeStyle = accent; k.fmCtx.lineWidth = 2;
        k.fmCtx.strokeRect(gx * cell, gy * cell, cell, cell);
      }
      const val = outOf(pos, d), [lo, hi] = fmapRange(d);
      k.out.textContent = val.toFixed(3);
      k.out.style.boxShadow = `inset 4px 0 0 ${lutCss((val - lo) / (hi - lo || 1))}`;
      $(".stages", k.root).classList.toggle("on", p > 0.45);
      k.stageFigs.forEach((f, i) => f.classList.toggle("on", p > 0.5 + i * 0.065));
      const zt = smooth((p - 0.78) / 0.14);
      k.zbar.classList.toggle("on", p > 0.74);
      k.zlab.classList.toggle("on", p > 0.74);
      drawZ(k, C.z[d], col, zt);
    });
  }
  function drawZ(k, z, col, t) {
    const ctx = k.zCtx, W = k.zbar.clientWidth, H = k.zbar.clientHeight, mid = H / 2;
    const m = Math.max(...z.map(Math.abs)) || 1, bw = W / z.length;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = css("--line");
    ctx.fillRect(0, mid - 0.5, W, 1);
    ctx.fillStyle = col;
    z.forEach((v, i) => {
      const h = v / m * (mid - 2) * t;
      ctx.fillRect(i * bw + 0.5, h > 0 ? mid - h : mid, Math.max(1, bw - 1), Math.abs(h));
    });
  }

  const planeNorms = FUSION && K.plane_norm ? PLANES.map(d => `${DET_LABEL[d]} ${K.plane_norm[d].toFixed(2)}`).join(" · ") : "";
  const deeperStep = { k: "Deeper layers", h: "Zooming out, stage by stage",
    p: `Each stage halves the resolution and applies more kernels to the previous maps, so one pixel summarises an ever larger area. By stage ${last.stage} a pixel sees more than 400 px of the tile: the 1–10 µm particle scale. One channel of each stage is shown.`,
    stat: `stage ${last.stage}: ${last.channels} channels at ${last.res} × ${last.res}` };
  register("kernel", {
    starts: [0, 0.47, 0.74],
    steps: FUSION ? [
      { k: "Convolution", h: "One kernel reads three detectors at once",
        p: `The BSE, Inlens and SE images of the tile go in together as one 3-plane image. At each position the kernel multiplies the ${KK} pixels under it in <em>each</em> plane by that plane's ${KK} learned weights and adds all ${PLANES.length * KK} products up: one pixel of the feature map. So every layer-1 kernel sees all three detectors; there are no per-detector passes any more.`,
        stat: `size of this kernel's weights per plane: ${planeNorms} · the real kernel covers ${KS} × ${KS} px of each ${P.tiles.size} × ${P.tiles.size} px plane and moves 1 px at a time` },
      deeperStep,
      { k: "Vector z", h: `The tile becomes ${C.z.fused.length} numbers`,
        p: `The last maps are averaged over the tile (mean and spread: ${C.feat_dim} numbers), then projected to a ${C.z.fused.length}-number vector <b>z</b> of length 1: one z for the whole tile, not one per detector. Training pulls the z of tiles from the same batch (but a different spot) together and pushes the other batches away; the next section shows exactly what that asks for. A light material-map term keeps the encoder looking at the structure.`,
        stat: run.loss ? `loss: ${run.loss}` : `early fusion · ${run.arch}` },
    ] : [
      { k: "Convolution", h: "A kernel paints a feature map",
        p: `At each position the kernel multiplies the ${KK} pixels under it by its ${KK} learned weights and adds them up: one pixel of the feature map. The encoder is shared, so the <em>same</em> weights scan both detectors; only a per-detector gain and offset (the adapter) differ.`,
        stat: `drawn enlarged: the real kernel covers ${KS} × ${KS} of the tile's ${P.tiles.size} × ${P.tiles.size} px and moves 1 px at a time` },
      deeperStep,
      { k: "Vector z", h: `Each detector becomes ${C.z.bse.length} numbers`,
        p: `The last maps are averaged over the tile (mean and spread: ${C.feat_dim} numbers), then projected to a ${C.z.bse.length}-number vector <b>z</b> of length 1. One z for BSE, one for Inlens; the bars show them.`,
        stat: `cosine similarity of these two z: ${C.z_cos.toFixed(3)}` },
    ],
    update: p => drawKernel(p),
    layout: layoutKernel,
  });

  // ==========================================================================================================
  // 03a / 03b  the two contrastive losses: V1 (label-free: BSE z vs Inlens z of the same tile) and V2 (batch-supervised)
  // ==========================================================================================================
  let matchSec = null, matrixThumb = null, match1Sec = null, matrix1Thumb = null;
  function digits(lo, hi) { return Math.max(2, Math.min(5, Math.ceil(-Math.log10(Math.max(hi - lo, 1e-6))) + 1)); }
  const thumbOf = Sm => () => {
    const c = document.createElement("canvas"), ctx = c.getContext("2d"), flat = Sm.flat(), N = Sm.length;
    const lo = Math.min(...flat), hi = Math.max(...flat), s = 8;
    c.width = c.height = N * s;
    Sm.forEach((row, i) => row.forEach((v, j) => { ctx.fillStyle = lutCss((v - lo) / (hi - lo || 1)); ctx.fillRect(j * s, i * s, s, s); }));
    return c.toDataURL();
  };
  const scaleBar = card => {
    const sc = $(".scale canvas", card), sw = sc.clientWidth, sctx = sc.getContext("2d");
    sc.width = sw; sc.height = 10;
    for (let i = 0; i < sw; i++) { sctx.fillStyle = lutCss(i / sw); sctx.fillRect(i, 0, 1.5, 10); }
  };
  const wireToggle = (root, sec, onChange) => $$(".toggle button", root).forEach(b => b.addEventListener("click", () => {
    $$(".toggle button", root).forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    onChange(b.dataset.net);
    if (sec.layout) sec.layout();                        // the note's length can change the matrix size
    sec.update(sec.p ?? 1, sec.step < 0 ? 0 : sec.step);
  }));

  // ---- V1: the label-free cross-detector loss. M = build.py's matrix (BSE z x Inlens z over a few tiles) --------
  function v1MatchSection(id, M, runInfo, zCos, standalone) {
    const root = $("#" + id), card = $(`#${id}-card`), q = s => $(s, root), qc = s => $(s, card);
    const N = M.tiles.length;
    let net = "trained";
    const thumbs = M.tiles.map(t => ({ bse: gridCanvas(t.thumb.bse, M.thumb_size, false), inlens: gridCanvas(t.thumb.inlens, M.thumb_size, false) }));
    const nHeld = M.tiles.filter(t => t.role === "held-out").length;
    qc(".match-key").innerHTML =
      `<span><i class="dot" style="background:var(--accent)"></i>tile from a spot the model never trained on</span>` +
      `<span class="k2"><i class="dot" style="background:var(--good)"></i>row's best match is the true partner</span>` +
      `<span class="k2"><i class="dot" style="background:var(--bad)"></i>row's best match is another tile</span>`;
    function softmaxDiag(S, i) {
      const row = S[i].map(v => v / M.temperature), mx = Math.max(...row);
      const e = row.map(v => Math.exp(v - mx));
      return e[i] / e.reduce((a, b) => a + b, 0);
    }
    let mx = 460, mctx;
    function updateNote() {
      const data = M[net], flat = data.sim.flat(), lo = Math.min(...flat), hi = Math.max(...flat), dg = digits(lo, hi);
      const what = net === "trained"
        ? `Run “${runInfo.name}”: ${runInfo.arch} encoder, ${runInfo.epoch} epoch${runInfo.epoch === 1 ? "" : "s"} on ${runInfo.n_train_tiles ?? "the"} tiles from ${runInfo.train_spots.length} spots, no batch labels.`
        : "Same network with random weights, before any training.";
      const collapsed = hi - lo < 0.02
        ? ` Every pair scores between ${lo.toFixed(dg)} and ${hi.toFixed(dg)}: all the vectors point in almost the same direction, so the colour scale is stretched to that narrow range.`
        : "";
      q(".match-note").textContent = what + collapsed;
    }
    function layoutMatrix() {
      const wrap = q(".matrix-wrap");
      const used = q(".mx-head").offsetHeight + q(".match-note").offsetHeight + 16;
      mx = Math.max(200, Math.floor(Math.min(wrap.clientHeight - used, wrap.clientWidth, 640)));
      mctx = fitCanvas(q("canvas.matrix"), mx, mx);
      scaleBar(card);
    }
    function drawMatrix(p, step) {
      const data = M[net], Sm = data.sim, flat = Sm.flat();
      const lo = Math.min(...flat), hi = Math.max(...flat), dg = digits(lo, hi);
      const ctx = mctx, lab = 20, th = Math.max(18, Math.min(52, mx * 0.09)), pad = lab + th + 6;
      const cell = (mx - pad) / N, ink = css("--ink"), muted = css("--muted"), accent = css("--accent");
      ctx.clearRect(0, 0, mx, mx);
      ctx.fillStyle = muted; ctx.font = "600 11px system-ui, sans-serif"; ctx.textAlign = "center";
      ctx.fillText("Inlens tile →", pad + (mx - pad) / 2, 10);
      ctx.save(); ctx.translate(11, pad + (mx - pad) / 2); ctx.rotate(-Math.PI / 2); ctx.fillText("← BSE tile", 0, 0); ctx.restore();
      for (let i = 0; i < N; i++) {
        const o = pad + i * cell + (cell - Math.min(th, cell - 4)) / 2, ts = Math.min(th, cell - 4);
        ctx.drawImage(thumbs[i].inlens, o, lab, ts, ts);
        ctx.drawImage(thumbs[i].bse, lab, o, ts, ts);
        if (M.tiles[i].role === "held-out") {
          ctx.fillStyle = accent;
          ctx.beginPath(); ctx.arc(o + ts - 4, lab + 4, 3, 0, 7); ctx.fill();
          ctx.beginPath(); ctx.arc(lab + ts - 4, o + 4, 3, 0, 7); ctx.fill();
        }
      }
      const shown = step === 0 ? 1 : step === 1 ? Math.max(1, Math.ceil(smooth((p - 0.33) / 0.26) * N * N)) : N * N;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.font = `${Math.max(9, Math.min(12, cell / 5))}px system-ui, sans-serif`;
      for (let k = 0; k < N * N; k++) {
        const i = Math.floor(k / N), j = k % N, x = pad + j * cell, y = pad + i * cell;
        if (k >= shown) { ctx.strokeStyle = css("--line"); ctx.lineWidth = 1; ctx.strokeRect(x + 1, y + 1, cell - 2, cell - 2); continue; }
        const v = (Sm[i][j] - lo) / (hi - lo || 1);
        ctx.fillStyle = lutCss(v);
        ctx.fillRect(x + 1, y + 1, cell - 2, cell - 2);
        if (cell > 44) { ctx.fillStyle = v > 0.6 ? "#111" : "#fff"; ctx.fillText(Sm[i][j].toFixed(dg), x + cell / 2, y + cell / 2); }
      }
      if (step === 0) { ctx.strokeStyle = ink; ctx.lineWidth = 2.5; ctx.strokeRect(pad + 1, pad + 1, cell - 2, cell - 2); }
      if (step === 2) {
        ctx.strokeStyle = ink; ctx.lineWidth = 2;
        for (let i = 0; i < N; i++) ctx.strokeRect(pad + i * cell + 1.5, pad + i * cell + 1.5, cell - 3, cell - 3);
        for (let i = 0; i < N; i++) {
          const j = Sm[i].indexOf(Math.max(...Sm[i]));
          ctx.fillStyle = css(j === i ? "--good" : "--bad"); ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(pad + j * cell + cell - 8, pad + i * cell + 8, 4.5, 0, 7); ctx.fill(); ctx.stroke();
        }
      }
      qc(".match-key").dataset.step = step;
      const diag = Sm.map((r, i) => r[i]), off = flat.filter((_, k) => k % N !== Math.floor(k / N));
      const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
      const hits = Math.round(data.retrieval * N);
      qc(".match-stats").innerHTML =
        `<dt>Best match = true partner</dt><dd>${hits} / ${N} rows <small style="font-weight:400;color:var(--muted)">(chance 1/${N})</small></dd>` +
        `<dt>Mean similarity, same tile</dt><dd>${mean(diag).toFixed(dg)}</dd>` +
        `<dt>Mean similarity, different tiles</dt><dd>${mean(off).toFixed(dg)}</dd>` +
        `<dt>Loss's pick for tile ${tileName}</dt><dd>${pct(softmaxDiag(Sm, 0))} <small style="font-weight:400;color:var(--muted)">(chance ${pct(1 / N)})</small></dd>`;
      qc(".scale-labels").innerHTML = `<span>${lo.toFixed(dg)}</span><span>colour = cosine similarity</span><span>${hi.toFixed(dg)}</span>`;
    }
    const sec = register(id, {
      starts: [0, 0.33, 0.66],
      steps: [
        { k: "One pair", h: "Compare the two vectors",
          p: standalone
            ? `Tile ${tileName}'s BSE vector and its Inlens vector from step 02 give one number: their cosine similarity (1 = pointing the same way). That's the top-left cell.`
            : `V1 is the earlier model: one encoder pass per detector, so tile ${tileName} gets a BSE vector and an Inlens vector. Their cosine similarity (1 = pointing the same way) is one number: the top-left cell. No batch label is involved anywhere in V1.`,
          stat: `BSE vs Inlens, same tile: ${zCos.toFixed(4)}` },
        { k: "Every pair", h: `${N} BSE tiles × ${N} Inlens tiles`,
          p: `Doing the same for ${N} tiles from ${new Set(M.tiles.map(t => t.sample_id)).size} spots fills a matrix. Rows are BSE tiles, columns Inlens tiles; the diagonal holds the true pairs (same tile, different detector).`,
          stat: `${nHeld} of ${N} tiles come from spots the model never trained on` },
        { k: "The loss", h: "Training wants the diagonal to win",
          p: `For each row the contrastive loss (NT-Xent, temperature ${M.temperature}) rewards the diagonal cell for beating every other cell in its row. A dot marks each row's best match (key below).${standalone ? "" : " The network only has to describe the material so that the two detectors' descriptions of the same tile agree; whatever that tells it about batches is a by-product, and section 04 shows how much that by-product is worth."}`,
          stat: "retrieval = share of rows whose best match is the true partner" },
      ],
      update: drawMatrix,
      layout: layoutMatrix,
    });
    wireToggle(root, sec, n => { net = n; updateNote(); });
    updateNote();
    return { sec, thumb: thumbOf(M.trained.sim) };
  }

  // ---- V2: the batch-contrastive loss on real tiles. CT = build.py's contrast block --------------------------------
  function v2ContrastSection(id, CT) {
    const root = $("#" + id), card = $(`#${id}-card`), q = s => $(s, root), qc = s => $(s, card);
    const N = CT.tiles.length, REL = CT.relation;
    let net = "trained";
    const thumbs = CT.tiles.map(t => gridCanvas(t.thumb, CT.thumb_size, false));
    const bnum = t => +t.batch.slice(-1);
    const nSpots = new Set(CT.tiles.map(t => t.sample_id)).size, nBatches = new Set(CT.tiles.map(t => t.batch)).size;
    const count = (i, rel) => REL[i].filter(x => x === rel).length;
    const nPos0 = count(0, "pos"), nSpot0 = count(0, "spot"), nNeg0 = count(0, "neg");
    const mean = a => a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0;
    const rowMean = (S, i, rel) => mean(S[i].filter((_, j) => REL[i][j] === rel));
    q(".mx-cap").innerHTML = `cosine similarity of <b>z</b> · ${N} tiles from ${nSpots} spots of ${nBatches} batches · rows and columns in the same order, grouped by batch`;
    qc(".match-key").innerHTML =
      `<span><i class="sw" style="background:var(--c1)"></i>Batch_1 &nbsp; <i class="sw" style="background:var(--c2)"></i>Batch_2 &nbsp; <i class="sw" style="background:var(--c3)"></i>Batch_3 &nbsp; <b class="kbox spot"></b> hatched = same spot, ignored by the loss</span>` +
      `<span><b class="kbox pos"></b>same batch, other spot: pulled together &nbsp; <b class="kbox neg"></b> other batch: pushed apart</span>` +
      `<span class="k2"><i class="dot" style="background:var(--good)"></i>row's best match is a positive &nbsp; <i class="dot" style="background:var(--bad)"></i>it is not</span>`;
    let mx = 460, mctx;
    const BW = 58;                                                 // right margin: the per-row share bars (step 3)
    function updateNote() {
      const d = CT[net], flat = d.sim.flat(), lo = Math.min(...flat), hi = Math.max(...flat), dg = digits(lo, hi);
      const what = net === "trained"
        ? `Run “${run.name}”: ${run.arch} encoder, ${run.epoch} epoch${run.epoch === 1 ? "" : "s"} on ${run.train_spots.length} spots${run.w_ce ? `, with a batch classifier head (weight ${run.w_ce})` : ""}${run.w_seg ? ` and a material-map term (weight ${run.w_seg})` : ""}.`
        : "Same network with random weights, before any training.";
      const collapsed = hi - lo < 0.02
        ? ` Every pair scores between ${lo.toFixed(dg)} and ${hi.toFixed(dg)}: the vectors all point almost the same way, so the colour scale is stretched to that narrow range.${net === "trained" ? " A full training run should spread them apart." : ""}`
        : "";
      q(".match-note").textContent = what + collapsed;
    }
    function layoutMatrix() {
      const wrap = q(".matrix-wrap");
      const used = q(".mx-head").offsetHeight + q(".match-note").offsetHeight + 16;
      mx = Math.max(220, Math.floor(Math.min(wrap.clientHeight - used, wrap.clientWidth - BW, 640)));
      mctx = fitCanvas(q("canvas.matrix"), mx + BW, mx);
      scaleBar(card);
    }
    function drawContrast(p, step) {
      const d = CT[net], Sm = d.sim, flat = Sm.flat(), lo = Math.min(...flat), hi = Math.max(...flat), dg = digits(lo, hi);
      const ctx = mctx, lab = 4, th = Math.max(14, Math.min(40, mx * 0.075)), pad = lab + th + 8;
      const cell = (mx - pad) / N, ink = css("--ink"), muted = css("--muted"), line = css("--line");
      ctx.clearRect(0, 0, mx + BW, mx);
      for (let i = 0; i < N; i++) {                                 // thumbnails (BSE) with a batch-coloured strip
        const ts = Math.min(th, cell - 3), o = pad + i * cell + (cell - ts) / 2, col = css(`--c${bnum(CT.tiles[i])}`);
        ctx.drawImage(thumbs[i], o, lab, ts, ts); ctx.fillStyle = col; ctx.fillRect(o, lab + ts + 1, ts, 3);
        ctx.drawImage(thumbs[i], lab, o, ts, ts); ctx.fillRect(lab + ts + 1, o, 3, ts);
      }
      const shown = step === 1 ? Math.max(N, Math.ceil(smooth((p - 0.33) / 0.26) * N * N)) : N * N;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.font = `${Math.max(9, Math.min(12, cell / 4))}px system-ui, sans-serif`;
      for (let k = 0; k < N * N; k++) {
        const i = Math.floor(k / N), j = k % N, x = pad + j * cell, y = pad + i * cell, rel = REL[i][j];
        const visible = step === 0 ? i === 0 : k < shown;
        if (!visible) { ctx.strokeStyle = line; ctx.lineWidth = 1; ctx.strokeRect(x + 1, y + 1, cell - 2, cell - 2); continue; }
        const v = (Sm[i][j] - lo) / (hi - lo || 1);
        ctx.fillStyle = rel === "self" ? css("--surface") : lutCss(v);
        ctx.fillRect(x + 1, y + 1, cell - 2, cell - 2);
        if (rel === "spot") {                                       // hatched: the loss ignores same-spot pairs
          ctx.save(); ctx.beginPath(); ctx.rect(x + 1, y + 1, cell - 2, cell - 2); ctx.clip();
          ctx.strokeStyle = "rgba(128,128,128,.8)"; ctx.lineWidth = 1.5;
          for (let t = -cell; t < cell * 2; t += 6) { ctx.beginPath(); ctx.moveTo(x + t, y); ctx.lineTo(x + t + cell, y + cell); ctx.stroke(); }
          ctx.restore();
        }
        if (cell > 30 && rel !== "self") { ctx.fillStyle = v > 0.6 ? "#111" : "#fff"; ctx.fillText(Sm[i][j].toFixed(dg), x + cell / 2, y + cell / 2); }
      }
      let start = 0;                                                // the batch blocks on the diagonal
      for (let i = 1; i <= N; i++) {
        if (i < N && bnum(CT.tiles[i]) === bnum(CT.tiles[start])) continue;
        const x = pad + start * cell, w = (i - start) * cell;
        ctx.strokeStyle = css(`--c${bnum(CT.tiles[start])}`); ctx.lineWidth = step === 0 ? 1.5 : 3;
        ctx.globalAlpha = step === 0 ? 0.6 : 1; ctx.strokeRect(x + 1, x + 1, w - 2, w - 2); ctx.globalAlpha = 1;
        start = i;
      }
      if (step === 0) {                                             // the anchor tile's row: outline its positives
        const col = css(`--c${bnum(CT.tiles[0])}`);
        ctx.strokeStyle = ink; ctx.lineWidth = 2.5; ctx.strokeRect(pad + 1, pad + 1, cell - 2, cell - 2);
        for (let j = 1; j < N; j++) if (REL[0][j] === "pos") { ctx.strokeStyle = col; ctx.lineWidth = 3; ctx.strokeRect(pad + j * cell + 2, pad + 2, cell - 4, cell - 4); }
        ctx.fillStyle = muted; ctx.font = "600 11px system-ui, sans-serif"; ctx.textAlign = "left";
        ctx.fillText(`← tile ${tileName} against every other tile`, pad + 4, pad + cell + 12);
      }
      if (step === 2) {                                             // best match per row, and the loss's share on positives
        for (let i = 0; i < N; i++) {
          let best = -1, bv = -Infinity;
          Sm[i].forEach((v, j) => { if (j !== i && v > bv) { bv = v; best = j; } });
          ctx.fillStyle = css(REL[i][best] === "pos" ? "--good" : "--bad"); ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(pad + best * cell + cell - 7, pad + i * cell + 7, 4.5, 0, 7); ctx.fill(); ctx.stroke();
          const y = pad + i * cell, bx = mx + 8, bw = BW - 14;
          ctx.fillStyle = line; ctx.fillRect(bx, y + cell * 0.3, bw, cell * 0.4);
          ctx.fillStyle = css("--accent"); ctx.fillRect(bx, y + cell * 0.3, bw * d.pos_share[i], cell * 0.4);
          ctx.fillStyle = ink; ctx.fillRect(bx + bw * CT.chance_share[i] - 0.75, y + cell * 0.18, 1.5, cell * 0.64);
        }
        ctx.fillStyle = muted; ctx.font = "600 10px system-ui, sans-serif"; ctx.textAlign = "left";
        ctx.fillText("share on", mx + 8, pad - 16); ctx.fillText("positives", mx + 8, pad - 5);
      }
      qc(".match-key").dataset.step = step;
      const same = rowMean(Sm, 0, "pos"), other = rowMean(Sm, 0, "neg"), own = rowMean(Sm, 0, "spot");
      const sm = t => `<small style="font-weight:400;color:var(--muted)">${t}</small>`;
      qc(".match-stats").innerHTML = step === 0
        ? `<dt>Tile ${tileName} vs same batch, other spots</dt><dd>${same.toFixed(dg)} ${sm(`${nPos0} tiles`)}</dd>` +
          `<dt>vs the other batches</dt><dd>${other.toFixed(dg)} ${sm(`${nNeg0} tiles`)}</dd>` +
          `<dt>vs its own spot (ignored)</dt><dd>${own.toFixed(dg)} ${sm(`${nSpot0} tile${nSpot0 === 1 ? "" : "s"}`)}</dd>` +
          `<dt>Row's softmax share on positives</dt><dd>${pct(d.pos_share[0])} ${sm(`chance ${pct(CT.chance_share[0])}`)}</dd>`
        : `<dt>Mean similarity, same batch, other spot</dt><dd>${d.within.toFixed(dg)}</dd>` +
          `<dt>Mean similarity, other batch</dt><dd>${d.across.toFixed(dg)}</dd>` +
          `<dt>Rows whose best match is a positive</dt><dd>${Math.round(d.best_is_pos * N)} / ${N} ${sm(`chance ${pct(mean(CT.chance_share))}`)}</dd>` +
          `<dt>Mean share on positives · loss</dt><dd>${pct(mean(d.pos_share))} · ${d.loss.toFixed(2)}</dd>`;
      qc(".scale-labels").innerHTML = `<span>${lo.toFixed(dg)}</span><span>colour = cosine similarity</span><span>${hi.toFixed(dg)}</span>`;
    }
    const gain = (a, b) => (b - a >= 0 ? "+" : "") + (b - a).toFixed(3);
    const sec = register(id, {
      starts: [0, 0.33, 0.66],
      steps: [
        { k: "One tile", h: "What the loss asks of one tile",
          p: `V2 reads the three detectors as one image (section 02) and is told the batch. Take tile ${tileName}'s z and compare it with ${N - 1} other tiles. The loss sorts them into three kinds. Tiles of the <b>same batch from another spot</b> are positives: it wants these similarities high. Tiles of <b>another batch</b> are negatives: it wants these low. Tiles of the <b>same spot</b> are left out: they look alike anyway, and counting them would teach the network to recognise the spot rather than the batch.`,
          stat: `${nPos0} positives · ${nNeg0} negatives · ${nSpot0} ignored (same spot)` },
        { k: "Every tile", h: `${N} tiles, ${nSpots} spots, ${nBatches} batches`,
          p: `The same for every tile. Rows and columns are grouped by batch, so the loss is asking for bright blocks on the diagonal (same batch) and darker cells everywhere else. Toggle <b>Before training</b>: with random weights every pair scores about the same, there is nothing yet that separates the batches. During training every mini-batch holds ${run.batch_spots ?? "several"} spots of each batch, ${run.tiles_per_spot ?? "a few"} tiles each, so every tile has positives to be pulled towards.`,
          stat: `same batch, other spot ${CT.trained.within.toFixed(3)} (${gain(CT.untrained.within, CT.trained.within)} with training) · other batch ${CT.trained.across.toFixed(3)} (${gain(CT.untrained.across, CT.trained.across)})` },
        { k: "The loss", h: "Supervised contrastive: the positives must win the row",
          p: `For each row the loss (Khosla et al. 2020, temperature ${CT.temperature}) turns the similarities into a softmax over the other tiles and asks the positives to take as much of it as possible. The bars on the right are that share; the tick is chance. Nothing here says what the batches <em>are</em>: the network has to find whatever repeats across the spots of a batch and differs between batches, which is exactly the property a black-box batch label hides. Section 07 then reads that embedding through the named features.${run.w_ce ? " A plain batch classifier head is trained alongside." : ""}${run.w_seg ? " A light material-map term keeps the encoder on the structure." : ""}${run.w_adv ? ` A session-adversarial head (weight ${run.w_adv}) punishes any embedding from which the imaging session can be read, so the batch signal cannot hide in the microscope settings.` : ""}`,
          stat: `mean share on positives ${pct(mean(CT.trained.pos_share))} after training · ${pct(mean(CT.untrained.pos_share))} before · chance ${pct(mean(CT.chance_share))}` },
      ],
      update: drawContrast,
      layout: layoutMatrix,
    });
    wireToggle(root, sec, n => { net = n; updateNote(); });
    updateNote();
    return { sec, thumb: thumbOf(CT.trained.sim) };
  }

  if (!FUSION) {                                                    // a page built against the old model: V1 only
    $("#match1").remove();
    $("#match .sec-num").textContent = "03";
    $("#match .match-h2").textContent = "Do the two embeddings match?";
    $("#match .match-sub").innerHTML = "the contrastive loss wants each BSE tile to be most similar to the Inlens image of the <em>same</em> tile";
    ({ sec: matchSec, thumb: matrixThumb } = v1MatchSection("match", C.matrix, run, C.z_cos, true));
  } else {
    if (C.v1 && C.v1.matrix) ({ sec: match1Sec, thumb: matrix1Thumb } = v1MatchSection("match1", C.v1.matrix, C.v1.run, C.v1.z_cos, false));
    else $("#match1").remove();
    if (C.contrast) ({ sec: matchSec, thumb: matrixThumb } = v2ContrastSection("match", C.contrast));
    else $("#match").remove();
    if (!match1Sec && matchSec) $("#match .sec-num").textContent = "03";
  }

  // ==========================================================================================================
  // 04-07  results: batch test, verdict, battery sliders, why  (present when build.py found the result files)
  // ==========================================================================================================
  const R = D.results;
  const FL = R ? R.feature_labels : {};
  const flab = f => FL[f] || f;
  const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(+v)) ? "–" : (+v).toFixed(d);
  const sgn = (v, d = 2) => (v > 0 ? "+" : "") + fmt(v, d);
  const bcol = b => `var(--c${b})`;
  const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const layerToggler = id => {
    const stage = $("#" + id);
    return step => { stage.dataset.step = step; $$(".layer", stage).forEach(l => l.classList.toggle("on", l.dataset.show.split(" ").includes(String(step)))); };
  };
  const thumbCanvas = draw => { const c = document.createElement("canvas"); c.width = 128; c.height = 72; draw(c.getContext("2d")); return c.toDataURL(); };
  const extraNodes = [], extraThumbs = [];
  if (!R) ["batch", "verdict", "sliders", "why"].forEach(id => { $("#" + id).style.display = "none"; });

  if (R) {
    // ---- 04 batch test: V2 (nested), V1 and the baselines on one axis; V2 confusion; test spots -----------------
    const PR = R.predict, ME = R.run_label || R.run;
    const BL = R.baselines, NT = R.novelty;
    const V2 = R.v2 && R.v2.score ? R.v2.score : null;                       // cnn/supcon.py score -> score.json
    const V1P = (R.v1 && R.v1.predict) || (R.is_v2 ? null : PR);             // the old model's predictions.json
    const V1B = BL ? BL.rows.find(r => r.name.startsWith("V1")) : null;      // the old model as a baselines row
    const V1 = V1B ? { bacc: V1B.lr_losess, ci90: V1B.ci90, perm_p: V1B.perm_p, mixed: V1B.lr_mixed, recall: V1B.recall, uses: V1B.uses, src: "baselines table (last.pt)" }
      : V1P ? { bacc: V1P.losess_bacc, ci90: null, perm_p: V1P.scores.lr_losess_perm_p, mixed: V1P.scores.lr_mixed, recall: null, uses: "the old model's predictions.json", src: "predictions.json" } : null;
    const ACQ = BL ? BL.rows.find(r => r.name === "imaging cues only") : null;
    const NTILES = R.n_tiles_per_spot || P.tiles.grid.length;
    const whisk = ci => ci ? `<em class="ci" style="left:${(100 * ci.lo).toFixed(1)}%;width:${(100 * (ci.hi - ci.lo)).toFixed(1)}%"></em>` : "";
    const ticks = () => `<em class="chance" style="left:33.3%" title="chance 0.33"></em>${ACQ ? `<em class="acq" style="left:${(100 * ACQ.lr_losess).toFixed(1)}%" title="imaging cues only"></em>` : ""}`;
    const bar = (v, ci) => `<span class="bt"><i style="--w:${(100 * v).toFixed(1)}%"></i>${ticks()}${whisk(ci)}</span>`;
    const rec = rows => rows ? rows.map(q => `B${q.batch} ${fmt(q.recall)} [${fmt(q.lo)}, ${fmt(q.hi)}]`).join(" · ") : "";
    const ciTxt = ci => ci ? `[${fmt(ci.lo)}, ${fmt(ci.hi)}]` : "";
    const nullRow = BL ? BL.rows.find(r => r.null) : null;
    const v2Row = V2
      ? `<div class="brow me"><span class="bl">V2<small>batch-supervised, early fusion · ${V2.n_folds} retrained encoders, each scored only on the ${/spot/.test(V2.note || "") ? "spots" : "session"} it never saw</small></span>${bar(V2.losess_bacc, V2.ci90)}` +
        `<span class="bv num">${fmt(V2.losess_bacc)} <small>${ciTxt(V2.ci90)} · no permutation p · mixed ${fmt(V2.mixed_bacc)}<br>${rec(V2.recall)}</small></span></div>`
      : `<div class="brow me"><span class="bl">V2<small>batch-supervised, early fusion</small></span><span class="bt"></span><span class="bv num"><small>not run yet: python cnn/supcon.py score --name v2</small></span></div>`;
    const v1Row = V1
      ? `<div class="brow ref"><span class="bl">V1<small>label-free, old model · ${esc(V1.uses)}</small></span>${bar(V1.bacc, V1.ci90)}` +
        `<span class="bv num">${fmt(V1.bacc)} <small>${ciTxt(V1.ci90)} · p ${fmt(V1.perm_p, 3)} · mixed ${fmt(V1.mixed)}${V1.recall ? `<br>${rec(V1.recall)}` : ""}</small></span></div>`
      : `<div class="brow ref"><span class="bl">V1<small>label-free, old model</small></span><span class="bt"></span><span class="bv num"><small>no V1 row in baselines.json and no predictions.json</small></span></div>`;
    const blRows = BL ? BL.rows.filter(r => r !== V1B).map(r => `<div class="brow ${r.name === "imaging cues only" ? "acqrow" : ""}"><span class="bl">${esc(r.name)}<small>${esc(r.uses)}</small></span>${bar(r.lr_losess, r.ci90)}` +
      `<span class="bv num">${fmt(r.lr_losess)} <small>${ciTxt(r.ci90)} · p ${fmt(r.perm_p, 3)} · mixed ${fmt(r.lr_mixed)}<br>${rec(r.recall)}` +
      (r.test ? `<br>test: ${r.test.map(t => `${t.sample_id} → B${t.call}`).join(", ")}` : "") + `</small></span></div>`).join("") : `<p class="note">no baselines yet (python cnn/baselines.py)</p>`;
    const nullHtml = nullRow ? `<div class="brow noise"><span class="bl">shuffled labels<small>permutation null of the features model, ${nullRow.null.n} shuffles</small></span>` +
      `<span class="bt"><i style="--w:${(100 * nullRow.null.mean).toFixed(1)}%"></i>${ticks()}<em class="ci" style="left:${(100 * nullRow.null.mean).toFixed(1)}%;width:${(100 * (nullRow.null.q95 - nullRow.null.mean)).toFixed(1)}%"></em></span>` +
      `<span class="bv num">${fmt(nullRow.null.mean)} <small>95th percentile ${fmt(nullRow.null.q95)}</small></span></div>` : "";
    const CP = R.compare, CPM = CP ? CP.models : {};
    const CAT = CPM["V1+2 concatenated"], CV1 = CPM["V1 (label-free)"], CV2 = CPM["V2 (batch-supervised)"];
    if (CP) {
      const short = { "V1 (label-free)": ["V1", "label-free: one encoder serves every fold"], "V2 (batch-supervised)": ["V2", "batch-supervised: retrained per fold"],
                      "V1+2 concatenated": ["V1 + V2 side by side", "both embeddings, each block standardised, weighted equally"],
                      "V1+2 fine-tuned (V1 encoder + batch supervision)": ["V1 fine-tuned with labels", "V1's encoder, then the V2 recipe"] };
      const dlt = m => m.delta_vs_v1 ? ` · vs V1 ${sgn(m.delta_vs_v1.delta)} [${sgn(m.delta_vs_v1.lo)}, ${sgn(m.delta_vs_v1.hi)}], P(better) ${fmt(m.delta_vs_v1.p_gt0)}` : "";
      $("#batch-models").innerHTML = `<h4 class="bars-sub">The two losses on the same test: ${esc(CP.folds)}, one classifier (cnn/compare.py)</h4>` +
        CP.order.map(name => { const m = CPM[name], [lab, sub] = short[name] || [name, ""];
          return `<div class="brow cmp ${name === "V1+2 concatenated" ? "me" : ""}"><span class="bl">${esc(lab)}<small>${esc(sub)}</small></span>${bar(m.bacc, m.ci90)}` +
            `<span class="bv num">${fmt(m.bacc)} <small>${ciTxt(m.ci90)} · mixed ${fmt(m.mixed_bacc)}${dlt(m)}<br>${rec(m.recall)}</small></span></div>`; }).join("") +
        Object.entries(CP.extra || {}).map(([name, m]) =>
          `<div class="brow cmp noise"><span class="bl">${esc(name.replace("concatenated", "side by side").replace(" + ", " + ").replace("V1 ", "V1 "))}<small>another combination tried</small></span>${bar(m.bacc, m.ci90)}` +
          `<span class="bv num">${fmt(m.bacc)} <small>${ciTxt(m.ci90)}${dlt(m)}</small></span></div>`).join("") +
        `<h4 class="bars-sub">Against the baselines, whole imaging sessions held out</h4>`;
    } else {
      $("#batch-models").innerHTML = "";
    }
    $("#batch-models").insertAdjacentHTML("beforeend", v2Row + v1Row + nullHtml + blRows);
    const cmpTxt = CAT ? `<b>Top block:</b> V1, V2 and the two <b>side by side</b> on the very same ${esc(CP.folds)} with one classifier: V1 ${fmt(CV1.bacc)}, V2 ${fmt(CV2.bacc)}, together ${fmt(CAT.bacc)} ${ciTxt(CAT.ci90)}. The two losses learn different things (V1 the material as two detectors agree on it, V2 whatever separates the batches) and their embeddings add up. Best of several combinations tried, so a seed check is queued. ` : "";

    // confusion matrix: V2's nested calls when scored, else the page run's predictions.json
    const PRX = PR || V1P;                                                   // the run's predictions, else V1's
    const CM = V2 ? { conf: V2.confusion, recall: V2.recall, who: "V2, nested leave-one-session-out" }
      : PRX ? { conf: PRX.confusion_losess, recall: PRX.recall_losess.map((v, i) => ({ batch: i + 1, recall: v })), who: `${PR ? ME : "V1, the old model"}, leave one session out (V2 not scored yet)` } : null;
    if (CM) {
      $("#batch-conf").innerHTML = `<p class="note" style="text-align:center">${esc(CM.who)}</p><table class="conf"><thead><tr><th>true ↓ · called →</th>${[1, 2, 3].map(j => `<th style="color:${bcol(j)}">B${j}</th>`).join("")}<th>recall · 95 % Wilson</th></tr></thead><tbody>` +
        [1, 2, 3].map((i, ii) => { const q = CM.recall[ii]; return `<tr><th style="color:${bcol(i)}">Batch_${i}</th>${CM.conf[ii].map((v, jj) => `<td class="${ii === jj ? "diag" : ""}">${v}</td>`).join("")}<td class="num">${fmt(q.recall)}${q.lo !== undefined ? ` <small>[${fmt(q.lo)}, ${fmt(q.hi)}]</small>` : ""}</td></tr>`; }).join("") + "</tbody></table>";
      $("#batch-conf-stats").innerHTML = V2
        ? `<dt>Balanced accuracy, every spot called out of fold</dt><dd>${fmt(V2.losess_bacc)} <small>(chance 0.33)</small></dd>` +
          `<dt>90 % interval, resampling the imaging sessions</dt><dd>${ciTxt(V2.ci90)}</dd>` +
          `<dt>Spots whose session holds more than one batch</dt><dd>${fmt(V2.mixed_bacc)}</dd>` +
          `<dt>Batch_3 vs the rest</dt><dd>${fmt(V2.b3_vs_rest)} <small>(chance 0.50)</small></dd>` +
          `<dt>Spots called</dt><dd>${V2.n_spots_called} <small>by ${V2.n_folds} encoders</small></dd>` +
          (V1 ? `<dt>V1 on the same test</dt><dd>${fmt(V1.bacc)} <small>${ciTxt(V1.ci90)}</small></dd>` : "")
        : `<dt>Balanced accuracy, leave one session out</dt><dd>${fmt(PRX.losess_bacc)} <small>(chance 0.33)</small></dd>` +
          `<dt>Leave one spot out</dt><dd>${fmt(PRX.loso_bacc)}</dd>` +
          `<dt>Batch_3 vs the rest</dt><dd>${fmt(PRX.b3_vs_rest && PRX.b3_vs_rest.bacc)} <small>(chance 0.50)</small></dd>` +
          `<dt>Permutation p of the losess score</dt><dd>${fmt(PRX.scores.lr_losess_perm_p, 3)}</dd>`;
    } else {
      $("#batch-conf").innerHTML = `<p class="note">no calls yet: python cnn/supcon.py score --name v2</p>`;
      $("#batch-conf-stats").innerHTML = "";
    }

    // test spots: V2's call (full model) next to V1's, with the session caveat from V1's predictions.json
    const nov = sid => { const n = NT && NT.test ? (NT.test[sid] || (NT.test.find && NT.test.find(t => t.sample_id === sid))) : null; return n ? (n.flag || n.unlike_training ? "unlike anything in training" : "looks like training") : null; };
    const v1Test = V1P && V1P.test ? V1P.test : [];
    const v2Test = V2 && V2.test ? V2.test : [];
    const testIds = [...new Set([...v2Test.map(t => t.sample_id), ...v1Test.map(t => t.sample_id)])];
    const pbars = p => `<div class="pbars">${p.map((v, i) => `<div class="prow"><span style="color:${bcol(i + 1)}">B${i + 1}</span><span class="bt"><i style="--w:${(100 * v).toFixed(1)}%;background:${bcol(i + 1)}"></i></span><span class="num">${pct(v)}</span></div>`).join("")}</div>`;
    const TC = R.test_calls && R.test_calls.calls, TCO = TC ? Object.keys(TC) : [];         // e.g. V1, V2, V1+V2
    const tcIds = TC ? [...new Set(TCO.flatMap(k => TC[k].map(t => t.sample_id)))] : [];
    const tcOf = (k, id) => TC[k].find(t => t.sample_id === id);
    const tcLabel = k => k === "V1+V2" ? "V1 + V2 side by side" : k;
    $("#batch-test").innerHTML = TC ? tcIds.map(id => {
      const b = v1Test.find(t => t.sample_id === id), calls = TCO.map(k => tcOf(k, id)).filter(Boolean);
      const agree = new Set(calls.map(c => c.call)).size === 1;
      return `<div class="tcard"><h4>${id}${b ? ` <small>image height ${b.session}</small>` : ""}</h4>` +
        TCO.map(k => { const c = tcOf(k, id); if (!c) return ""; return `<p class="who${k === "V1+V2" ? " best" : ""}">${tcLabel(k)}</p>${pbars(c.p)}` +
          `<p class="call">calls <b style="color:${bcol(c.call)}">Batch_${c.call}</b> <small>(${pct(Math.max(...c.p))}) · same call in ${pct(c.call_stability)} of refits</small></p>`; }).join("") +
        `<p class="note">${agree ? "the models agree" : "the models disagree"}${b ? `; its session holds only ${b.session_batches.map(x => x.replace("Batch_", "B")).join(", ")} in training` : ""}${b && calls.some(c => c.call === b.seam_guess) ? "; the image-adjacency clue says B" + b.seam_guess + ", which is about where the crop was cut, not the material" : ""}.</p></div>`;
    }).join("") : testIds.length ? testIds.map(id => {
      const a = v2Test.find(t => t.sample_id === id), b = v1Test.find(t => t.sample_id === id);
      return `<div class="tcard"><h4>${id}${b ? ` <small>image height ${b.session}</small>` : ""}</h4>` +
        (a ? `<p class="who">V2</p>${pbars(a.p)}<p class="call">V2 calls <b style="color:${bcol(a.call)}">Batch_${a.call}</b>${nov(id) ? ` <small>· ${nov(id)}</small>` : ""}</p>`
          : `<p class="note">V2: not run yet</p>`) +
        (b ? `<p class="call">V1 called <b style="color:${bcol(b.call)}">Batch_${b.call}</b> <small>(${pct(Math.max(...b.p))})${a && a.call !== b.call ? " · the two models disagree" : ""}</small></p>` +
          `<p class="note">its session holds only ${b.session_batches.map(x => x.replace("Batch_", "B")).join(", ")} in training${(a ? a.call : b.call) === b.seam_guess ? "; the call agrees with that neighbour, which is also what a session-leaky model would do" : ""}.</p>` : "") +
        `</div>`;
    }).join("") : `<p class="note">no test-spot calls yet</p>`;
    const tcBest = TC && TC["V1+V2"] ? TC["V1+V2"] : null;
    const toggleBatch = layerToggler("batch-stage");
    const leakV2 = V2 && V2.leak_full_model;
    const V2U = V2 && /spot/.test(V2.note || "") ? "group of spots" : "imaging session";    // what each V2 fold hides
    const V2N = V2 ? V2.n_folds : 13;
    register("batch", {
      starts: [0, 0.34, 0.67],
      steps: [
        { k: "Models", h: "V1, V2 and the baselines on one test",
          p: `${cmpTxt}<b>Lower block:</b> each spot's ${NTILES} tile embeddings are averaged and a logistic regression is scored on spots it never saw, with a whole <em>imaging session</em> held out at a time for V1 and the baselines. <b>V1</b> never saw a batch label, so one encoder is a fair test. <b>V2</b> learns from the labels (03b), so ${V2N} encoders are trained from scratch, each with one ${V2U} locked away, and each calls only the spots it never saw. No permutation p for V2: that would need ${V2N} × 200 retrainings. One spot is worth 0.02 to 0.05 of balanced accuracy, so read the whiskers, not the bar.`,
          stat: (V2 ? `V2 ${fmt(V2.losess_bacc)} ${ciTxt(V2.ci90)}${V1 ? ` · V1 ${fmt(V1.bacc)} ${ciTxt(V1.ci90)}` : ""} · imaging cues alone ${ACQ ? fmt(ACQ.lr_losess) : "–"}` : `V2 not scored yet${V1 ? ` · V1 ${fmt(V1.bacc)} ${ciTxt(V1.ci90)}` : ""}`) + (CAT ? ` · V1 + V2 side by side ${fmt(CAT.bacc)} ${ciTxt(CAT.ci90)}` : "") },
        { k: "Right and wrong", h: V2 ? "Where V2 is right and wrong" : "Where the old model is right and wrong",
          p: `Rows are the true batch, columns the call${V2 ? `, every spot called by an encoder that never saw its ${V2U}` : ", each spot called with its whole session held out"}. Batch_3 is the baseline with 17 spots. The recall of each batch comes with a 95 % Wilson interval: with 7 spots per batch it is wide.${V2 && V1 ? ` V1 scored ${fmt(V1.bacc)} on the same spots.` : ""}`,
          stat: CM ? `recall ${rec(CM.recall)}` : "not run yet" },
        { k: "Test spots", h: "Three unlabeled spots, one per batch",
          p: TC
            ? `Each model is refitted on all 31 training spots and gives each test spot three probabilities. The stability figure is how often the same call comes back when one training spot is dropped and the model refitted (31 refits). Polaron said the test set holds one spot per batch, and no single model calls three different batches, so every model has at least one wrong. xrv9xvzb is the most consistent call. Treat all of these as weak until the V2 seed check shows whether V1 + V2 is reliable.${leakV2 ? ` The full V2 model's nearest-neighbour same-session rate is ${pct(leakV2.nn_same_session_rate)} against ${pct(leakV2.nn_chance)} by chance (p ${fmt(leakV2.nn_perm_p, 3)}).` : ""}`
            : `The V2 model trained on all 31 spots gives each test spot three probabilities; V1's call is shown under it. Read the line under each card: every test image was taken in a session that holds one batch only, so agreeing with that neighbour is not proof of a material call.${leakV2 ? ` The full V2 model's nearest-neighbour same-session rate is ${pct(leakV2.nn_same_session_rate)} against ${pct(leakV2.nn_chance)} by chance (p ${fmt(leakV2.nn_perm_p, 3)}).` : ""}`,
          stat: tcBest ? "V1 + V2: " + tcBest.map(t => `${t.sample_id} → B${t.call} (${pct(Math.max(...t.p))}, stable ${pct(t.call_stability)})`).join(" · ")
            : v2Test.length ? v2Test.map(t => `${t.sample_id} → B${t.call} (${pct(Math.max(...t.p))})`).join(" · ") : v1Test.length ? "V1: " + v1Test.map(t => `${t.sample_id} → B${t.call}`).join(" · ") : "–" },
      ],
      update: (p, step) => toggleBatch(step),
    });
    extraNodes.push({ label: "Models", line: "V1, V2 and the baselines on one test", sec: "batch", steps: [0, 1, 2] });
    extraThumbs.push(thumbCanvas(ctx => {
      const vals = [V2 ? V2.losess_bacc : 0, V1 ? V1.bacc : 0, ...(BL ? BL.rows.filter(r => r !== V1B).map(r => r.lr_losess) : [])].slice(0, 8);
      vals.forEach((v, i) => { ctx.fillStyle = i === 0 ? "#3cc7b0" : "#888"; ctx.fillRect(4 + i * 15, 68 - 60 * v, 11, 60 * v); });
    }));

    // ---- 05 verdict ------------------------------------------------------------------------------------------
    const V = R.verdict, LOTS = V.lots, CFG = V.config;
    const KX = v => 50 + 50 * clamp(v / 4, -1, 1);
    const zcls = z => z === "EQUIV" ? "good" : z === "BEYOND" ? "bad" : "mid";
    function kpiRow(f, r) {
      if (!r || r.skip) return `<div class="krow"><span class="kl">${flab(f)}</span><span class="kaxis"><small>${r ? esc(r.skip) : "not computed"}</small></span><span></span></div>`;
      const zc = zcls(r.zone);
      const fq = R.feature_quality && R.feature_quality[f];
      const sub = (r.tier === "tier1" ? (r.can_reject ? "tier 1 · can reject" : "tier 1 · investigate only") : r.tier === "tier2" ? `tier 2 · ${r.n_inside}/${r.n} inside the range` : "diagnostic") +
        (fq ? ` · trust ${fq.trust} (split-half r ${fmt(fq.split_half_r)}, masks agree ${fmt(fq.mask_agreement)})` : "");
      return `<div class="krow ${r.tier}"><span class="kl">${flab(f)}<small>${sub}</small></span>` +
        `<span class="kaxis"><i class="band" style="left:${KX(-1.5)}%;width:${KX(1.5) - KX(-1.5)}%"></i><i class="zero"></i>` +
        `<i class="ci ${zc}" style="left:${KX(r.ci_lo_sd)}%;width:${Math.max(0.6, KX(r.ci_hi_sd) - KX(r.ci_lo_sd))}%"></i><b class="dot ${zc}" style="left:${KX(r.delta_sd)}%"></b></span>` +
        `<span class="kv num"><b class="${zc}">${r.zone}</b> ${sgn(r.delta_sd, 1)} SD</span></div>`;
    }
    const badge = v => `<b class="badge ${v.replace(/ /g, "-").toLowerCase()}">${v}</b>`;
    const lotTitle = l => l.startsWith("Test/") ? `test spot ${l.slice(5)}` : l;
    function lotPanel(l, full) {
      const lot = LOTS[l], feats = full ? [...CFG.tier1, ...CFG.tier2, ...CFG.diagnostics] : [...CFG.tier1, ...CFG.tier2];
      return `<div class="lotp"><h4>${lotTitle(l)} <small>${lot.n_sites} site${lot.n_sites > 1 ? "s" : ""}, ${lot.n_sessions} session${lot.n_sessions > 1 ? "s" : ""}</small> ${badge(lot.verdict)}</h4>${feats.map(f => kpiRow(f, lot.kpis[f])).join("")}</div>`;
    }
    const testLots = Object.keys(LOTS).filter(l => l.startsWith("Test/"));
    $("#verdict-kpis").innerHTML = ["Batch_1", "Batch_2"].map(l => lotPanel(l, true)).join("");
    $("#verdict-decide").innerHTML = ["Batch_1", "Batch_2"].map(l => {
      const lot = LOTS[l];
      return `<div class="lotp"><h4>${l} ${badge(lot.verdict)}</h4><p class="act">${esc(lot.action)}</p><ul class="reasons">` +
        lot.reasons.map(r => `<li><b>${esc(r.label)}</b><br><small>${esc(r.detail)}</small>${r.action ? `<br><em>→ ${esc(r.action)}</em>` : ""}</li>`).join("") + "</ul></div>";
    }).join("");
    $("#verdict-test").innerHTML = testLots.map(l => lotPanel(l, false)).join("");
    const siLine = testLots.map(l => `${l.slice(5)}: Si ${sgn(LOTS[l].kpis.si_solid_frac.delta_sd, 1)} SD`).join(" · ");
    const toggleVerdict = layerToggler("verdict-stage");
    const bl = V.baseline.porosity_frac;
    register("verdict", {
      starts: [0, 0.34, 0.67],
      steps: [
        { k: "Normal variation", h: "Every feature against the Batch_3 baseline",
          p: `For each feature: the lot's mean minus the baseline mean, in units of the baseline's spot-to-spot SD, with a 90 % interval that treats spots of one imaging session as partly the same measurement. The shaded band is ±1.5 SD, the margin we call normal variation. Interval inside the band: <b>EQUIV</b>. Interval outside it: <b>BEYOND</b>. Anything else: <b>INCONCL</b>.`,
          stat: `baseline: ${bl.n} spots in ${bl.n_sessions} sessions · margin = ${CFG.margin_multiplier} × SD · ${CFG.tier1.length + CFG.tier2.length + CFG.diagnostics.length} features` },
        { k: "The rule", h: "Accept, investigate or reject",
          p: `Tier 1 (${CFG.tier1.map(flab).join(", ")}) decides. Tier 2 (${CFG.tier2.map(flab).join(", ")}) is a quality range: at least 6 of 7 spots inside the baseline mean ± 2.86 SD. The rest is shown, never decisive. <b>REJECT</b> needs a Tier-1 feature BEYOND after Holm, with the same sign in every shared session, on a feature that survives a black-level shift: only the Si-like share does. <b>ACCEPT</b> needs every Tier-1 feature EQUIV and no flag. Everything else is <b>INVESTIGATE</b>, with a named reason and an action. Nothing was tuned on Batch_1 or Batch_2.`,
          stat: `Batch_1: ${LOTS.Batch_1.verdict} · Batch_2: ${LOTS.Batch_2.verdict}` },
        { k: "One spot", h: "A single test spot cannot be judged",
          p: `The rule needs at least ${CFG.min_sites} sites, so each test spot alone is INSUFFICIENT DATA. Its features are still placed against the baseline, with the baseline's own spread standing in for the lot's. That is enough to see which test spot is Si-rich, and by how much.`,
          stat: siLine },
      ],
      update: (p, step) => toggleVerdict(step),
    });
    extraNodes.push({ label: "Verdict", line: "accept · investigate · reject vs Batch_3", sec: "verdict", steps: [0, 1, 2] });
    extraThumbs.push(thumbCanvas(ctx => {
      const cols = { ACCEPT: "#12937f", REJECT: "#c2410c", INVESTIGATE: "#e0a400" };
      ["Batch_1", "Batch_2"].forEach((l, i) => { ctx.fillStyle = cols[LOTS[l].verdict] || "#888"; ctx.fillRect(10, 10 + i * 30, 108, 22); });
    }));

    // ---- 06 battery sliders ----------------------------------------------------------------------------------
    const IM = R.impacts, PROPS = IM.properties, BANDS = IM.bands, lotKeys = Object.keys(IM.lots);
    const SX = v => 50 + 50 * clamp(v / 3, -1, 1);
    const toggleSliders = layerToggler("sliders-stage");
    let selLot = "Batch_1", selProp = "capacity", sliderStep = -1;
    function sliderRows(showLots) {
      return PROPS.map(pr => {
        const b3 = BANDS.Batch_3[pr.id], b1 = BANDS.Batch_1[pr.id], b2 = BANDS.Batch_2[pr.id], m = IM.lots[selLot][pr.id];
        const band = b => `<i class="iqr" style="left:${SX(b.q25)}%;width:${Math.max(0.6, SX(b.q75) - SX(b.q25))}%"></i>`;
        return `<div class="srow ${pr.id === selProp ? "sel" : ""}" data-prop="${pr.id}"><span class="sl"><b>${pr.label}</b><small>${pr.lower_label} ← · → ${pr.higher_label}</small></span>` +
          `<span class="saxis"><i class="band" style="left:${SX(b3.q25)}%;width:${Math.max(0.6, SX(b3.q75) - SX(b3.q25))}%"></i><i class="zero"></i>` +
          (showLots ? `<span class="lot1">${band(b1)}<b class="med" style="left:${SX(b1.median)}%"></b></span><span class="lot2">${band(b2)}<b class="med" style="left:${SX(b2.median)}%"></b></span>` : "") +
          (showLots && m && m.score !== null ? `<i class="mci" style="left:${SX(m.ci90[0])}%;width:${Math.max(0.6, SX(m.ci90[1]) - SX(m.ci90[0]))}%"></i><b class="mark" style="left:${SX(m.score)}%"></b>` : "") +
          `</span><span class="sv num">${showLots && m && m.score !== null ? `${sgn(m.score)} <small>${m.label.replace("_", " ")}</small>` : ""}</span></div>`;
      }).join("");
    }
    function contribPanel() {
      const m = IM.lots[selLot][selProp], pr = PROPS.find(p => p.id === selProp);
      if (!m) return "";
      const head = m.score === null ? "no usable feature" : `${sgn(m.score)} [${sgn(m.ci90[0])}, ${sgn(m.ci90[1])}] · ${m.label.replace("_", " ")} · P(higher) ${fmt(m.p_higher)} · P(lower) ${fmt(m.p_lower)}`;
      const rows = m.contributions.map(c => `<li><b>${flab(c.feature)}</b> <span class="num">${sgn(c.contribution)}</span> <small>(${sgn(c.delta_margin, 1)} margins${c.kind === "spread" ? ", spread" : ""} · ${c.confidence} evidence · ${c.trust} trust)</small><br><small>${esc(c.mechanism)} <i>${esc(c.citation)}</i></small></li>`).join("");
      return `<h4>${lotTitle(selLot)} · ${pr.label}: ${head}</h4><p class="q">${esc(pr.question)} ${esc(pr.blurb)}</p><ul class="contrib">${rows}</ul>` +
        (m.missing_features.length ? `<p class="note">not usable for this lot: ${m.missing_features.map(flab).join(", ")}</p>` : "") +
        m.estimates.map(e => `<p class="note">${esc(e.label)}: ${e.value} ${e.unit} [${e.lo}, ${e.hi}] — ${esc(e.assumption)}</p>`).join("");
    }
    function renderSliders() {
      const show = sliderStep >= 1;
      $("#slider-rows").innerHTML = sliderRows(show);
      $$("#slider-rows .srow").forEach(el => el.addEventListener("click", () => { selProp = el.dataset.prop; renderSliders(); }));
      $("#slider-lots").innerHTML = show ? lotKeys.map(l => `<button type="button" aria-pressed="${l === selLot}">${lotTitle(l)}</button>`).join("") : "";
      $$("#slider-lots button").forEach((b, i) => b.addEventListener("click", () => { selLot = lotKeys[i]; renderSliders(); }));
      $("#slider-contrib").innerHTML = show ? contribPanel() :
        `<p class="q">Each slider is a weighted average of the features the literature links to that property, in units of normal variation (±1.5 baseline SD), clipped at ±3. Weight = strength of the evidence × how much the feature is trusted to be material rather than microscope. Shaded: where Batch_3's own spots sit (interquartile range of per-spot scores). Positive always means more of the property.</p>`;
    }
    register("sliders", {
      starts: [0, 0.34, 0.67],
      steps: [
        { k: "Six properties", h: "From feature shifts to battery properties",
          p: `No paper gives a tolerance for a 2D section index, so every slider is directional and relative to the baseline: it says which way the measured shifts push a property and how sure the literature is, never a cycle count. Click a row to see its recipe.`,
          stat: `${PROPS.length} properties · ${Object.values(IM.rules).reduce((s, r) => s + r.length, 0)} cited rules` },
        { k: "Batch_1 and Batch_2", h: "Where each batch sits",
          p: `Dots and bars: the median and interquartile range of the per-spot scores of each batch. The teal marker: the model score for the selected lot with its 90 % interval, from a Monte Carlo over each feature's uncertainty. A lot that sits inside the Batch_3 band is, for that property, indistinguishable from the baseline.`,
          stat: `Batch_2 swelling ${sgn(IM.lots.Batch_2.swelling.score)} · Batch_1 capacity ${sgn(IM.lots.Batch_1.capacity.score)}` },
        { k: "Test spots", h: "One spot at a time",
          p: `For a single spot the spread terms are missing and the intervals borrow the baseline's variance, so they are wide. The Si-rich test spot pins the swelling and capacity sliders at the clip.`,
          stat: testLots.map(l => `${l.slice(5)}: swelling ${sgn(IM.lots[l].swelling.score)}`).join(" · ") },
      ],
      update: (p, step) => {
        if (step === sliderStep) return;
        sliderStep = step;
        toggleSliders(step);
        if (step === 2 && !selLot.startsWith("Test/")) selLot = lotKeys.find(l => l.startsWith("Test/")) || selLot;
        if (step === 1 && selLot.startsWith("Test/")) selLot = "Batch_1";
        renderSliders();
      },
    });
    renderSliders();
    extraNodes.push({ label: "Battery sliders", line: "what the science expects, with citations", sec: "sliders", steps: [0, 1, 2] });
    extraThumbs.push(thumbCanvas(ctx => {
      PROPS.forEach((pr, i) => { ctx.fillStyle = "#888"; ctx.fillRect(10, 8 + i * 11, 108, 2); const m = IM.lots.Batch_2[pr.id];
        if (m && m.score !== null) { ctx.fillStyle = "#3cc7b0"; ctx.fillRect(10 + 108 * SX(m.score) / 100 - 2, 5 + i * 11, 4, 8); } });
    }));

    // ---- 07 why ----------------------------------------------------------------------------------------------
    const EX = R.explain, EXS = EX ? EX.spots : {}, exKeys = Object.keys(EXS);
    const DIFF = R.v2 && R.v2.difference ? R.v2.difference : null;        // cnn/difference.py -> difference.json
    const hasExplain = EX && exKeys.length > 0;
    if (!hasExplain && !DIFF) $("#why").style.display = "none";
    else {
      const whySteps = [];
      const leak = PR ? PR.leak : (R.v2 && R.v2.score ? R.v2.score.leak_full_model : null);
      const leakWho = PR ? "" : " (V2 full model)";
      const pr = R.probe;
      if (hasExplain) {
        const testKeys = exKeys.filter(k => k.startsWith("Test/")), trainKeys = exKeys.filter(k => !k.startsWith("Test/"));
        let selSpot = testKeys[0] || exKeys[0];
        $("#why-spot").innerHTML = [...testKeys, ...trainKeys].map(k => `<option value="${k}">${k}${EXS[k].ablation ? " ★" : ""}</option>`).join("");
        $("#why-spot").value = selSpot;
        $("#why-spot").addEventListener("change", e => { selSpot = e.target.value; renderWhy(); });
        const ablName = { si_removed: "Si particles blanked", pores_removed: "pores blanked", control: "control: same shapes, random graphite" };
        const pBar = v => `<span class="pb">${v.map((p, i) => `<i style="width:${(100 * p).toFixed(1)}%;background:${bcol(i + 1)}" title="B${i + 1} ${pct(p)}"></i>`).join("")}</span>`;
        const nFeat = (EX.features || []).length || 13;
        function renderWhy() {
          const s = EXS[selSpot], call = s.call, dec = s.decomposition;
          const feats = dec.features.slice(0, 7), fmax = Math.max(...dec.features.map(f => Math.abs(f.contribution))) || 1;
          $("#why-head").innerHTML = `${s.y ? `true Batch_${s.y}, ` : "unlabeled, "}called <b style="color:${bcol(call)}">Batch_${call}</b> <small>(P ${s.p_insample.map((p, i) => `B${i + 1} ${pct(p)}`).join(" · ")})</small>`;
          $("#why-decomp").innerHTML = `<div class="share"><span class="bt"><i style="--w:${(100 * dec.share_known).toFixed(1)}%"></i></span><span><b>${pct(dec.share_known)}</b> of the pull towards Batch_${call} is explained by the ${nFeat} named features; the rest is something the features do not name.</span></div>` +
            `<div class="fbars">${feats.map(f => `<div class="frow"><span class="fl">${flab(f.feature)}<small>${sgn(f.delta_b3_sd, 1)} SD vs Batch_3</small></span><span class="fax"><i class="zero"></i><i class="fb ${f.contribution >= 0 ? "pos" : "neg"}" style="left:${f.contribution >= 0 ? 50 : 50 - 50 * Math.abs(f.contribution) / fmax}%;width:${50 * Math.abs(f.contribution) / fmax}%"></i></span><span class="num">${sgn(f.contribution)}</span></div>`).join("")}</div>` +
            `<p class="note">bars: how much each feature moved this spot's score towards (right) or away from (left) Batch_${call}, through the linear map from features to embedding. "SD vs Batch_3": where the feature's own value sits against the baseline.</p>`;
          const g = s.heat.grid, lo = s.heat.min, hi = s.heat.max;
          $("#why-heat").innerHTML = `<div class="heat">${g.map(row => `<div class="hrow">${row.map(v => `<i style="background:${v === null ? "transparent" : lutCss((v - lo) / (hi - lo || 1))}" title="${fmt(v)}"></i>`).join("")}</div>`).join("")}</div>` +
            `<div class="tops">${s.heat.top.map(t => `<figure><div class="pair2"><img src="${t.bse}" alt=""><img src="${t.map}" alt=""></div><figcaption>tile r${t.row}c${t.col} · score ${fmt(t.score)}<br><small>pore ${pct(t.map_fractions[0])} · graphite ${pct(t.map_fractions[1])} · Si ${pct(t.map_fractions[2])}</small></figcaption></figure>`).join("")}</div>` +
            `<p class="note">top: the spot's ${g.length} × ${g[0] ? g[0].length : 0} tiles coloured by their score along the Batch_${call} direction (yellow = most like it; the tiles average exactly to the spot's score). Below: the three strongest tiles, BSE and the network's own material map (blue pore, grey graphite, amber Si).</p>`;
          const AT = R.attribution && R.attribution.spots ? R.attribution.spots[selSpot] : null;
          if (AT) {
            const mats = [["pore", "pores"], ["si", "Si"], ["graphite", "graphite"]];
            const enr = mats.map(([k, lab]) => { const sh = AT.share[k], ar = AT.area[k]; return `<div class="frow"><span class="fl">${lab}<small>${pct(ar)} of the area</small></span><span class="fax"><i class="zero"></i><i class="fb ${sh >= ar ? "pos" : "neg"}" style="--w:${(50 * Math.min(1, Math.abs(sh - ar) / 0.5)).toFixed(1)}%"></i></span><span class="num">${pct(sh)} of the pull</span></div>`; }).join("");
            const det = Object.entries(AT.detector_share).map(([d, v]) => `${d} ${pct(v)}`).join(" · ");
            $("#why-heat").innerHTML += `<h4>Where in the image, pixel by pixel</h4><figure class="attr"><img src="${AT.mosaic}" alt=""><figcaption>the spot's ${AT.grid[0]} × ${AT.grid[1]} tiles over the BSE image: red pushes towards Batch_${AT.call}, blue away (exact decomposition of the classifier's score into ${R.attribution.cell_px} px cells; max rounding error ${AT.completeness_max_err.toExponential(1)})</figcaption></figure>` +
              `<div class="fbars">${enr}</div><p class="note">what the red falls on: the share of the positive pull that sits on pore, Si and graphite pixels against each material's share of the area. A material that carries more of the pull than its area is what the network is reading. Detectors carrying the call: ${det}.</p>`;
          }
          const nb = s.neighbours, nl = L => L.map(n => `<li><b style="color:${bcol(n.batch)}">B${n.batch}</b> ${n.key.split("/")[1]} <small>session ${n.session} · cos ${fmt(n.cos, 3)}</small></li>`).join("");
          $("#why-nb").innerHTML = `<div class="nbcols"><div><h4>Most similar training spots</h4><ol>${nl(nb.all)}</ol></div><div><h4>… from other imaging sessions</h4><ol>${nl(nb.other_sessions)}</ol></div></div>` +
            `<p class="note">Case-based evidence: the spots this one resembles in embedding space. If the two lists differ a lot, the embedding is partly recognising the session rather than the material.</p>`;
          const ab = s.ablation, pe = s.perturbation;
          if (ab) {
            const base = ab.base_p.indexOf(Math.max(...ab.base_p)) + 1;
            const row = (name, v) => `<div class="frow"><span class="fl">${name}</span>${pBar(v.p)}<span class="num">B${v.call}${v.call !== base ? " ⇄" : ""}</span></div>`;
            $("#why-abl").innerHTML = `<h4>Take a material away and re-embed</h4><div class="fbars">${row("as imaged", { p: ab.base_p, call: base })}${Object.keys(ablName).map(k => row(ablName[k], ab[k])).join("")}</div>` +
              `<h4>Change the microscope and re-embed</h4><div class="fbars">${Object.keys(pe).filter(k => k !== "base_p").map(k => row(k.replace(/_/g, " "), pe[k])).join("")}</div>` +
              `<p class="note">bars are P(B1 | B2 | B3) after the ${R.n_tiles_per_spot || P.tiles.grid.length} tiles were altered and re-embedded; ⇄ marks a flipped call. A call that flips when the Si is blanked was carried by the Si; one that flips under a black-level or gain change was carried by the imaging. The control blanks graphite with the same shapes, so it separates "material removed" from "inpainting artefact".</p>`;
          } else $("#why-abl").innerHTML = `<p class="note">Ablations and perturbations were run on the spots marked ★ in the selector (the test spots and two per batch); pick one to see them.</p>`;
        }
        renderWhy();
        whySteps.push(
          { k: "Named features", h: "How much of the call is things we can name",
            p: `The embedding splits into the part a linear map from the ${nFeat} tile features reproduces and the rest. The spot's score along its called batch's direction is the sum of the two, so the first bar is the share of the call that named features explain, and each feature below gets its own signed push.`,
            stat: `pick any of the ${exKeys.length} spots above` },
          { k: "Where", h: "Which tiles carry the call",
            p: `Every tile is scored along the same direction; the grid of ${R.n_tiles_per_spot || P.tiles.grid.length} tiles is the spot. The strongest tiles are shown with the material map the network itself predicts, so a materials expert can look at exactly the structure that drove the call.`,
            stat: "yellow = most like the called batch" },
          { k: "Neighbours", h: "Which spots it resembles",
            p: `The five closest training spots by cosine similarity, once overall and once excluding the spot's own imaging session. The second list is the honest one.`,
            stat: leak ? `session leak: ${pct(leak.nn_same_session_rate)} vs chance ${pct(leak.nn_chance)}` : "" },
          { k: "Counterfactuals", h: "Remove a material, change the microscope, re-embed",
            p: `Blank the Si particles (or the pores) with graphite-like pixels in all ${R.n_tiles_per_spot || P.tiles.grid.length} tiles, run them through the network again, and watch the batch probabilities. Then do the same with a black-level offset, a gain change and extra noise. The first says what the call is made of; the second says whether it is made of the microscope.`,
            stat: "run for the test spots and two spots per batch" });
      } else {
        $("#why-top").style.display = "none";
        ["why-decomp", "why-heat", "why-nb", "why-abl"].forEach(id => { $("#" + id).innerHTML = ""; });
      }
      // the Differences step: an embedding difference read through the named features (difference.json)
      if (DIFF) {
        const order = { batch: 0, test: 1, spots: 2 };
        const pairs = DIFF.pairs.slice().sort((a, b) => (order[a.kind] ?? 3) - (order[b.kind] ?? 3));
        const dmax = Math.max(...pairs.flatMap(q => Object.values(q.features).map(Math.abs))) || 1;
        const kindTitle = { batch: "Batch against batch (means of their spots)", test: "Each test spot against Batch_3", spots: "Two spots" };
        let lastKind = null;
        $("#why-diff").innerHTML = pairs.map(q => {
          const top = Object.entries(q.features).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 6);
          const head = q.kind !== lastKind ? `<h4 class="dkind">${kindTitle[q.kind] || q.kind}</h4>` : "";
          lastKind = q.kind;
          return head + `<div class="dpair"><div class="share"><span class="bt"><i style="--w:${(100 * q.share_named).toFixed(1)}%"></i></span><span><b>${esc(q.label)}</b>: <b>${pct(q.share_named)}</b> of this difference is named features <small>· distance ${fmt(q.distance, 1)}</small></span></div>` +
            `<div class="fbars">${top.map(([f, v]) => `<div class="frow"><span class="fl">${flab(f)}</span><span class="fax"><i class="zero"></i><i class="fb ${v >= 0 ? "pos" : "neg"}" style="left:${v >= 0 ? 50 : 50 - 50 * Math.abs(v) / dmax}%;width:${Math.max(0.4, 50 * Math.abs(v) / dmax)}%"></i></span><span class="num">${sgn(v)} SD</span></div>`).join("")}</div></div>`;
        }).join("") +
          `<p class="note">A linear read-out from the tile embedding to the ${DIFF.features.length} named features (fitted on all training tiles, R² ${fmt(DIFF.readout_r2_tiles)}) turns the difference between two embeddings into a predicted difference in every feature, in units of Batch_3's spot-to-spot SD of that feature (right = the first item has more). The six largest are shown per pair, all on one scale. The first bar is the share of the difference that lies along the named features; the rest is what the embedding knows and the features do not name.</p>`;
        whySteps.push({ k: "Differences", h: "What the difference between two embeddings is made of",
          p: `Take the V2 embedding of one batch (the mean of its spots) minus another, or a test spot minus Batch_3, and read that difference through the ${DIFF.features.length} named features. A bar to the right says the first item has more of that feature, in units of Batch_3's normal spot-to-spot variation. The share bar says how much of the difference the named features can account for at all.`,
          stat: pairs.filter(q => q.kind === "batch").map(q => `${q.label.replace(" (means)", "")}: ${pct(q.share_named)} named`).join(" · ") });
      } else {
        $("#why-diff").innerHTML = `<p class="note">not run yet: python cnn/difference.py --name v2</p>`;
        whySteps.push({ k: "Differences", h: "What the difference between two embeddings is made of",
          p: `Reads the V2 embedding difference between two batches, or a test spot and Batch_3, through the named features. Not run yet: <code>python cnn/difference.py --name v2</code> writes difference.json.`, stat: "not run yet" });
      }
      const toggleWhy = layerToggler("why-stage");
      const topR2 = pr ? Object.entries(pr.r2).sort((a, b) => b[1] - a[1]).slice(0, 2) : [];
      $("#why-stats").innerHTML =
        (leak ? `<dt>Session leak${leakWho}: nearest neighbour in the same session</dt><dd>${pct(leak.nn_same_session_rate)}<br><small>chance ${pct(leak.nn_chance)}, p ${fmt(leak.nn_perm_p, 3)}</small></dd>` +
          `<dt>Session guessed from the embedding</dt><dd>${fmt(leak.loo_session_bacc_multi)}<br><small>chance ${fmt(leak.loo_chance)}</small></dd>` : "") +
        (pr ? `<dt>Features the embedding predicts best (R² per tile)</dt><dd>${topR2.map(([f, v]) => `${flab(f)} ${fmt(v)}`).join("<br>")}</dd>` +
          `<dt>Batch signal left after removing the features</dt><dd>${fmt(pr.scores.complement.lr_losess)}<br><small>p ${fmt(pr.scores.complement.lr_losess_perm_p, 3)}; noise alone gives ${fmt(pr.synthetic_complement_losess)}</small></dd>` : "");
      const n = whySteps.length;
      register("why", {
        starts: Array.from({ length: n }, (_, i) => i / n),
        steps: whySteps,
        update: (p, step) => toggleWhy(hasExplain ? step : 4),      // without explain.json the only step is Differences (layer 4)
      });
      extraNodes.push({ label: "Why", line: hasExplain ? "features, tiles, neighbours, ablations, differences" : "embedding differences through the named features", sec: "why", steps: Array.from({ length: n }, (_, i) => i) });
      const t0 = hasExplain ? (EXS[Object.keys(EXS)[0]].heat.top[0] || {}).bse : null;
      extraThumbs.push(t0 || thumbCanvas(ctx => { ctx.fillStyle = "#888"; ctx.fillRect(10, 10, 108, 52); }));
    }
  }

  // ==========================================================================================================
  // 07b  embedding map: PCA of the spot embeddings  (present when cnn/pca_plot.py wrote pca.js)
  // ==========================================================================================================
  const PCA = window.PCA;
  if (!PCA) $("#pca").style.display = "none";
  if (PCA) {
    let pcaView = PCA.views.length - 1;
    function interpTable() {      // literature features against the embedding's batch axes (cnn/interpret_features.py)
      try {
        const I = PCA.interpret; if (!I) return "";
        return `<h4>What the batch signal is made of: the ${I.n_features} literature features against the label-free embedding's batch axes</h4>` +
          I.axes.map(a => `<p class="q"><b>${esc(a.what)}</b> (${esc(a.check)}). Strongest links, Spearman across the 31 spots:</p>` +
            `<table class="conf lit-overall"><thead><tr><th>literature feature</th><th>ledger entry</th><th>link</th><th>inside sessions</th><th>q</th><th>papers: more of it means</th></tr></thead><tbody>` +
            a.top.map(t => `<tr><th>${esc(flab(t.feature))}</th><td>${esc(t.entry || "–")}</td><td class="num">${sgn(t.rho)}</td><td class="num">${t.rho_session === null ? "–" : sgn(t.rho_session)}</td><td class="num">${fmt(t.q, 3)}</td><td>${(t.outcomes || []).map(o => `<span class="lit-chip ${o.good ? "good" : "bad"}">${o.more ? "▲" : "▼"} ${esc(o.label)} <small>${o.n}</small></span>`).join(" ") || '<small class="note">no agreed effect, or not yet asked</small>'}</td></tr>`).join("") +
            `</tbody></table>`).join("") +
          `<p class="note">Reading the last column: a positive link means images further along this axis have more of the feature; the chips say what full-text papers agree more of that feature does to a cell (number = papers; green good, orange bad). "Inside sessions" removes each imaging session's mean first: a link that survives there is not the microscope. q is corrected for testing all features. From cnn/results/interpret_${esc(I.tag)}.md.</p>`;
      } catch (e) { return ""; }
    }
    function renderPca() {
      const v = PCA.views[pcaView], W = 720, H = 440, pad = 34;
      const pts = v.spots.concat(v.test), xs = pts.map(p => p.x), ys = pts.map(p => p.y);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      const X = x => pad + (W - 2 * pad) * (x - x0) / ((x1 - x0) || 1), Y = y => H - pad - (H - 2 * pad) * (y - y0) / ((y1 - y0) || 1);
      const tiles = v.tiles.map(t => `<circle cx="${X(t[0]).toFixed(1)}" cy="${Y(t[1]).toFixed(1)}" r="1.6" fill="${bcol(t[2])}" opacity="0.22"/>`).join("");
      const spots = v.spots.map(p => `<circle cx="${X(p.x).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="7" fill="${bcol(+p.batch.slice(6))}" stroke="var(--bg)" stroke-width="1.5"><title>${p.id} · ${p.batch} · image height ${p.session}</title></circle>`).join("");
      const test = v.test.map(p => { const cx = X(p.x), cy = Y(p.y);
        return `<path d="M${cx} ${cy - 9}L${cx + 9} ${cy}L${cx} ${cy + 9}L${cx - 9} ${cy}Z" fill="var(--ink)" stroke="var(--bg)" stroke-width="1.5"><title>test spot ${p.id}</title></path>` +
          `<text x="${cx + 12}" y="${cy + 4}" font-size="11" fill="var(--ink)">${p.id}</text>`; }).join("");
      $("#pca-views").innerHTML = PCA.views.map((w, i) => `<button type="button" aria-pressed="${i === pcaView}">${esc(w.label)}</button>`).join("");
      $$("#pca-views button").forEach((b, i) => b.addEventListener("click", () => { pcaView = i; renderPca(); }));
      $("#pca-plot").innerHTML = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-height:56vh;border:1px solid var(--line);border-radius:8px">` +
        `<text x="${W / 2}" y="${H - 8}" text-anchor="middle" font-size="11" fill="var(--muted)">axis 1 · ${pct(v.var[0])} of the spread</text>` +
        `<text x="12" y="${H / 2}" text-anchor="middle" font-size="11" fill="var(--muted)" transform="rotate(-90 12 ${H / 2})">axis 2 · ${pct(v.var[1])}</text>` +
        tiles + spots + test + `</svg>`;
      $("#pca-note").innerHTML = `<p class="q"><b>${esc(v.label)}.</b> ${esc(v.note)} Each spot is ${v.dims} numbers; these two axes hold ${pct(v.var[0] + v.var[1])} of their spread. ` +
        `PCA shows the directions with the most spread, not the ones that best separate the batches, so overlap here does not mean the batches cannot be told apart. Hover a dot for the spot.</p>` + interpTable();
    }
    register("pca", {
      starts: [0],
      steps: [{ k: "The map", h: "Do the batches form groups?",
        p: `One dot per spot, coloured by batch. Dots close together have similar embeddings. Switch between the label-free model, the label-trained one and the two side by side. Only the label-free view is free of the labels: the others were trained on these 31 spots.`,
        stat: `${PCA.n_spots} spots · ${PCA.n_tiles} tiles · ${PCA.views.length} views` }],
      update: () => {},
    });
    renderPca();
    extraNodes.push({ label: "Embedding map", line: "where the batches sit, in two axes", sec: "pca", steps: [0] });
    extraThumbs.push(thumbCanvas(ctx => {
      const v = PCA.views[PCA.views.length - 1], xs = v.spots.map(p => p.x), ys = v.spots.map(p => p.y);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), col = ["#8f98ff", "#ff8f5a", "#3cc7b0"];
      v.spots.forEach(p => { ctx.fillStyle = col[+p.batch.slice(6) - 1]; ctx.beginPath();
        ctx.arc(8 + 112 * (p.x - x0) / ((x1 - x0) || 1), 64 - 56 * (p.y - y0) / ((y1 - y0) || 1), 3.5, 0, 6.3); ctx.fill(); });
    }));
  }

  // ==========================================================================================================
  // 08  papers: feature -> outcome evidence and the batch outlook  (present when literature/batch_outlook.py ran)
  // ==========================================================================================================
  const LIT = window.LITERATURE;
  if (!LIT) $("#papers").style.display = "none";
  if (LIT) {
    const SYM = { more: ["▲", "lit-up", "more"], less: ["▼", "lit-down", "less"], optimum: ["◆", "lit-opt", "an optimum"],
                  mixed: ["≈", "lit-mix", "papers disagree"], "too few papers": ["·", "lit-none", "too few papers"] };
    const doiLink = q => q.doi ? `<a href="https://doi.org/${esc(q.doi)}" target="_blank" rel="noopener">${esc(q.title)}</a>` : esc(q.title);
    const cname = id => LIT.concepts.find(c => c.id === id).label;
    const oname = id => LIT.outcomes.find(o => o.id === id).label;
    let selCell = "si_fraction|swelling", litLot = "Batch_2", litOutcome = "swelling", litStep = -1;
    const toggleLit = layerToggler("papers-stage");

    function matrix() {
      return `<table class="lit-matrix"><thead><tr><th></th>${LIT.outcomes.map(o => `<th>${o.label}</th>`).join("")}</tr></thead><tbody>` +
        LIT.concepts.map(c => `<tr><th>${c.label}<small>${c.features.map(flab).join(", ")}</small></th>` + LIT.outcomes.map(o => {
          const key = `${c.id}|${o.id}`, pr = LIT.pairs[key]; if (!pr) return "<td></td>";
          const [ch, cls] = SYM[pr.consensus];
          return `<td class="${cls} ${key === selCell ? "sel" : ""}" data-key="${key}" title="${pr.counts[0]} more · ${pr.counts[1]} less · ${pr.counts[2]} optimum · ${pr.counts[3]} no effect">${ch}<small>${pr.n}</small></td>`;
        }).join("") + "</tr>").join("") + "</tbody></table>";
    }
    function cellPanel() {
      const [c, o] = selCell.split("|"), pr = LIT.pairs[selCell]; if (!pr) return "";
      const rules = pr.rules.map(r => `<span class="lit-rule ${r.literature === "agrees" ? "ok" : ""}">slider rule for ${flab(r.feature)} (sign ${r.sign > 0 ? "+" : "−"}): ${esc(r.literature)}</span>`).join(" ");
      return `<h4>When ${cname(c)} is higher, is ${oname(o).toLowerCase()} higher? Papers say: <b class="${SYM[pr.consensus][1]}">${SYM[pr.consensus][2]}</b></h4>` +
        `<p class="q">${pr.counts[0]} more · ${pr.counts[1]} less · ${pr.counts[2]} an optimum · ${pr.counts[3]} no effect, from ${pr.n} full-text papers. ${rules}</p>` +
        `<ul class="contrib">${pr.quotes.map(q => `<li><span class="lit-src gxl">GXL · read</span> <b>${esc(q.direction.replace("feature_up_outcome_up", "more").replace("feature_up_outcome_down", "less").replace("non_monotonic", "optimum").replace("no_clear_effect", "no effect"))}</b> <small>(${esc(q.evidence_type)}${q.material ? ", " + esc(q.material) : ""})</small><br>“${esc(q.quote)}” <small>${doiLink(q)} (${esc(q.year)})</small></li>`).join("")}</ul>` +
        ((pr.web || []).length ? `<ul class="contrib">${pr.web.map(w => `<li><span class="lit-src web">web search · not GXL · not read</span> <small><a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.title)}</a> (${esc(w.authors)}, ${esc(w.venue)}). ${esc(w.says)} <i>Our reading: ${esc(w.reading)}.</i></small></li>`).join("")}</ul>` : "") +
        (pr.abstract_only.length ? `<p class="note"><span class="lit-src gxla">GXL · abstract only · not read</span> ${pr.abstract_only.map(a => `<a href="https://doi.org/${esc(a.doi)}" target="_blank" rel="noopener">${esc(a.title)}</a> (${a.year})`).join("; ")}</p>` : "");
    }
    // ---- step 0: what a feature looks like (three real tiles), where the batches sit, what the papers say ----
    const CARDS = LIT.cards ? LIT.cards.cards : [];
    let selCard = 0;
    function renderCard() {
      if (!CARDS.length) { $("#lit-card").innerHTML = `<p class="note">Run literature/feature_cards.py to add the pictures.</p>`; return; }
      $("#lit-card-tabs").innerHTML = CARDS.map((c, i) => `<button type="button" aria-pressed="${i === selCard}">${esc(c.label)}</button>`).join("");
      $$("#lit-card-tabs button").forEach((b, i) => b.addEventListener("click", () => { selCard = i; renderCard(); }));
      const c = CARDS[selCard], names = ["low", "typical", "high"];
      const pics = c.tiles.map((t, k) => `<figure><img src="${t.img}" alt="${names[k]}"><figcaption><b>${names[k]}</b> · ${esc(t.text)}<small>from ${t.batch} · ${esc(t.sample_id)}</small></figcaption></figure>`).join("");
      const marks = Object.entries(c.batches).map(([b, v]) => `<b class="lit-bm" style="left:${(4 + 92 * v.pos).toFixed(1)}%;background:${bcol(+b.slice(6))}" title="${b}: ${esc(v.text)}">${b.slice(6)}</b>`).join("");
      const legend = Object.entries(c.batches).map(([b, v]) => `<span style="color:${bcol(+b.slice(6))}"><b>${b}</b> ${esc(v.text)}</span>`).join(" · ");
      const chips = c.effects.map(e => { const good = (e.more ? 1 : -1) * LIT.outcomes.find(o => o.id === e.outcome).good > 0;
        return `<span class="lit-chip ${good ? "good" : "bad"}" title="${e.counts[0]} papers say more, ${e.counts[1]} less, ${e.counts[2]} an optimum">${e.more ? "▲" : "▼"} ${esc(e.label)} <small>${e.n} papers</small></span>`; }).join("");
      $("#lit-card").innerHTML =
        `<div class="lit-pics">${pics}</div>` +
        `<div class="lit-axis"><span>low</span><div class="lit-track">${marks}</div><span>high</span></div>` +
        `<p class="q">Where the batches sit between the low and the high picture (batch mean over its spots): ${legend}. ` +
        `Tint: ${c.tint === "si" ? "silicon in yellow" : "pores in blue"}. Each picture is one 12.8 µm tile.</p>` +
        `<h4>The papers say more of this means:</h4><div class="lit-chips">${chips || '<span class="note">no agreed effect in the papers read</span>'}</div>` +
        `<p class="q"><b>So a higher value is ${esc(c.lean)}.</b> Green = good for the cell, orange = bad. Counts are full-text papers read by GXL Paperclip; the sentences are in the next step.</p>`;
    }
    // ---- step 1: the grid, either what the papers say or what that does to one batch ----
    let litView = "papers";
    function batchMatrix(b) {
      const G = (LIT.grid || {})[b] || {}, mag = v => Math.min(1, Math.abs(v) / 1.5);
      return `<table class="lit-matrix"><thead><tr><th></th>${LIT.outcomes.map(o => `<th>${o.label}<small>more is ${o.good > 0 ? "good" : "bad"}</small></th>`).join("")}</tr></thead><tbody>` +
        LIT.concepts.map(c => `<tr><th>${c.label}<small>${c.features.map(flab).join(", ")}</small></th>` + LIT.outcomes.map(o => {
          const key = `${c.id}|${o.id}`, g = G[key];
          if (!g || Math.abs(g.effect) < 0.05) return `<td class="lit-none" data-key="${key}">·</td>`;
          const up = g.effect > 0, good = (up ? 1 : -1) * o.good > 0;
          return `<td class="${key === selCell ? "sel" : ""}" data-key="${key}" style="color:${good ? "var(--c3)" : "var(--c2)"};opacity:${(0.35 + 0.65 * mag(g.effect)).toFixed(2)};font-weight:${g.clear ? 700 : 400}" ` +
            `title="${b}: this feature sits ${sgn(g.shift, 1)} SD from Batch_3${g.clear ? "" : " (not clear of zero)"}; papers say higher means ${g.papers_say} (${g.n} papers)">${up ? "▲" : "▼"}<small>${sgn(g.effect, 1)}</small></td>`;
        }).join("") + "</tr>").join("") + "</tbody></table>" +
        `<p class="q">${b} against Batch_3. Arrow: which way this batch's measured shift pushes the outcome, given what the papers say. Green = better for the cell, orange = worse; bold = the shift is clear of zero; faint = small. A dot means no shift or no agreed direction.</p>`;
    }
    function renderMatrix() {
      const views = [["papers", "What the papers say"], ["Batch_1", "Batch_1"], ["Batch_2", "Batch_2"]];
      $("#lit-view").innerHTML = views.map(([id, lab]) => `<button type="button" aria-pressed="${id === litView}">${lab}</button>`).join("");
      $$("#lit-view button").forEach((b, i) => b.addEventListener("click", () => { litView = views[i][0]; renderMatrix(); }));
      $("#lit-matrix").innerHTML = litView === "papers" ? matrix() : batchMatrix(litView);
      $$("#lit-matrix td[data-key]").forEach(td => td.addEventListener("click", () => { selCell = td.dataset.key; renderMatrix(); }));
      $("#lit-cell").innerHTML = cellPanel();
    }
    const LX = v => 50 + 50 * clamp(v / 2, -1, 1);
    function renderOutlook() {
      const OV = LIT.overall, order = ["Batch_1", "Batch_2", "Batch_3"].sort((a, b) => OV[b].p_best - OV[a].p_best);
      $("#lit-overall").innerHTML = `<table class="conf lit-overall"><thead><tr><th>Batch</th><th>leans towards being the best of the three</th><th>score against Batch_3, 90 % interval</th></tr></thead><tbody>` +
        order.map(b => `<tr><th style="color:${bcol(+b.slice(6))}">${b}</th><td class="num">${pct(OV[b].p_best)}</td><td class="num">${b === "Batch_3" ? "0 (the reference)" : `${sgn(OV[b].score)} [${sgn(OV[b].ci90[0])}, ${sgn(OV[b].ci90[1])}]`}</td></tr>`).join("") + "</tbody></table>";
      $("#lit-lots").innerHTML = ["Batch_1", "Batch_2"].map(b => `<button type="button" aria-pressed="${b === litLot}">${b}</button>`).join("");
      $$("#lit-lots button").forEach((el, i) => el.addEventListener("click", () => { litLot = ["Batch_1", "Batch_2"][i]; renderOutlook(); }));
      $("#lit-outcomes").innerHTML = LIT.outcomes.map(o => {
        const m = LIT.batches[litLot][o.id], good = o.good * m.score > 0;
        return `<div class="srow ${o.id === litOutcome ? "sel" : ""}" data-o="${o.id}"><span class="sl"><b>${o.label}</b><small>more is ${o.good > 0 ? "good" : "bad"}</small></span>` +
          `<span class="saxis"><i class="zero"></i><i class="mci" style="left:${LX(m.ci90[0])}%;width:${Math.max(0.6, LX(m.ci90[1]) - LX(m.ci90[0]))}%"></i><b class="mark" style="left:${LX(m.score)}%"></b></span>` +
          `<span class="sv num">${sgn(m.score)} <small>${m.ci90[0] > 0 || m.ci90[1] < 0 ? (good ? "better" : "worse") : "not clear"}</small></span></div>`;
      }).join("");
      $$("#lit-outcomes .srow").forEach(el => el.addEventListener("click", () => { litOutcome = el.dataset.o; renderOutlook(); }));
      const m = LIT.batches[litLot][litOutcome];
      $("#lit-drivers").innerHTML = `<h4>${litLot} · ${oname(litOutcome)}: ${sgn(m.score)} [${sgn(m.ci90[0])}, ${sgn(m.ci90[1])}]</h4>` +
        (m.drivers.length ? `<ul class="contrib">${m.drivers.map(d => `<li><b>${d.features.map(flab).join(", ")}</b> <span class="num">${sgn(d.effect)}</span> ` +
          `<small>(shift ${sgn(d.shift_sd, 1)} SD${d.clear ? "" : ", not clear of zero"} · papers say higher means ${d.papers_say}: ${d.counts.feature_up_outcome_up} more, ${d.counts.feature_up_outcome_down} less, ${d.counts.non_monotonic} optimum · ${d.n_papers} papers)</small>` +
          (d.quote ? `<br><span class="lit-src gxl">GXL · read</span> <small>“${esc(d.quote.text)}” ${doiLink(d.quote)} (${esc(d.quote.year)})</small>` : "") + `</li>`).join("")}</ul>`
          : `<p class="note">No feature has an agreed direction in the papers read.</p>`);
    }
    function renderTrust() {
      const T = LIT.totals, rules = Object.entries(LIT.pairs).flatMap(([k, pr]) => pr.rules.map(r => ({ ...r, key: k, n: pr.n })));
      $("#lit-trust").innerHTML =
        `<h4>The ${T.rules} slider rules of section 06 against the papers: ${T.rules_agree} agree, ${T.rules - T.rules_agree - T.rules_disagree} not settled, ${T.rules_disagree} contradicted</h4>` +
        `<ul class="contrib lit-rules">${rules.sort((a, b) => (a.literature === "agrees") - (b.literature === "agrees")).map(r => `<li class="${r.literature === "agrees" ? "ok" : "open"}"><b>${flab(r.feature)}</b> → ${oname(r.key.split("|")[1])} <small>(sign ${r.sign > 0 ? "+" : "−"})</small>: ${esc(r.literature)} <small>· ${r.n} papers</small></li>`).join("")}</ul>` +
        `<h4>How much "which batch" depends on the choices</h4><p class="q">Batch_3 is the baseline: what the supplier promised, with Batch_1 and Batch_2 arriving afterwards. Baseline does not mean defect-free; its score is 0 because the other two are measured against it.</p>` +
        `<table class="conf lit-overall"><thead><tr><th>If…</th>${[1, 2, 3].map(i => `<th style="color:${bcol(i)}">Batch_${i} best</th>`).join("")}</tr></thead><tbody>` +
        (LIT.sensitivity || []).map(r => `<tr><th>${esc(r.choice)}</th>${["Batch_1", "Batch_2", "Batch_3"].map(b => `<td class="num">${pct(r[b])}</td>`).join("")}</tr>`).join("") + `</tbody></table>` +
        `<h4>What this cannot tell you</h4><ul class="contrib"><li><b>Silicon is confirmed, silicon oxide is not.</b> Polaron says the bright particles are silicon and the dark ones graphite. Several papers read are about silicon oxide, which swells less.</li><li><b>The batches are constructed groups.</b> Polaron cut about 20 large images into crops and grouped the crops on features it extracted, so a batch is a kind of microstructure, not a production lot.</li>` +
        `<li><b>The chances are too confident.</b> Features are redrawn independently although several move together. Read them as a lean, not a measured probability.</li>` +
        `<li><b>A machine read the papers.</b> Every sentence was found in its paper, but nobody checked that the paper's material matches this electrode.</li>` +
        `<li><b>Open-access papers only.</b> The reader cannot open the paywalled electrochemistry journals; those are listed as not read.</li>` +
        `<li><b>No cycling data.</b> Every outcome is an expectation from the literature, not a measurement on these batches.</li></ul>`;
    }
    const OV = LIT.overall, T = LIT.totals, lead = ["Batch_1", "Batch_2", "Batch_3"].sort((a, b) => OV[b].p_best - OV[a].p_best)[0];
    register("papers", {
      starts: [0, 0.25, 0.5, 0.75],
      steps: [
        { k: "See it", h: "What each feature looks like, and what more of it does",
          p: `Three real tiles for each feature: a low, a typical and a high one, with the measured phase tinted. The coloured markers show where each batch sits between them. Underneath, what the papers agree more of that feature does to a battery. Pick a feature above the pictures.`,
          stat: `${CARDS.length} features · tiles at the 5th, 50th and 95th percentile` },
        { k: "The literature", h: "One question per feature and outcome",
          p: `For example: when porosity is higher, is charging faster or slower? GXL Paperclip's reader opens the full-text papers it finds and answers in a fixed form with one sentence copied from the paper. An answer is kept only if that sentence is found in the paper's text. Switch to Batch_1 or Batch_2 above the table to see which way that batch's measured shifts push each outcome. Click a cell for the sentences. Each item is tagged with where it came from: found and read by GXL Paperclip (the only ones counted), found by GXL but abstract only, or from an ordinary web search.`,
          stat: `${T.questions} questions · ${T.papers} papers read by GXL (${T.answers} answers) · ${T.web} extra from web search, not counted` },
        { k: "Which batch", h: "Measured shifts × what the papers say",
          p: `Each feature's shift from Batch_3 (section 05) is multiplied by the direction the papers agree on and weighted by how many papers there are. Good means more capacity, faster charging, longer life and more uniformity, and less first-charge loss and swelling, all counted equally. Click an outcome to see what drives it.`,
          stat: `${lead} leans best (${pct(OV[lead].p_best)}) · Batch_1 better than Batch_2: ${pct(OV.p_batch1_better_than_batch2)}` },
        { k: "How far to trust it", h: "A check on the sliders, and the limits",
          p: `The same counts test the sign of every slider rule in section 06. A rule the papers agree with is supported by sentences you can read; one that is not settled should be shown as an assumption.`,
          stat: `${T.rules_agree} of ${T.rules} slider rules agree · ${T.rules_disagree} contradicted` },
      ],
      update: (p, step) => {
        if (step === litStep) return;
        litStep = step;
        toggleLit(step);
        if (step === 0) renderCard(); else if (step === 1) renderMatrix(); else if (step === 2) renderOutlook(); else renderTrust();
      },
    });
    renderCard();
    extraNodes.push({ label: "Production literature", line: "what each feature does to a battery, and which batch that favours", sec: "papers", steps: [0, 1, 2, 3] });
    extraThumbs.push(thumbCanvas(ctx => {
      const col = { more: "#3cc7b0", less: "#ff8f5a", optimum: "#ffc22e", mixed: "#888", "too few papers": "#444" };
      LIT.concepts.forEach((c, i) => LIT.outcomes.forEach((o, j) => { const pr = LIT.pairs[`${c.id}|${o.id}`]; ctx.fillStyle = col[pr ? pr.consensus : "too few papers"]; ctx.fillRect(10 + j * 18, 3 + i * 6, 16, 5); }));
    }));
  }

  // ==========================================================================================================
  // 09  the research harness: papers -> ledger -> plug-in -> tests -> GXL evidence  (present when ledger/site_data.py ran)
  // ==========================================================================================================
  const HZ = window.HARNESS;
  if (!HZ) $("#harness").style.display = "none";
  if (HZ) {
    const Lg = HZ.ledger, EV = HZ.evidence, IX = HZ.index, n0 = v => (v ?? 0).toLocaleString("en");
    const STATUS = [["implemented", "built here"], ["in_progress", "being built"], ["idea", "idea"], ["v1_only", "built in the first repo"], ["rejected", "tested, rejected"]];
    const st = s => Lg.status[s] || 0;
    const toggleHz = layerToggler("harness-stage");
    const sk = name => HZ.skills.find(s => s.name === name);
    const nSkills = HZ.skills.filter(s => !/^hyperresearch/.test(s.name)).length, nHyper = HZ.skills.filter(s => /^hyperresearch-/.test(s.name)).length;
    const nPlug = Object.keys(HZ.plugins).length, nCols = Object.values(HZ.plugins).reduce((a, c) => a + c.length, 0);
    const modCls = m => m.includes("spot_features") ? "plug" : m.includes("depth_profile") ? "depth" : "tile";
    const modOf = c => Object.keys(HZ.plugins).find(m => HZ.plugins[m].includes(c)) || "";

    // a box-and-arrow diagram in one SVG: nodes {id, x, y, w, h, title, lines, cls}, edges [from, to, label, cls]
    let hzDiag = 0;
    function diagram(vb, nodes, edges, extra = "") {
      const N = Object.fromEntries(nodes.map(n => [n.id, n])), mid = `hz-arrow-${++hzDiag}`;   // one marker id per SVG
      const edge = (a, b) => {                      // centre-to-centre, clipped to both boxes
        const A = N[a], B = N[b], dx = B.x - A.x, dy = B.y - A.y;
        const cut = (n, s) => { const t = Math.min(Math.abs((n.w / 2 + 6) / (dx || 1e-9)), Math.abs((n.h / 2 + 6) / (dy || 1e-9))); return [n.x + s * dx * t, n.y + s * dy * t]; };
        return [cut(A, 1), cut(B, -1)];
      };
      const arrows = edges.map(([a, b, lab, cls]) => {
        const [[x1, y1], [x2, y2]] = edge(a, b);
        return `<path class="hz-edge ${cls || ""}" d="M${x1},${y1} L${x2},${y2}" marker-end="url(#${mid})"/>` +
          (lab ? `<text class="hz-elab" x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 6}" text-anchor="middle">${esc(lab)}</text>` : "");
      }).join("");
      const boxes = nodes.map(n => `<g class="hz-node ${n.cls || ""}"><rect x="${n.x - n.w / 2}" y="${n.y - n.h / 2}" width="${n.w}" height="${n.h}" rx="10"/>` +
        `<text x="${n.x}" y="${n.y - n.h / 2 + 24}" text-anchor="middle" class="hz-t">${esc(n.title)}</text>` +
        (n.lines || []).map((l, i) => `<text x="${n.x}" y="${n.y - n.h / 2 + 44 + i * 17}" text-anchor="middle" class="hz-l">${esc(l)}</text>`).join("") + `</g>`).join("");
      return `<svg class="hz-svg" viewBox="${vb}" preserveAspectRatio="xMidYMid meet"><defs><marker id="${mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="hz-head"/></marker></defs>${extra}${arrows}${boxes}</svg>`;
    }

    // 0 · the loop
    function renderLoop() {
      const W = 250, H = 92;
      const nodes = [
        { id: "papers", x: 165, y: 70, w: W, h: H, title: "1 · Papers", lines: [`${n0(IX.amass.papers + IX.paperclip.papers)} indexed (Amass + Paperclip)`, `${HZ.vault_notes ?? "–"} full texts in the vault`] },
        { id: "ledger", x: 500, y: 70, w: W, h: H, title: "2 · Ledger", cls: "key", lines: [`${Lg.n} ideas, ${Lg.papers} papers`, "duplicate check · DOI verified"] },
        { id: "plug", x: 835, y: 70, w: W, h: H, title: "3 · Plug-in feature", lines: ["qc/spot_features/<id>.py", `${nCols} columns from ${nPlug} modules`] },
        { id: "test", x: 835, y: 360, w: W, h: H, title: "4 · Honest test", lines: ["spot = unit, Batch_3 vs rest", "and inside imaging sessions"] },
        { id: "gxl", x: 500, y: 360, w: W, h: H, title: "5 · GXL evidence", cls: "gxl", lines: [`${EV.answers} answers from ${EV.papers} papers read`, "every quote found in its paper"] },
        { id: "qc", x: 165, y: 360, w: W, h: H, title: "6 · Verdict and sliders", lines: ["sections 05 and 06", "cited rules, signs checked"] },
        { id: "agent", x: 500, y: 215, w: 330, h: 86, title: "Claude Code agents", cls: "agent", lines: [`${nSkills} skills · hyperresearch (${nHyper} steps)`, "lit-to-ledger · build-feature · paperclip"] },
      ];
      const edges = [["papers", "ledger", "cite"], ["ledger", "plug", "claim, build"], ["plug", "test", "run"], ["test", "gxl", "ask"],
        ["gxl", "qc", "sign"], ["qc", "papers", "findings → new questions", "back"],
        ["agent", "papers", "", "spoke"], ["agent", "ledger", "", "spoke"], ["agent", "plug", "", "spoke"], ["agent", "test", "", "spoke"], ["agent", "gxl", "", "spoke"]];
      $("#hz-loop").innerHTML = diagram("0 0 1000 430", nodes, edges) +
        `<p class="note">Solid arrows: the loop every feature goes through. Dotted: what the agents drive. The agents only ever write their own plug-in file and their own ledger entry; everything downstream (table, verdict, sliders, this page) picks the new columns up by itself.</p>`;
    }

    // 1 · sources, cheapest first, and the funnel from indexed to read
    function renderSources() {
      const rows = [
        { k: "Amass index", s: "local JSON, offline", n: IX.amass.papers, sub: `${IX.amass.searches} searches · ${n0(IX.amass.tiers.core)} core battery papers`, use: "first look: does a paper on this idea exist, is it already cited", cost: "free" },
        { k: "GXL Paperclip index", s: "same searches, PMC + arXiv", n: IX.paperclip.papers, sub: `${IX.paperclip.searches} searches · ${n0(IX.paperclip.tiers.core)} core`, use: "full text: methods, exact numbers, matched passages", cost: "hackathon credits" },
        { k: "hyperresearch vault", s: "fetched full texts, kept for reuse", n: HZ.vault_notes || 0, sub: "deep reviews on request only", use: "a source read once is searchable for every later agent", cost: "agent tokens" },
        { k: "OpenAlex → Crossref", s: "live API", n: null, sub: "J. Power Sources, JES, Electrochim. Acta", use: "the paywalled journals the other two barely hold; every DOI is looked up here", cost: "free" },
      ];
      const mx = Math.max(...rows.map(r => r.n || 0));
      const funnel = [["indexed", IX.amass.papers + IX.paperclip.papers, "Amass + Paperclip, two overlapping indexes"],
        ["read in full by GXL", EV.papers, `${EV.answers} answers kept, ${EV.dropped} dropped: quote not in the paper`],
        ["cited in the ledger", Lg.papers, `${Lg.verified} DOIs verified in OpenAlex / Crossref`]].sort((a, b) => b[1] - a[1]);
      const fx = v => Math.max(4, 100 * Math.log10(1 + v) / Math.log10(1 + funnel[0][1]));
      $("#hz-sources").innerHTML =
        `<h4>Where the agents look, cheapest first</h4><div class="bars">` + rows.map(r =>
          `<div class="brow"><span class="bl"><b>${r.k}</b><small>${r.s} · ${r.cost}</small></span>` +
          `<span class="bt">${r.n ? `<i style="--w:${100 * r.n / mx}%"></i>` : ""}</span><span class="bv num">${r.n ? n0(r.n) : "live"}<small>${esc(r.sub)}</small></span></div>` +
          `<p class="note hz-use">${esc(r.use)}</p>`).join("") + `</div>` +
        `<h4>From indexed to read (log scale)</h4><div class="hz-funnel">` + funnel.map(([k, v, s]) =>
          `<div class="hz-frow"><span class="bl"><b>${k}</b><small>${esc(s)}</small></span><span class="hz-fbar"><i style="--w:${fx(v)}%"></i></span><span class="bv num">${n0(v)}</span></div>`).join("") + `</div>` +
        `<p class="note">Ledger references by the tool that found them: ${Object.entries(Lg.ref_sources).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k === "team" ? "team / first-repo research report" : k} ${v}`).join(" · ")}.</p>`;
    }

    // 2 · the ledger: one YAML file per idea
    let hzSel = HZ.chain[1];
    function renderLedger() {
      const total = Lg.n;
      const bar = `<div class="hz-stack">${STATUS.map(([s, lab]) => st(s) ? `<i class="hz-${s}" style="--w:${100 * st(s) / total}%" title="${lab}: ${st(s)}"><span>${st(s)}</span></i>` : "").join("")}</div>` +
        `<div class="legend">${STATUS.map(([s, lab]) => `<span><i class="hz-sw hz-${s}"></i>${lab} ${st(s)}</span>`).join("")}</div>`;
      const chips = STATUS.map(([s, lab]) => {
        const es = Lg.entries.filter(e => e.status === s);
        return es.length ? `<div class="hz-group"><small>${lab}</small>${es.map(e => `<button type="button" class="hz-chip hz-${s} ${e.id === hzSel ? "sel" : ""}" data-id="${e.id}" title="${esc(e.name)}">${esc(e.id.replace(/_/g, " "))}</button>`).join("")}</div>` : "";
      }).join("");
      const e = Lg.entries.find(x => x.id === hzSel) || Lg.entries[0];
      const detail = `<div class="tcard hz-detail"><p class="who">${esc(e.family || "")} · ${esc(e.status)}${e.owner ? " · " + esc(e.owner) : ""}</p><h4>${esc(e.name)}</h4>` +
        (e.implemented_in ? `<p class="q"><code>${esc(e.implemented_in)}</code>${e.columns.length ? " → " + e.columns.map(flab).map(esc).join(", ") : ""}</p>` : "") +
        (e.relevance ? `<p class="q"><b>Why it matters:</b> ${esc(e.relevance)}</p>` : "") +
        (e.findings ? `<p class="q"><b>Findings:</b> ${esc(e.findings)}${e.findings.length >= 600 ? "…" : ""}</p>` : "") +
        `<p class="note">${e.n_refs} paper${e.n_refs === 1 ? "" : "s"}${e.sources.length ? " · found via " + e.sources.join(", ") : ""}</p></div>`;
      $("#hz-ledger").innerHTML = `<h4>${total} ideas, every one with its papers and its result</h4>${bar}<div class="hz-ledger-grid"><div class="hz-chips">${chips}</div>${detail}</div>` +
        `<p class="note">Before anything is added, <code>ledger.py check</code> compares it with every entry and built column (words, synonyms and character n-grams) and exits with an error on a likely duplicate. <code>normalize</code> looks every DOI up in OpenAlex, then Crossref, and flags any it cannot find. Rejected ideas stay, so nobody tests them twice. Click an idea.</p>`;
      $$("#hz-ledger .hz-chip").forEach(b => b.addEventListener("click", () => { hzSel = b.dataset.id; renderLedger(); }));
    }

    // 3 · the worked example: from a black-box direction to a named, cited feature
    function renderChain() {
      const ent = id => Lg.entries.find(e => e.id === id) || {};
      const ev = (c, o) => ((EV.by_concept[c] || {}).pairs || {})[o];
      const evTxt = (c, o) => { const p = ev(c, o); return p ? `${p.n} papers read · ${p.consensus === "more" ? "higher → MORE" : p.consensus === "less" ? "higher → LESS" : p.consensus}` : "not asked"; };
      const test = c => HZ.tests.find(t => t.column === c);
      const tTxt = c => { const t = test(c); return t ? `B3 vs rest AUC ${fmt(t.auc3)} (p ${fmt(t.p3, 3)}) · inside sessions ${t.within} (p ${fmt(t.p_within, 3)})` : "not computed here"; };
      const node = (k, h, p, cls = "") => `<div class="hz-cnode ${cls}"><p class="who">${k}</p><h4>${esc(h)}</h4><p class="q">${p}</p></div>`;
      const arrow = l => `<div class="hz-carrow"><span>${esc(l)}</span>→</div>`;
      const rows = [
        [node("black box", "DINOv2-L patch tokens, BSE", "a frozen vision model (never saw an electrode) separates Batch_3 from the rest without labels; its direction is split exactly into per-patch scores"),
          arrow("sparse autoencoder"),
          node("one latent", "latent 715: thin slivers, flake tips", "2,048 sparse features; this one fires on thin solid poking into pores, AUC ≈ 0.99 for Batch_3, family-wise p < 0.001"),
          arrow("name it"),
          node("hand-crafted", flab("thin_solid_frac"), `<code>thin_solid_frac</code>: distance to pore, max-filtered, < 0.5 µm. ${tTxt("thin_solid_frac")}`),
          arrow("ask GXL"),
          node("GXL evidence", "thin ligaments → charging speed", `${evTxt("thin_ligaments", "charge_speed")}; first-charge loss: ${evTxt("thin_ligaments", "first_charge_loss")}`, "gxl"),
          arrow("rule"),
          node("slider", "charging speed + first-charge loss", "rule sign from the papers; split evidence → low confidence", "qc")],
        [node("black box", "the same direction, by depth", "profiled from the bottom edge (current collector) upwards: strongest in the bottom 11 µm"),
          arrow("measure"),
          node("hand-crafted", flab("depth_interface_b0_per_um"), `${tTxt("depth_interface_b0_per_um")}`),
          arrow("slope"),
          node("hand-crafted", flab("depth_interface_slope_per_10um"), `${tTxt("depth_interface_slope_per_10um")}: Batch_1/2 denser towards the current collector, Batch_3 flat`),
          arrow("ask GXL"),
          node("GXL evidence", "porosity at the current collector → charging", evTxt("current_collector_porosity", "charge_speed"), "gxl"),
          arrow("rule"),
          node("slider", "charging speed", "the papers agree with the rule's sign", "qc")],
      ];
      $("#hz-chain").innerHTML = `<h4>Worked example: making a black-box signal explainable</h4>` + rows.map(r => `<div class="hz-crow">${r.join("")}</div>`).join("") +
        `<p class="note">Every step is a file: <code>analysis/interp/</code> in the first repo (embeddings, autoencoder), <code>qc/depth_profile.py</code> (the hand-crafted columns), <code>literature/evidence.json</code> (the papers), <code>qc/impact_rules.yaml</code> (the rule). The ledger entries ${HZ.chain.map(c => `<code>${c}</code>`).join(", ")} hold the numbers and papers. Honest result: the bottom-band columns separate across spots but not inside sessions, and the thin-solid fraction keeps only its within-session sign on this recipe.</p>`;
    }

    // 4 · the same tests for every built column
    let hzCol = null;
    function renderTests() {
      const T = HZ.tests;
      if (!T.length) { $("#hz-tests").innerHTML = `<p class="note">No features table yet: run qc/features_table.py, then ledger/site_data.py.</p>`; return; }
      const W = 620, H = 330, X = a => 50 + (W - 70) * a, Y = p => H - 36 - (H - 60) * Math.min(2, -Math.log10(Math.max(p, 1e-3))) / 2;
      const grid = [0, 0.25, 0.5, 0.75, 1].map(a => `<line class="hz-grid" x1="${X(a)}" x2="${X(a)}" y1="${Y(1)}" y2="${Y(0.01)}"/><text class="hz-ax" x="${X(a)}" y="${H - 16}" text-anchor="middle">${a}</text>`).join("") +
        [1, 0.1, 0.01].map(p => `<line class="hz-grid ${p === 0.1 ? "cut" : ""}" x1="${X(0)}" x2="${X(1)}" y1="${Y(p)}" y2="${Y(p)}"/><text class="hz-ax" x="${X(0) - 6}" y="${Y(p) + 4}" text-anchor="end">${p}</text>`).join("");
      const pts = T.map((t, i) => `<circle class="hz-pt ${modCls(modOf(t.column))} ${t.column === hzCol ? "sel" : ""} ${t.p3 < 0.05 ? "sig" : ""}" data-i="${i}" cx="${X(t.auc3)}" cy="${Y(t.p_within)}" r="${t.p3 < 0.05 ? 7 : 5}"><title>${esc(flab(t.column))}: AUC ${fmt(t.auc3)} (p ${fmt(t.p3, 3)}), inside sessions ${t.within} p ${fmt(t.p_within, 3)}</title></circle>`).join("");
      const svg = `<svg class="hz-svg hz-scatter" viewBox="0 0 ${W} ${H}">${grid}` +
        `<text class="hz-ax" x="${X(0.5)}" y="${H - 1}" text-anchor="middle">Batch_3 vs rest, AUC across spots (0.5 = no difference)</text>` +
        `<text class="hz-ax" transform="translate(12 ${Y(0.1)}) rotate(-90)" text-anchor="middle">inside sessions, p (log)</text>` +
        `<text class="hz-q" x="${X(0.98)}" y="${Y(0.012)}" text-anchor="end">holds inside sessions</text>` +
        `<text class="hz-q" x="${X(0.98)}" y="${Y(0.9)}" text-anchor="end">separates, but so do the sessions</text>${pts}</svg>`;
      const t = T.find(x => x.column === hzCol) || [...T].sort((a, b) => a.p_within - b.p_within)[0];
      hzCol = t.column;
      const best12 = [...T].sort((a, b) => a.p12 - b.p12)[0];
      $("#hz-tests").innerHTML = `<h4>${T.length} built columns, one scorecard</h4><div class="hz-test-grid">${svg}<div class="tcard"><p class="who">${esc(modOf(t.column))}</p><h4>${esc(flab(t.column))}</h4>` +
        `<dl class="stats"><dt>Batch_1 / 2 / 3 mean</dt><dd>${["Batch_1", "Batch_2", "Batch_3"].map(b => fmt(t.means[b], 3)).join(" / ")}</dd>` +
        `<dt>Batch_3 vs rest AUC</dt><dd>${fmt(t.auc3)} <small>p ${fmt(t.p3, 3)}</small></dd><dt>inside sessions, B3 − rest</dt><dd>${t.within} <small>p ${fmt(t.p_within, 3)}</small></dd>` +
        `<dt>Batch_1 vs Batch_2 AUC</dt><dd>${fmt(t.auc12)} <small>p ${fmt(t.p12, 3)}</small></dd></dl>` +
        `<p class="note">Click a dot. Big dots: p < 0.05 across spots. Colour: <span class="hz-k tile">tile features</span> <span class="hz-k depth">full-height depth</span> <span class="hz-k plug">plug-ins</span></p></div></div>` +
        `<p class="note">Masks: ${HZ.masks === "seg3" ? "seg3 (multi-detector segmentation)" : "the BSE-threshold recipe (harmonise); the seg3 masks are the newer default"}. The spot is the unit (31 spots, never tiles). Across spots the labels are shuffled freely; inside sessions only between spots of the same imaging session, so the session cannot be the cue. ${T.length} columns were tried, so a single p near 0.05 is expected by chance: read the pattern, not one dot. Batch_1 vs Batch_2: the best of ${T.length} is p ${fmt(best12.p12, 3)} (${esc(flab(best12.column))}), about what chance gives.</p>`;
      $$("#hz-tests .hz-pt").forEach(c => c.addEventListener("click", () => { hzCol = T[+c.dataset.i].column; renderTests(); }));
    }

    // 5 · many agents at once, and what stops them producing slop
    function renderAgents() {
      const plugs = Object.entries(HZ.plugins);
      const nodes = [
        ...["A", "B", "C"].map((a, i) => ({ id: "s" + i, x: 110, y: 70 + i * 120, w: 190, h: 70, title: `agent session ${a}`, cls: "agent", lines: ["owns one plug-in", "and one ledger entry"] })),
        ...plugs.filter(([m]) => m.includes("spot_features")).slice(0, 3).map(([m, c], i) => ({ id: "p" + i, x: 390, y: 70 + i * 120, w: 270, h: 70, title: m.replace("qc/spot_features/", ""), lines: [`${c.length} columns`] })),
        { id: "run", x: 640, y: 190, w: 150, h: 70, title: "run.py", lines: ["every spot, + test"] },
        { id: "table", x: 860, y: 70, w: 210, h: 70, title: "features table", lines: ["merges every plug-in"] },
        { id: "verdict", x: 860, y: 190, w: 210, h: 70, title: "verdict · sliders", lines: ["sections 05, 06"] },
        { id: "rep", x: 860, y: 310, w: 210, h: 70, title: "ledger report · page", lines: ["section 09"] },
      ];
      const pn = nodes.filter(n => n.id.startsWith("p")).length;
      const edges = [...Array(Math.min(3, pn)).keys()].flatMap(i => [["s" + i, "p" + i], ["p" + i, "run"]]).concat([["run", "table"], ["table", "verdict"], ["table", "rep"]]);
      const gates = [
        ["Duplicate check", "ledger.py check exits 1 on a likely duplicate; the agent must extend the old entry instead", `${Lg.n} ideas, one file each`],
        ["Verified DOIs", "every DOI is looked up in OpenAlex then Crossref; the agent may only use DOIs a tool printed", `${Lg.verified} of ${Lg.papers} verified`],
        ["Verified quotes", "a GXL answer counts only if five consecutive words of its quote are found in the paper", `${EV.dropped} answers dropped, ${EV.answers} kept`],
        ["Honest statistics", "spot = unit; Batch_3 vs rest and inside imaging sessions; correct for how many were tried", `${HZ.tests.length} columns, one scorecard`],
        ["Negative results kept", "a rejected idea stays in the ledger with its numbers", `${st("rejected")} rejected, still listed`],
        ["Frozen decision layer", "agents add diagnostics; the tier-1 rule of section 05 was frozen before any of this", "no agent reaches a verdict"],
      ];
      $("#hz-agents").innerHTML = `<h4>Several agents at once, without stepping on each other</h4>` +
        diagram("0 0 1000 380", nodes, edges) +
        `<h4>What keeps it honest</h4><div class="hz-gates">${gates.map(([h, p, s]) => `<div class="tcard"><h4>${h}</h4><p class="q">${p}</p><span class="hz-gs num">${s}</span></div>`).join("")}</div>`;
    }

    const R9 = [renderLoop, renderSources, renderLedger, renderChain, renderTests, renderAgents];
    let hzStep = -1;
    $("#harness-stats").innerHTML = [["ideas in the ledger", Lg.n], ["papers cited (DOI-verified)", `${Lg.papers} (${Lg.verified})`],
      ["papers indexed", n0(IX.amass.papers + IX.paperclip.papers)], ["GXL answers kept", `${EV.answers} from ${EV.papers} papers`],
      ["feature columns built", `${nCols} in ${nPlug} modules`], ["agent skills", `${nSkills} + hyperresearch`]].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
    register("harness", {
      starts: [0, 0.17, 0.34, 0.5, 0.67, 0.84],
      steps: [
        { k: "The loop", h: "One loop for every idea",
          p: `Claude Code agents with project skills run the same six steps for every feature idea: find papers, record the idea in the ledger, build it as a plug-in, test it the same honest way, ask GXL's paper reader what it does to a battery, and feed the result back. A person decides what to try; the files decide what counts.`,
          stat: `${Lg.n} ideas · ${st("implemented")} built here · ${st("rejected")} rejected` },
        { k: "Sources", h: "Papers, cheapest first",
          p: `The agent starts with the local Amass and Paperclip indexes (free, offline, ${n0(IX.amass.papers + IX.paperclip.papers)} papers), opens full text through GXL Paperclip only when an abstract does not say how to measure a feature, and keeps what it fetched in the hyperresearch vault. Every DOI is checked against OpenAlex and Crossref.`,
          stat: `${n0(IX.amass.papers + IX.paperclip.papers)} indexed → ${Lg.papers} cited → ${EV.papers} read in full` },
        { k: "Ledger", h: "One file per idea, papers attached",
          p: `Each idea is a YAML file: what it measures, why it should matter for the battery, the papers behind it, who is building it, and what it did on our data. LEDGER.md is generated from these files. Ideas built in the first repo are kept as port candidates with their old numbers.`,
          stat: `${Lg.verified} of ${Lg.papers} DOIs verified` },
        { k: "Explain", h: "From a black box to a named feature",
          p: `The CNN and DINOv2 can separate Batch_3, but cannot say why. A sparse autoencoder splits the embedding into features one can look at; the clearest becomes a hand-crafted measurement; GXL's reader says what that measurement does to a battery; the slider uses the papers' sign.`,
          stat: "embedding → latent → named column → papers → rule" },
        { k: "Tests", h: "The same scorecard for every column",
          p: `A new column gets no special treatment: Batch_3 against the rest across spots, then again inside imaging sessions where the microscope cannot be the cue, and Batch_1 against Batch_2. Most columns separate across spots and fail inside sessions; the page shows them all.`,
          stat: `${HZ.tests.length} columns · ${HZ.tests.filter(t => t.p_within < 0.1).length} with inside-session p < 0.1 · ${HZ.masks || "harmonise"} masks` },
        { k: "Agents", h: "Parallel agents, guarded",
          p: `A new feature is one plug-in file, so several agent sessions work at once without touching each other's files. Six gates decide what reaches the page: the duplicate check, verified DOIs, verified quotes, the same statistics, kept negatives, and a decision rule no agent can change.`,
          stat: `${nPlug - 2} plug-ins · ${HZ.skills.length} skills · built ${esc(HZ.built)}` },
      ],
      update: (p, step) => {
        if (step === hzStep) return;
        hzStep = step;
        toggleHz(step);
        R9[step]();
      },
    });
    renderLoop();
    extraNodes.push({ label: "Research harness", line: "papers → ledger → plug-in → tests → GXL evidence", sec: "harness", steps: [0, 1, 2, 3, 4, 5] });
    extraThumbs.push(thumbCanvas(ctx => {
      const pts = [[20, 14], [64, 10], [108, 14], [108, 58], [64, 62], [20, 58]];
      ctx.strokeStyle = "#3cc7b0"; ctx.lineWidth = 2; ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath(); ctx.stroke();
      pts.forEach(([x, y], i) => { ctx.fillStyle = i === 1 ? "#3cc7b0" : i === 4 ? "#ffc22e" : "#888"; ctx.fillRect(x - 9, y - 6, 18, 12); });
      ctx.fillStyle = "#8f98ff"; ctx.fillRect(50, 30, 28, 12);
    }));
  }

  // ==========================================================================================================
  // the pipeline map (top bar + hero overview)
  // ==========================================================================================================
  // One node per stage. A node may span more than one section (Prediction = 04 models + 05 verdict,
  // Interpretation = 07 why + 08 literature): `parts` lists the (section, steps) pairs it covers. The
  // register() blocks still carry a `line` per node; the overview shows labels only.
  const stageNodes = [
    ...firstNodes.map((n, i) => ({ ...n, thumb: firstThumbs[i] })),
    { label: "Preprocessing", sec: "prep", steps: [0, 1, 2, 3, 4, 5, 6], thumb: win.img.bse },
    { label: "Embedding", sec: "kernel", steps: [0, 1, 2], thumb: kOff[DETS[0]].fmap.toDataURL() },
    ...(matrixThumb ? [{ label: "Contrastive learning", sec: "match", steps: [0, 1, 2], thumb: matrixThumb() }] : []),
    ...extraNodes.map((n, i) => ({ ...n, thumb: extraThumbs[i] })),
  ];
  const MERGE = { Models: "Prediction", Verdict: "Prediction", Why: "Interpretation", "Embedding map": "Interpretation", "Production literature": "Interpretation" };
  const NODES = [];
  stageNodes.forEach(n => {
    const label = MERGE[n.label] || n.label;
    let node = NODES.find(m => m.label === label);
    if (!node) NODES.push(node = { label, thumb: n.thumb, parts: [] });
    node.parts.push({ sec: n.sec, steps: n.steps });
  });
  const nodeOf = sec => NODES.findIndex(n => n.parts.some(q => q.sec === sec.id && q.steps.includes(sec.step)));
  document.documentElement.style.setProperty("--n-nodes", NODES.length);
  $("#pipemap").innerHTML = NODES.map(n =>
    `<li><button type="button" title="${n.label}"><img src="${n.thumb}" alt=""><span class="lbl">${n.label}</span></button></li>`).join("");
  $("#overview").innerHTML = NODES.map(n =>
    `<li><button type="button"><img src="${n.thumb}" alt=""><b>${n.label}</b></button></li>`).join("");
  const jumpTo = n => goToStep(sections.find(s => s.id === n.parts[0].sec), n.parts[0].steps[0]);
  $$("#pipemap button").forEach((b, i) => b.addEventListener("click", () => jumpTo(NODES[i])));
  $$("#overview button").forEach((b, i) => b.addEventListener("click", () => jumpTo(NODES[i])));
  const mapItems = $$("#pipemap li");

  function updateMap(current) {
    const after = !current && window.scrollY >= sections[sections.length - 1].el.offsetTop;
    const idx = current ? nodeOf(current) : after ? NODES.length : -1;
    mapItems.forEach((li, i) => { li.classList.toggle("on", i === idx); li.classList.toggle("done", i < idx); });
    $("#pipe-now").textContent = current && NODES[idx] ? `${NODES[idx].label} · step ${current.step + 1} of ${current.steps.length}` : "";
  }

  // ==========================================================================================================
  // scroll engine
  // ==========================================================================================================
  $("#built").textContent = `Built ${D.built} from ${S.batch}/${S.sample_id} and CNN run “${run.name}”${run.checkpoint ? ` (${run.checkpoint})` : ""}.`;
  let current = null;                                     // the section under the middle of the viewport
  function frame() {
    const vh = window.innerHeight, y = window.scrollY;
    const docH = document.documentElement.scrollHeight - vh;
    $("#progress").style.width = (100 * clamp(y / (docH || 1))) + "%";
    current = null;
    sections.forEach(sec => {
      const top = sec.el.offsetTop, span = sec.el.offsetHeight - vh;
      const p = clamp((y - top) / (span || 1));
      if (y + vh / 2 >= top && y + vh / 2 < top + sec.el.offsetHeight) current = sec;
      if (p !== sec.p && y + vh > top - vh && y < top + sec.el.offsetHeight + vh) {
        sec.p = p;
        const k = stepOf(sec, p);
        setStep(sec, k);
        sec.update(p, k);
      }
    });
    updateMap(current);
    if (target && Math.abs(y - yAt(target.sec, restP(target.sec, target.k))) < 2) target = null;   // arrived
  }
  let queued = false;
  const request = () => { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; frame(); }); } };
  function relayout() {
    sections.forEach(sec => {
      if (sec.layout) sec.layout();
      const p = sec.p ?? 0, k = stepOf(sec, p);
      setStep(sec, k);
      sec.update(p, k);
    });
    frame();
  }
  window.addEventListener("scroll", request, { passive: true });
  window.addEventListener("resize", () => requestAnimationFrame(relayout));
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", relayout);
  window.addEventListener("load", relayout);              // images change the stage layout once loaded

  // keyboard: → / space next step, ← previous (from the hero: into the first section)
  window.addEventListener("keydown", e => {
    if (e.altKey || e.ctrlKey || e.metaKey || e.target.closest("input, textarea, select")) return;
    const next = e.key === "ArrowRight" || (e.key === " " && !e.target.closest("button, a"));
    const prev = e.key === "ArrowLeft";
    if (!next && !prev) return;
    e.preventDefault();
    stopPlay();
    const base = target || (current && { sec: current, k: current.step });
    if (base) return goToStep(base.sec, base.k + (next ? 1 : -1));
    const lastSec = sections[sections.length - 1];
    if (window.scrollY >= lastSec.el.offsetTop) { if (prev) goToStep(lastSec, lastSec.starts.length - 1); }
    else if (next) goToStep(sections[0], 0);
  });

  relayout();
})();
