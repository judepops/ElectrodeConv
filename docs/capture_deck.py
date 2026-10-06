"""Turn the animated judging deck (demo/index.html) into still images and GIFs for the README.

    python docs/capture_deck.py              # -> docs/figures/deck/*.png and docs/figures/*.gif
    python docs/capture_deck.py --gifs-only  # just the three animations
    python docs/capture_deck.py --stills-only

GitHub does not run the deck's JavaScript, so each slide is opened in headless Chrome and photographed. For a still
the deck is told to skip its animations and show the finished slide. For a GIF frame the page's animation clock is
frozen at a chosen time (query parameter ?t=<milliseconds>), so every frame is the deck's own drawing at that
instant, not a redraw.

Needs Google Chrome (macOS path below; set CHROME to override) and Pillow.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "demo"
OUT = REPO / "docs" / "figures"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SIZE = (1600, 900)

# Injected into a temporary copy of the deck: no CSS transitions (so a still shows the settled layout), only the
# current slide visible, and a frozen animation clock when ?t= is given.
PATCH = """<style>*,*::before,*::after{transition:none!important;animation:none!important}
.slide:not(.on){display:none!important}.slide.on{opacity:1!important}</style>
<script>(() => { const t = new URLSearchParams(location.search).get("t"), still = t === null;
  // a still wants every animation finished: tell the deck the reader prefers reduced motion. A GIF frame wants it
  // running, so say the opposite, whatever this machine's own setting is.
  const mm = window.matchMedia.bind(window);
  window.matchMedia = q => /reduced-motion/.test(q) ? { matches: still, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} } : mm(q);
  if (still) return;
  window.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };   // the deck redraws finished on resize
  const T = +t; let calls = 0; performance.now = () => 0;                          // freeze the animation clock at T ms
  window.requestAnimationFrame = cb => (++calls < 400 ? setTimeout(() => cb(T), 0) : 0); })();</script></head>"""

# slide index -> (name, number of builds); the order of the <section>s in demo/index.html
SLIDES = [("title", 1), ("lanes", 1), ("preprocessing", 7), ("v1_loss", 3), ("v2_loss", 4), ("combining", 3),
          ("accuracy", 4), ("seeds", 1), ("harness", 1), ("features", 1), ("outcomes", 2)]
# animations to turn into GIFs: (file name, slide, build, milliseconds to sample, crop box or None)
ANIMATIONS = [
    ("convolution_sweep", 3, 0, [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000], None),
    ("v1_contrastive_matrix", 3, 2, [0, 300, 600, 900, 1200, 1500, 1800, 2200], None),
    ("v2_contrastive", 4, 3, [0, 400, 800, 1200, 1600, 2000, 2300, 2600], None),
]


def shot(page, target, dest, tmp):
    """One screenshot of file://page + target (e.g. '?t=3000#3.0')."""
    dest.unlink(missing_ok=True)
    profile = Path(tmp) / f"profile_{dest.stem}"
    p = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                          "--force-device-scale-factor=1", f"--user-data-dir={profile}", f"--window-size={SIZE[0]},{SIZE[1]}",
                          "--virtual-time-budget=4000", f"--screenshot={dest}", f"file://{page}{target}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):                                   # Chrome sometimes lingers after writing the file
        if dest.exists() and dest.stat().st_size > 0:
            break
        time.sleep(0.5)
    time.sleep(0.4)
    p.kill()
    shutil.rmtree(profile, ignore_errors=True)
    return dest.exists()


def main():
    gifs_only, stills_only = "--gifs-only" in sys.argv, "--stills-only" in sys.argv
    if not Path(CHROME).exists():
        sys.exit(f"Chrome not found at {CHROME}; set the CHROME environment variable")
    (OUT / "deck").mkdir(parents=True, exist_ok=True)
    page = DEMO / "_capture.html"
    page.write_text((DEMO / "index.html").read_text().replace("</head>", PATCH))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for i, (name, builds) in enumerate([] if gifs_only else SLIDES):
                for b in range(builds):
                    dest = OUT / "deck" / f"{i:02d}_{name}_{b}.png"
                    ok = shot(page, f"#{i}.{b}", dest, tmp)
                    print(("ok   " if ok else "FAIL ") + dest.name, flush=True)
            for name, slide, build, times, box in ([] if stills_only else ANIMATIONS):
                frames = []
                for t in times:
                    f = Path(tmp) / f"{name}_{t}.png"
                    if shot(page, f"?t={t}#{slide}.{build}", f, tmp):
                        im = Image.open(f).convert("RGB")
                        frames.append((im.crop(box) if box else im).resize((960, 540), Image.LANCZOS))
                if frames:
                    q = [f.quantize(colors=128, method=Image.MEDIANCUT) for f in frames]
                    q[0].save(OUT / f"{name}.gif", save_all=True, append_images=q[1:] + [q[-1]] * 4, duration=450, loop=0, optimize=True)
                    print(f"ok   {name}.gif ({len(frames)} frames)", flush=True)
    finally:
        page.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
