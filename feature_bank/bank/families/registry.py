"""registry: the team's named features (features/<folder>/feature.py), run on a Crop through an adapter.

How it works
    features.load_feature_modules() fills features.REGISTRY with the team's @feature functions. Every one of them
    calls features._common.harmonise.harmonised(sample). Here `sample` is an empty object and harmonised() is
    answered from the Crop: the harmonised BSE, its sigma-2 px blur, the harmonised Inlens, the void / bright /
    bright_fixed / dim maps and the anchors as `acq`. The SE view is built only if a feature asks for it (none
    does). No file is opened and the object carries no id, so the same code runs on every crop version (P0, the
    six imaging changes, the five injected material changes). Three tripwires stop the run with a clear error
    instead of leaking: a feature that reads anything from `sample` (the stretched .bse / .inlens / .se, the id,
    the folder), a feature that reads the SE channel without a leakrisk tag, and a feature that reads the anchors
    without an imaging tag.
    Only the functions listed in ROWS are run, so the column set is fixed: a feature the team adds later is not
    run until it has a row here (unaudited() lists such features).

Names
    A team column <function> or <function>_<key> keeps its name, except for parts the bank does not allow:
    a part beginning "poros" -> void, pore -> void (one word for the dark phase: it is unfilled void, the true
    pore space is not known), aspect -> elongation (forbidden name part), thick -> minor (it is the minor axis of a
    2D section, no thickness claim), tortuosity_2d -> tau2d_section (a 2D section number, never a tortuosity).

Statistics (53 scalars, all detector BSE). View "phase" = measured on the phase maps only; "harmonised" = also
needs the noise-matched BSE grey levels. um = the physical length the statistic probes.
    stat                              unit       nm   um    tag       what it is
    carbon_dark_domain_frac           fraction   50   5.6   mixed     graphite interior in a second, darker grey level (patches >= 25 um2)
    solid_chord_x_um / _y_um          um         25   5     material  mean solid chord along x (in plane) and y (through plane), kept apart
    solid_chord_hv_ratio              ratio      25   5     material  x chord / y chord
    flake_d50_um / flake_d50_aw_um    um         50   3.4   material  graphite fragment diameter, number and area weighted (watershed)
    flake_minor_d50_um                um         50   2.7   material  median minor axis of the fragments
    flake_elongation_median           ratio      50   3.4   material  median major / minor axis
    flake_n_per_1000um2               1/1000um2  50   3.4   material  fragments per area
    flake_orient_order                -1..1      50   0.4   mixed     nematic order of the layer direction on the graphite/void boundary
    flake_tilt_deg                    degrees    50   0.4   imaging   mean layer direction
    void_tile_cv / bright_tile_cv     sd/mean    25   12.8  material  spread of the phase fraction over 512 px tiles
    bright_excess_het_ratio           ratio      25   12.8  material  that tile variance / what the two-point correlation predicts
    local_void_q25_frac               fraction   25   5     material  25th percentile of the void fraction of 5 um tiles
    local_void_dense_window_frac      fraction   25   2.5   material  share of 2.5 um windows below a quarter of the crop's void fraction
    void_lt_d50_um / void_lt_d90_um   um         25   0.9-2.3  material  area-weighted local thickness of the void (median, top decile)
    solid_lt_d50_um                   um         50   4.6   material  the same median for the solid
    interface_density_per_um          1/um       25   0.025 material  void/solid boundary length per area (L_A, from line crossings)
    void_n_per_1000um2                1/1000um2  25   0.2   material  void objects >= 64 px per area
    void_open_frac_lo / _mid / _hi    fraction   25   -     material  void fraction on void_lo, void, void_hi
    void_open_ci95_frac               fraction   100  12    material  95 % sampling half-width of that fraction (integral range)
    void_fixed060_frac                fraction   25   -     material  void by a fixed 0.6 g threshold on the blurred BSE (sensitivity recipe)
    void_threshold                    g          25   -     imaging   the void threshold of this crop version
    bright_solid_frac_lo / _mid / _hi fraction   25   -     material  bright area / solid area on bright_lo, bright, bright_hi
    bright_frac_ci95                  fraction   100  12    material  95 % sampling half-width of the bright fraction
    bright_fixed_solid_frac           fraction   25   -     mixed     bright area / solid area, fixed 1.45 g threshold
    bright_n_per_1000um2              1/1000um2  25   1     material  bright objects >= 1 um, edge corrected
    bright_contrast_ratio             g          25   0.15  imaging   median grey level of the bright grain cores
    bright_dim_frac                   fraction   25   0.8   mixed     area in the dim-grey band (1.15-1.45 g) between graphite and bright
    bright_internal_dark_frac         fraction   25   0.15  mixed     grain interior darker than 0.85 x the grain's own core level
    bright_d50_um / bright_d90_um     um         25   4.4-6.9  material  area-weighted grain diameter quantiles, edge corrected
    bright_solidity_aw                ratio      25   0.8   material  area-weighted median area / convex hull area
    bright_elongation_aw              ratio      25   0.8   material  area-weighted median second-moment axis ratio
    bright_orient_order               -1..1      25   0.8   material  nematic order of the long axes of elongated grains
    bright_agglom_d50_um              um         25   4     material  diameter d50 of grains merged when closer than 1 um
    bright_contact_void_frac          fraction   25   0.15  mixed     share of the grain outline with void within 150 nm
    tau2d_section_solid_tau_y / _x    ratio      100  33.4  material  2D section transport factor of the solid, through plane and in plane
    tau2d_section_solid_anisotropy    ratio      100  33.4  material  tau_y / tau_x, median over tiles
    s2_void_corrlen_x_um / _y_um      um         25   1.2 / 0.6  material  two-point correlation length of the void along x and y
    s2_bright_corrlen_x_um / _y_um    um         25   2 / 1.4    material  the same for the bright phase
    s2_void_ / s2_bright_integral_range_um2   um2  100  12  material  area over which the phase is correlated
    undefined_count                   count      25   -     mixed     how many of the columns above were undefined in this crop version

Tags
    material  uses the phase maps alone, so it changes only when the maps change.
    mixed     compares grey levels or gradients inside one picture: carbon_dark_domain_frac (channelling contrast
              depends on kV and tilt), flake_orient_order (75 nm gradients; curtaining and scan blur are oriented
              too), bright_dim_frac (a fixed grey band, which gamma moves), bright_internal_dark_frac (a grey ratio),
              bright_fixed_solid_frac (a fixed grey threshold, while the bright / graphite grey ratio is set by the
              session: 12 % under gamma 0.8 on the smoke crops, against 2 % for the decision map),
              bright_contact_void_frac (a 150 nm contact band lies inside the 100-125 nm BSE edge spread: 18 % under a
              1 px blur on the smoke crops; the screen found the same).
    imaging   void_threshold is an anchor; flake_tilt_deg is the team's own mounting / scan-rotation diagnostic;
              bright_contrast_ratio is the bright / graphite grey ratio, which the microscope session sets (session
              R2 0.997 in notes/feature_screen.md, where it is recommended as an acquisition sentinel).

Undefined values
    The team features return NaN when a phase is missing (for example after bright_rm100). The bank allows no
    NaN, so an undefined column is written as 0 (sizes, counts, fractions, spreads, order parameters, tau) or 1
    (ratios and grey levels whose neutral value is 1: solid_chord_hv_ratio, flake_elongation_median,
    bright_excess_het_ratio, bright_solidity_aw, bright_elongation_aw, bright_contrast_ratio,
    tau2d_section_solid_anisotropy), and undefined_count says how many were filled. A team feature that raises a
    numerical error is filled the same way and reported on stderr.

Skipped, and why
    interface_density_resid_z   loads models/minkowski_functionals.npz (a line fitted on Batch_3 spots: nothing
                                fitted may enter the bank) and reads the spot's id to leave itself out.
    The lo / hi band is run only for the two phase fractions; the other columns use the decision maps.
    Not in features.REGISTRY, so not run (the team audit of 2026-10-03 withdrew them):
    carbon_domain_boundary_on_particle_frac, pore_chord, flake_orient_spread_deg, the void excess_het_ratio,
    bright_frac, bright_core_cv, bright_quadrat_cv, euler_density_per_1000um2, s2_solid.
    Not importable by the registry (folders starting with _): features/_retired (bright_phase, histogram_anomaly,
    particle_size, pore_size and the old void-fraction feature read the percentile-stretched sample.bse;
    histogram_anomaly also loads models/histogram_anomaly.npz).
    No registered feature reads sample.bse / .inlens / .se or needs the session or the height of the source picture:
    all 34 that are run go through harmonised() only. tau2d_section cuts square tiles as tall as the Crop, which is
    the same 1336 rows for every crop.

Check against the team's own route (harmonise_arrays on the raw pictures, their 1336 x 6984 crop) on r17byphk: the
    median column differs by 0.3 %, 38 of 48 by under 2 %, 46 by under 10 %. The Crop is 40 columns narrower and
    its noise top-up is another draw; flake_tilt_deg (14 %) and local_void_q25_frac (11 %) differ most.

Cost: about 8 s per crop version, about 1.3 GB.
"""
import math
import sys
from contextlib import contextmanager

