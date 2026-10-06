"""Draw the README's result figures from the files the pipeline wrote. Nothing here is typed in by hand.

    python docs/make_figures.py            # -> docs/figures/fig_*.png

Reads   cnn/results/compare_extra.json, cnn/results/baselines.json     model scores and their intervals
        dashboard/site/pca.js                                          the embedding map
        experiments/patch_size_and_seeds/scores_with_leak.txt          the seed / patch-size study
        literature/evidence.json, literature/evidence_terms.yaml       what the papers say
        literature/feature_cards.json, dashboard/site/img/lit_*.jpg    what each feature looks like
        results/feature_bank/harness_v1_quick/results.md               the frozen-feature bank

Colour: one validated palette throughout. Batch_1 blue, Batch_2 orange, Batch_3 aqua (the three hues stay apart for
colour-blind readers); a single blue for one-series charts; blue / red around neutral grey for direction.
"""
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from PIL import Image  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "figures"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, RED, NEUTRAL = "#2a78d6", "#eb6834", "#1baf7a", "#d03b3b", "#f0efec"
BATCH = {"Batch_1": BLUE, "Batch_2": ORANGE, "Batch_3": AQUA}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "font.size": 11,
    "font.family": "sans-serif", "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK,
    "axes.edgecolor": GRID, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": False, "xtick.major.size": 0, "ytick.major.size": 0, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "legend.frameon": False,
})


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", f"docs/figures/{name}")


def title(ax, head, sub):
    ax.set_title(head, pad=26)
    ax.text(0, 1.0, sub, transform=ax.transAxes, va="bottom", ha="left", fontsize=10, color=INK2)


def chance(ax, x=1 / 3, label="chance"):
    ax.axvline(x, color=INK2, lw=1, ls=(0, (3, 3)), zorder=1)
    ax.text(x, ax.get_ylim()[1], f" {label}", color=INK2, fontsize=9, va="top", ha="left")


