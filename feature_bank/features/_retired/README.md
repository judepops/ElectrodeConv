# features/_retired

The five original features, kept for reference and comparability but no longer computed: folders starting with `_`
are skipped by the registry, so their columns no longer appear in `processed/features.csv`. They ran on the 1-99 %
stretched image with a per-image multi-Otsu threshold, which follows the imaging session rather than the material
(the independent audit of 2026-10-03; numbers in each folder's README and in its ledger entry).

| Folder | Columns | Replaced by |
|---|---|---|
| `porosity/` | `porosity_frac` | `open_porosity` (`porosity_open_frac`) |
| `bright_phase/` | `bright_phase_frac` | `si_fraction` (`bright_solid_frac`) |
| `pore_size/` | `pore_size_median_um2`, `pore_size_p90_um2`, `pore_size_count_per_1000um2` | `local_thickness` (`pore_lt_d50_um`), `two_point_correlation` (`s2_void_corrlen_x_um`) |
| `particle_size/` | `particle_size_d10/d50/d90_um` | nothing yet: it measured pore spacing, not graphite particle size (graphite flake size is `flake_morphology`, in progress) |
| `histogram_anomaly/` | `histogram_anomaly_z` | no material replacement: it tracked acquisition (session R2 0.94) |

To compute one again (e.g. for an old comparison), import it explicitly: `import features._retired.porosity.feature`
registers its `@feature` functions before `features.compute_all(sample)`.