import numpy as np
from scipy import ndimage as ndi

import features as team
from bank.core import PX_NM, FeatureResult
from features._common import harmonise as H

FAMILY = "registry"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {
    "bands": ["lo", "hi"],                                              # besides the decision maps ("mid")
    "banded": {"void_open_frac": "void", "bright_solid_frac": "bright"},   # function -> the map whose threshold moves
}

P, HM, AN = "phase", "harmonised", "anchored"
# stat, team function (after renaming), view, scale_nm, length_um, tag, value when undefined
ROWS = (
    ("carbon_dark_domain_frac", "carbon_dark_domain_frac", HM, 50, 5.6, "mixed", 0.0),
    ("solid_chord_x_um", "solid_chord", P, 25, 5.0, "material", 0.0),
    ("solid_chord_y_um", "solid_chord", P, 25, 5.0, "material", 0.0),
    ("solid_chord_hv_ratio", "solid_chord", P, 25, 5.0, "material", 1.0),
    ("flake_d50_um", "flake", P, 50, 3.4, "material", 0.0),
    ("flake_d50_aw_um", "flake", P, 50, 3.4, "material", 0.0),
    ("flake_minor_d50_um", "flake", P, 50, 2.7, "material", 0.0),
    ("flake_elongation_median", "flake", P, 50, 3.4, "material", 1.0),
    ("flake_n_per_1000um2", "flake", P, 50, 3.4, "material", 0.0),
    ("flake_orient_order", "flake_orient_order", HM, 50, 0.4, "mixed", 0.0),
    ("flake_tilt_deg", "flake_tilt_deg", HM, 50, 0.4, "imaging", 0.0),
    ("void_tile_cv", "void_tile_cv", P, 25, 12.8, "material", 0.0),
    ("bright_tile_cv", "bright_tile_cv", P, 25, 12.8, "material", 0.0),
    ("bright_excess_het_ratio", "bright_excess_het_ratio", P, 25, 12.8, "material", 1.0),
    ("local_void_q25_frac", "local_void", P, 25, 5.0, "material", 0.0),
    ("local_void_dense_window_frac", "local_void", P, 25, 2.5, "material", 0.0),
    ("void_lt_d50_um", "void_lt", P, 25, 0.9, "material", 0.0),
    ("void_lt_d90_um", "void_lt", P, 25, 2.3, "material", 0.0),
    ("solid_lt_d50_um", "solid_lt_d50_um", P, 50, 4.6, "material", 0.0),
    ("interface_density_per_um", "interface_density_per_um", P, 25, 0.025, "material", 0.0),
    ("void_n_per_1000um2", "void_n_per_1000um2", P, 25, 0.2, "material", 0.0),
    ("void_open_frac", "void_open_frac", P, 25, None, "material", 0.0),
    ("void_open_ci95_frac", "void_open_ci95_frac", P, 100, 12.0, "material", 0.0),
    ("void_fixed060_frac", "void_fixed060_frac", HM, 25, None, "material", 0.0),
    ("void_threshold", "void_threshold", AN, 25, None, "imaging", 0.0),
    ("bright_solid_frac", "bright_solid_frac", P, 25, None, "material", 0.0),
    ("bright_frac_ci95", "bright_frac_ci95", P, 100, 12.0, "material", 0.0),
    ("bright_fixed_solid_frac", "bright_fixed_solid_frac", P, 25, None, "mixed", 0.0),
    ("bright_n_per_1000um2", "bright_n_per_1000um2", P, 25, 1.0, "material", 0.0),
    ("bright_contrast_ratio", "bright_contrast_ratio", HM, 25, 0.15, "imaging", 1.0),
    ("bright_dim_frac", "bright_dim_frac", P, 25, 0.8, "mixed", 0.0),
    ("bright_internal_dark_frac", "bright_internal_dark_frac", HM, 25, 0.15, "mixed", 0.0),
    ("bright_d50_um", "bright_d50_um", P, 25, 4.4, "material", 0.0),
    ("bright_d90_um", "bright_d90_um", P, 25, 6.9, "material", 0.0),
    ("bright_solidity_aw", "bright_solidity_aw", P, 25, 0.8, "material", 1.0),
    ("bright_elongation_aw", "bright_elongation_aw", P, 25, 0.8, "material", 1.0),
    ("bright_orient_order", "bright_orient_order", P, 25, 0.8, "material", 0.0),
    ("bright_agglom_d50_um", "bright_agglom_d50_um", P, 25, 4.0, "material", 0.0),
    ("bright_contact_void_frac", "bright_contact_void_frac", P, 25, 0.15, "mixed", 0.0),
    ("tau2d_section_solid_tau_y", "tau2d_section", P, 100, 33.4, "material", 0.0),
    ("tau2d_section_solid_tau_x", "tau2d_section", P, 100, 33.4, "material", 0.0),
    ("tau2d_section_solid_anisotropy", "tau2d_section", P, 100, 33.4, "material", 1.0),
    ("s2_void_corrlen_x_um", "s2_void", P, 25, 1.2, "material", 0.0),
    ("s2_void_corrlen_y_um", "s2_void", P, 25, 0.6, "material", 0.0),
    ("s2_void_integral_range_um2", "s2_void", P, 100, 12.0, "material", 0.0),
    ("s2_bright_corrlen_x_um", "s2_bright", P, 25, 2.0, "material", 0.0),
    ("s2_bright_corrlen_y_um", "s2_bright", P, 25, 1.4, "material", 0.0),
    ("s2_bright_integral_range_um2", "s2_bright", P, 100, 12.0, "material", 0.0),
)
SKIPPED = {"interface_density_resid_z": "loads models/minkowski_functionals.npz and reads the spot's id"}
_RENAMED_PARTS = {"pore": "void", "aspect": "elongation", "thick": "minor"}
_functions = {}                                   # team function (after renaming) -> callable, filled on first use