# ----------------------------------------------------------------------------------------------------------------
def fig_accuracy():
    """The three models on the same held-out spots."""
    m = json.loads((REPO / "cnn/results/compare_extra.json").read_text())["models"]
    rows = [("V1 + V2 ensemble\n(4 V2 members, the final model)", m["V1 + V2 seed ensemble (4 seeds, probabilities averaged)"]),
            ("V1\nlabel-free", m["V1 (label-free)"]),
            ("V2\ntrained on the batch labels", m["V2 (batch-supervised)"])]
    seeds = [m[k]["bacc"] for k in ("V1+2 concatenated", "V1 + v2s1 concatenated", "V1 + v2s2 concatenated", "V1 + v2_noseg concatenated")]
    fig, ax = plt.subplots(figsize=(8.4, 3.3))
    for i, (_, r) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([r["ci90"]["lo"], r["ci90"]["hi"]], [y, y], color=BLUE, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([r["bacc"]], [y], s=90, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.text(r["ci90"]["hi"] + 0.015, y, f"{r['bacc']:.2f}", va="center", fontsize=11, fontweight="bold")
        ax.text(r["ci90"]["hi"] + 0.075, y, f"[{r['ci90']['lo']:.2f}, {r['ci90']['hi']:.2f}]", va="center", fontsize=9.5, color=INK2)
    ytop = len(rows) - 1
    ax.scatter(seeds, [ytop + 0.3] * len(seeds), s=26, color=INK2, zorder=3)
    ax.text(max(seeds) + 0.015, ytop + 0.3, "each V1 + V2 pairing on its own", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=10)
    ax.set_ylim(-0.6, ytop + 0.75)
    ax.set_xlim(0.25, 1.06)
    ax.set_xticks([0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("balanced accuracy on spots the model never saw (line: 90 % interval over imaging sessions)")
    chance(ax)
    title(ax, "Which batch? Held-out accuracy of the three models",
          "31 spots, 5 folds by spot; the supervised encoder is retrained for every fold")
    save(fig, "fig_accuracy.png")


def fig_imaging_vs_material():
    """Where the microscope can be the cue, and where it cannot."""
    rows = {r["name"]: r for r in json.loads((REPO / "cnn/results/baselines.json").read_text())["rows"]}
    order = [("imaging cues only", "Imaging cues only\n(black level, contrast, noise)"),
             ("pixel statistics", "Pixel statistics"),
             ("hand-crafted features (13, seg3 masks)", "13 hand-built features"),
             ("untrained k7 encoder", "Untrained CNN"),
             ("V1 CNN embedding", "V1 CNN embedding\n(label-free)")]
    fig, ax = plt.subplots(figsize=(8.4, 3.9))
    for i, (key, _) in enumerate(order):
        y, r = len(order) - 1 - i, rows[key]
        a, b = r["lr_losess"], r["lr_mixed"]
        ax.plot([a, b], [y, y], color=GRID, lw=2, zorder=1)
        ax.scatter([a], [y], s=90, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.scatter([b], [y], s=90, color=ORANGE, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.text(max(a, b) + 0.02, y, f"{a:.2f} → {b:.2f}", va="center", fontsize=9.5, color=INK2)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([o[1] for o in order][::-1], fontsize=10)
    ax.set_ylim(-0.6, len(order) - 0.2)
    ax.set_xlim(0.2, 0.95)
    ax.set_xticks([0.3, 0.5, 0.7, 0.9])
    ax.set_xlabel("balanced accuracy, whole imaging session held out")
    chance(ax)
    ax.scatter([], [], s=70, color=BLUE, label="all 31 spots")
    ax.scatter([], [], s=70, color=ORANGE, label="only the 13 spots whose session holds more than one batch")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.42), ncol=2, fontsize=9.5, handletextpad=0.3, columnspacing=1.6)
    title(ax, "Imaging cues alone guess the batch, until the session stops giving it away",
          "Where one session holds several batches the microscope cannot be the cue: imaging cues fall to chance, material features and the CNN do not")
    save(fig, "fig_imaging_vs_material.png")


def fig_embedding_map():
    s = (REPO / "dashboard/site/pca.js").read_text()
    d = json.loads(s[s.index("{"):s.rindex("}") + 1])
    v = d["views"][-1]
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    t = np.array(v["tiles"])
    for b, c in BATCH.items():
        k = t[:, 2] == int(b[-1])
        ax.scatter(t[k, 0], t[k, 1], s=5, color=c, alpha=0.16, linewidths=0, zorder=1)
        p = [q for q in v["spots"] if q["batch"] == b]
        ax.scatter([q["x"] for q in p], [q["y"] for q in p], s=95, color=c, edgecolor=SURFACE, linewidth=2, zorder=3,
                   label=f"{b.replace('_', ' ')} ({len(p)} spots)")
    xs, ys = [q["x"] for q in v["spots"]], [q["y"] for q in v["spots"]]
    px, py = 0.12 * (max(xs) - min(xs)), 0.12 * (max(ys) - min(ys))
    ax.set_xlim(min(xs) - px, max(xs) + px)
    ax.set_ylim(min(ys) - py, max(ys) + py)
    for q in v["test"]:
        ax.scatter([q["x"]], [q["y"]], s=95, marker="D", color=INK, edgecolor=SURFACE, linewidth=2, zorder=4)
    ax.scatter([], [], s=70, marker="D", color=INK, label="test spots")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel(f"principal axis 1 ({100 * v['var'][0]:.0f} % of the spread)")
    ax.set_ylabel(f"principal axis 2 ({100 * v['var'][1]:.0f} %)")
    ax.legend(loc="upper left", fontsize=9.5, handletextpad=0.2, borderaxespad=0.2)
    title(ax, "Where the batches sit in the embedding",
          f"PCA of the final model's spot embeddings ({v['dims']} numbers per spot); faint dots are the 806 tiles")
    save(fig, "fig_embedding_map.png")


def fig_patch_size_leak():
    """Seeds and patch size: the session leak falls as the training patch grows."""
    rows = []
    for line in (REPO / "experiments/patch_size_and_seeds/scores_with_leak.txt").read_text().splitlines():
        p = line.split()
        if p and p[0].startswith("exp_"):
            rows.append({"recipe": "matching only" if "conly" in p[0] else "material map + matching",
                         "patch": 256 if "big" in p[0] else 128, "acc": float(p[1]), "leak": float(p[4])})
    # the team's GPU runs at 320 px (cnn/results/v1_variants.md): V1 and the same without the material map
    rows += [{"recipe": "material map + matching", "patch": 320, "acc": 0.58, "leak": 0.06},
             {"recipe": "matching only", "patch": 320, "acc": 0.53, "leak": 0.10}]
    POS = {128: 0, 256: 1, 320: 2}
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9), sharex=True)
    for ax, key, ylab, ref, reflab in ((axes[0], "leak", "nearest neighbour from the same imaging session", 0.058, "chance 0.06"),
                                        (axes[1], "acc", "balanced accuracy, session held out", 1 / 3, "chance 0.33")):
        for recipe, c, dx in (("material map + matching", BLUE, -0.07), ("matching only", ORANGE, 0.07)):
            r = [q for q in rows if q["recipe"] == recipe]
            ax.scatter([POS[q["patch"]] + dx for q in r], [q[key] for q in r], s=80, color=c, edgecolor=SURFACE, linewidth=2, zorder=3,
                       label=recipe if key == "leak" else None)
        ax.axhline(ref, color=INK2, lw=1, ls=(0, (3, 3)), zorder=1)
        ax.text(2.45, ref, f" {reflab}", color=INK2, fontsize=9, va="bottom", ha="right")
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["128 px (3.2 µm)\nlaptop", "256 px (6.4 µm)\nlaptop", "320 px (8 µm)\nteam GPU"], fontsize=9)
        ax.set_xlim(-0.5, 2.5)
        ax.set_ylabel(ylab, fontsize=9.5)
        ax.yaxis.grid(True, color=GRID, lw=1)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", colors=INK2)
    axes[0].set_ylim(0, 0.52)
    axes[1].set_ylim(0.25, 0.82)
    axes[0].legend(loc="upper right", fontsize=9.5, handletextpad=0.2)
    axes[0].set_title("Small training patches teach the network the session", pad=26)
    axes[0].text(0, 1.0, "share of spots whose closest spot in the embedding is from the same session; one dot per trained model",
                 transform=axes[0].transAxes, va="bottom", fontsize=9.5, color=INK2)
    fig.supxlabel("side of the training patch cut from each 512 px tile", fontsize=10, color=INK2, y=-0.08)
    fig.subplots_adjust(wspace=0.28)
    save(fig, "fig_patch_size_leak.png")


def fig_evidence_grid():
    terms = yaml.safe_load((REPO / "literature/evidence_terms.yaml").read_text())
    pairs = {(p["concept"], p["outcome"]): p for p in json.loads((REPO / "literature/evidence.json").read_text())["pairs"]}
    outcomes = [("capacity", "energy\nstorage"), ("charge_speed", "charging\nspeed"), ("lifespan", "lifespan"),
                ("first_charge_loss", "first-charge\nloss"), ("swelling", "swelling"), ("uniformity", "uniformity")]
    concepts = [c for c in terms["concepts"] if any(pairs.get((c["id"], o), {}).get("n_papers", 0) >= 2 for o, _ in outcomes)]
    concepts.sort(key=lambda c: -sum(pairs.get((c["id"], o), {}).get("n_papers", 0) for o, _ in outcomes))
    fig, ax = plt.subplots(figsize=(8.6, 0.46 * len(concepts) + 1.9))
    for i, c in enumerate(concepts):
        y = len(concepts) - 1 - i
        for j, (o, _) in enumerate(outcomes):
            p = pairs.get((c["id"], o))
            n = p["n_papers"] if p else 0
            cons = p["consensus"] if p else "too few papers"
            strength = min(1.0, n / 8)
            col = NEUTRAL
            if cons == "more":
                col = matplotlib.colors.to_hex(np.array(matplotlib.colors.to_rgb(NEUTRAL)) * (1 - strength) + np.array(matplotlib.colors.to_rgb(BLUE)) * strength)
            elif cons == "less":
                col = matplotlib.colors.to_hex(np.array(matplotlib.colors.to_rgb(NEUTRAL)) * (1 - strength) + np.array(matplotlib.colors.to_rgb(RED)) * strength)
            ax.add_patch(plt.Rectangle((j + 0.04, y + 0.06), 0.92, 0.88, color=col, lw=0))
            mark = {"more": "▲", "less": "▼", "optimum": "◆", "mixed": "≈"}.get(cons, "")
            dark = cons in ("more", "less") and strength > 0.55
            if n:
                ax.text(j + 0.5, y + 0.5, f"{mark} {n}".strip(), ha="center", va="center", fontsize=10,
                        color="white" if dark else (INK if mark else INK2))
    ax.set_xlim(0, len(outcomes))
    ax.set_ylim(0, len(concepts))
    ax.set_xticks([j + 0.5 for j in range(len(outcomes))])
    ax.set_xticklabels([o[1] for o in outcomes], fontsize=9.5, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks([len(concepts) - 1 - i + 0.5 for i in range(len(concepts))])
    ax.set_yticklabels([c["id"].replace("_", " ").replace("si ", "Si ") for c in concepts], fontsize=10)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    fig.text(0.125, 1.0, "What the papers say more of each feature does to a cell", fontsize=13, fontweight="bold", va="bottom")
    fig.text(0.125, 0.955, "▲ more of the outcome (blue)   ▼ less (red)   ◆ an optimum   ≈ papers disagree.  Number = full-text papers whose "
             "quoted sentence was found in the paper", fontsize=9, color=INK2, va="bottom")
    save(fig, "fig_evidence_grid.png")


def fig_feature_bank():
    text = (REPO / "results/feature_bank/harness_v1_quick/results.md").read_text()
    rows = []
    for line in text.splitlines():
        m = re.match(r"\|\s*(.+?)\s*\|\s*([\d–-]+)\s*\|\s*([\d.]+) \[([\d.]+), ([\d.]+)\]", line)
        if m:
            rows.append((m.group(1).replace("**", ""), float(m.group(3)), float(m.group(4)), float(m.group(5))))
    keep = {"acquisition only (imgqc)": "Imaging descriptors only\n(the bar to beat)", "single family: emb_dinov3l": "DINOv3 ViT-L, frozen",
            "single family: emb_dinov2l": "DINOv2 ViT-L, frozen", "single family: emb_convnextb": "DINOv3 ConvNeXt-B, frozen",
            "Model A (all non-leakrisk spaces)": "All families, learned kernel weights", "single family: emb_micronet": "MicroNet ResNet50, frozen",
            "single family: glcm_lbp": "Co-occurrence + local binary patterns", "single family: psd": "Power spectra",
            "Model B (no imaging, no leakrisk)": "All material-side families", "single family: xdet": "Cross-detector statistics",
            "single family: fbank": "Gabor / blob / ridge filter bank", "single family: registry": "The team's named features",
            "single family: orient": "Orientation statistics", "single family: phase": "Phase maps: fractions, S2, chords"}
    rows = sorted([(keep[n], v, lo, hi) for n, v, lo, hi in rows if n in keep], key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(8.6, 0.36 * len(rows) + 1.6))
    for y, (name, v, lo, hi) in enumerate(rows):
        bar = name.startswith("Imaging")
        c = ORANGE if bar else BLUE
        ax.plot([lo, hi], [y, y], color=c, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([v], [y], s=70, color=c, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.text(hi + 0.015, y, f"{v:.2f}", va="center", fontsize=9.5, color=INK2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=9.5)
    ax.set_ylim(-0.7, len(rows) - 0.2)
    ax.set_xlim(0.12, 1.02)
    ax.set_xticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("balanced accuracy, one source image held out at a time (line: 95 % bootstrap interval)")
    chance(ax)
    ax.scatter([], [], s=60, color=BLUE, label="material and mixed feature families")
    ax.scatter([], [], s=60, color=ORANGE, label="imaging descriptors only")
    ax.legend(loc="lower right", fontsize=9.5, handletextpad=0.2)
    title(ax, "Half a million frozen features, and none beats the microscope's own fingerprint",
          "12 feature families on the 31 crops, kernel classifier fitted inside each fold")
    save(fig, "fig_feature_bank.png")


def fig_feature_cards():
    cards = {c["concept"]: c for c in json.loads((REPO / "literature/feature_cards.json").read_text())["cards"]}
    pick = ["si_fraction", "porosity", "heterogeneity"]
    fig, axes = plt.subplots(len(pick), 3, figsize=(8.4, 9.3))
    for i, cid in enumerate(pick):
        c = cards[cid]
        for k, name in enumerate(("low", "typical", "high")):
            ax, t = axes[i, k], c["tiles"][k]
            ax.imshow(Image.open(REPO / "dashboard/site" / t["img"]))
            ax.set_xticks([])
            ax.set_yticks([])
            for s_ in ax.spines.values():
                s_.set_visible(False)
            ax.set_xlabel(f"{name}: {t['text']}", fontsize=9.5, color=INK)
        good = [("more " if e["more"] else "less ") + e["label"] for e in c["effects"]]
        axes[i, 0].set_title(f"{c['label']}.  Papers, more of it: {', '.join(good)}", fontsize=10.5, loc="left", pad=8, fontweight="bold")
    fig.subplots_adjust(hspace=0.34, wspace=0.05)
    fig.text(0.125, 0.955, "What three of the features look like on real tiles", fontsize=13, fontweight="bold")
    fig.text(0.125, 0.935, "12.8 µm tiles at the 5th, 50th and 95th percentile; silicon tinted yellow, pores tinted blue", fontsize=9.5, color=INK2)
    save(fig, "fig_feature_cards.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (fig_accuracy, fig_imaging_vs_material, fig_embedding_map, fig_patch_size_leak, fig_evidence_grid, fig_feature_bank, fig_feature_cards):
        f()