class ProvenanceError(AttributeError):
    """A team feature tried to read something a bank family must never see."""


class _Sample:
    """What the team features get as `sample`: nothing. Any attribute they ask for is refused."""
    __slots__ = ()

    def __getattr__(self, key):
        raise ProvenanceError(f"a team feature read sample.{key}: the bank hands over the Crop's arrays only "
                              "(no stretched pictures, no id, no folder)")


class _Spot(H.Harmonised):
    """The team's Harmonised, built from a Crop. It notes when the anchors or the SE channel are read, and decodes
    the SE view only then."""

    def __getattribute__(self, key):
        if key in ("se", "acq"):
            own = object.__getattribute__(self, "__dict__")
            own.setdefault("_touched", set()).add(key)
            if key == "se" and own["se"] is None:
                own["se"] = own["_se"]()
        return object.__getattribute__(self, key)


def bank_name(team_name):
    """A team function or column name with the parts the bank does not allow replaced (see Names above)."""
    parts = []
    for part in team_name.replace("tortuosity_2d", "tau2d_section", 1).split("_"):
        part = "void" if part.startswith("poros") else _RENAMED_PARTS.get(part, part)
        if not parts or parts[-1] != part:                      # "void_void_threshold" -> "void_threshold"
            parts.append(part)
    return "_".join(parts)


def team_functions():
    """{team function after renaming: callable} for the functions that have rows here."""
    if not _functions:
        team.load_feature_modules()
        wanted = {row[1] for row in ROWS}
        found = {bank_name(name): fn for name, fn in team.REGISTRY.items()}
        missing = sorted(wanted - set(found))
        if missing:
            raise RuntimeError(f"registry: the team registry no longer has {missing}")
        _functions.update({name: found[name] for name in sorted(wanted)})
    return _functions


def unaudited():
    """Registered team features that are neither run nor listed in SKIPPED (added after this file was written)."""
    team_functions()
    known = {row[1] for row in ROWS} | set(SKIPPED)
    return sorted(name for name in team.REGISTRY if bank_name(name) not in known)


def warmup(cfg):
    team_functions()
    extra = unaudited()
    if extra:
        print(f"registry: not run, no row in bank/families/registry.py yet: {extra}", file=sys.stderr)


def _spot(crop, bse_blur, **maps):
    """The Crop as the team's Harmonised. `maps` swaps phase maps (void="void_lo", ...) for the lo / hi bands.

    Left out of `acq` on purpose: the window position inside the source picture, the noise seed, and whether an SE
    file exists (all three are provenance, not anchors).
    """
    a = crop.anchors
    acq = {"bse_black_raw": a["black"], "bse_graphite_raw": a["graphite"], "bse_noise_sigma": a["bse_noise_sigma"],
           "inlens_noise_sigma": a["inlens_noise_sigma"], "void_threshold": a["void_threshold"],
           "bright_threshold": a["bright_threshold"], "bright_mode": a["bright_mode"],
           "bright_mode_found": a["bright_mode_found"]}
    spot = _Spot(crop.view("BSE", "harmonised"), bse_blur, crop.view("Inlens", "harmonised"), None,
                 *(crop.phase(maps.get(k, k)) for k in ("void", "bright", "bright_fixed", "dim")), acq)
    spot.__dict__["_se"] = lambda: crop.view("SE", "anchored")
    return spot


@contextmanager
def _handed_over(spot):
    """A fresh empty sample for which the team's harmonised(sample) returns `spot`, without touching a file."""
    sample, before = _Sample(), dict(H._cache)
    H._cache.update(sample=sample, value=spot)
    try:
        yield sample
    finally:
        H._cache.update(before)


def _run(name, fn, sample, spot, tags):
    """One team function -> {bank stat: value}; {} if it raised a numerical error. Leaks stop the run."""
    spot.__dict__.pop("_touched", None)
    try:
        out = fn(sample)
    except ProvenanceError:
        raise
    except Exception as e:                                       # noqa: BLE001  (a team feature failing on odd input)
        print(f"registry: {name} failed ({type(e).__name__}: {e}); its columns get the undefined value", file=sys.stderr)
        return {}
    touched = spot.__dict__.pop("_touched", set())
    if "se" in touched and tags != {"leakrisk"}:
        raise ProvenanceError(f"registry: {name} read the SE channel: tag its rows leakrisk (detector SE)")
    if "acq" in touched and tags != {"imaging"}:
        raise ProvenanceError(f"registry: {name} read the anchors: tag its rows imaging")
    if isinstance(out, dict):
        return {bank_name(f"{name}_{k}"): float(v) for k, v in out.items()}
    return {name: float(out)}


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    functions = team_functions()
    tags = {name: {row[5] for row in ROWS if row[1] == name} for name in functions}
    # the blur the team's recipe segments on (sigma 2 px), computed once for every pass
    bse_blur = ndi.gaussian_filter(crop.view("BSE", "harmonised"), H.CFG["segmentation"]["blur_sigma_px"])
    values = {}
    spot = _spot(crop, bse_blur)
    with _handed_over(spot) as sample:
        for name, fn in functions.items():
            values.update(_run(name, fn, sample, spot, tags[name]))
    banded = {}
    for band in cfg["bands"]:
        for name, which in cfg["banded"].items():
            moved = _spot(crop, bse_blur, **{which: f"{which}_{band}"})
            with _handed_over(moved) as sample:
                banded[(name, band)] = _run(name, functions[name], sample, moved, tags[name]).get(name, math.nan)

    undefined = 0
    for stat, name, view, scale_nm, length_um, tag, fill in ROWS:
        versions = [("", values.get(stat, math.nan))]
        if name in cfg["banded"]:                                # a phase fraction is always reported lo / mid / hi
            versions = [(f"_{b}", versions[0][1] if b == "mid" else banded[(name, b)])
                        for b in ("lo", "mid", "hi") if b == "mid" or b in cfg["bands"]]
        for suffix, value in versions:
            if not np.isfinite(value):
                value, undefined = fill, undefined + 1
            res.scalar("BSE", view, scale_nm, stat + suffix, value, length_um=length_um, tag=tag)
    res.scalar("BSE", "phase", PX_NM, "undefined_count", undefined, tag="mixed")
    return res
