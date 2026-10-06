# preprocessing/

Turns the raw images in `data/` into the clean images and tiles everything else uses. Run once after cloning, and again whenever `config.yaml` changes.

```bash
python preprocessing/process_data.py                          # settings from config.yaml, skips images already done
python preprocessing/process_data.py --size 256 --stride 128  # another tile setting, gets its own folder
python preprocessing/process_data.py --batches Batch_4        # a new batch only
python preprocessing/process_data.py --force                  # remake from scratch
```

| File | What it is |
|---|---|
| `config.yaml` | shared settings: tile size and overlap, train/val/test split, baseline batch |
| `process_data.py` | the program. Also what the features import (`Sample`, `load_sample`, `tiles`, ...) |
| `acquisition.py`, `acquisition.yaml`, `acquisition.md` | step 5: the acquisition check, its frozen limits and its evidence |

## Steps per image

1. grey: read the TIF as one 8-bit channel (the files are grey saved as RGB)
2. trim: drop plain white or black border rows and columns (none in the current images)
3. normalise: stretch brightness so the darkest 1 % is 0 and the brightest 1 % is 255
4. tiles: cut into square tiles, drop mostly blank ones
5. acquisition check (once per spot): was the spot imaged like the known ones? Prints a `WARNING` for each problem and
   a summary at the end. It changes no image. Skip it with `--no-acquisition-check`

Only steps 3 and 4 lose anything (the 1 % clipping, the edge that doesn't fit a whole tile).

## Acquisition warnings

The images come from 13 microscope sessions with different settings. The harmonisation in `features/_common` evens out
black level, grey mapping and noise, but it cannot undo polishing stripes, blur or burnt-out pixels. Step 5 grades
each spot against what the known spots cover:

| Grade | Meaning | What to do |
|---|---|---|
| G-A | imaged like the known spots | nothing |
| G-B | beyond any known spot, but inside the range we tested | features usable, treat with care |
| G-C | beyond the tested range | features NOT COMPARABLE: re-image next to a retained reference |

It checks BSE black level, BSE noise, Inlens burn-out (pixels at 255), curtaining (vertical polishing stripes) and
focus. On the current data, 29 of 31 spots are G-A. The two Batch_1 spots from session 2316 (4ih2ggld, 5n1q8atc) are
G-C for curtaining. The first run takes ~10 s per spot (it fills the harmonised cache the features use anyway); later
runs reuse `processed/acquisition.csv` unless `--force`. Code: `acquisition.py`, limits: `acquisition.yaml`,
evidence: `acquisition.md`.

The `acq_` values are about the microscope, not the material, so they never go into `features.csv` and must never be
model inputs.

## Output (in `processed/`, not in git)

| Output | What it is |
|---|---|
| `processed/full/{batch}/{sample_id}_{detector}.png` | each image after steps 1-3 |
| `processed/tiles/{size}px_stride{stride}_scale{scale}/{split}/{batch}/{sample_id}_{detector}_y{y}_x{x}.png` | square tiles in `train` / `val` / `test` folders. Each split folder works as a torchvision `ImageFolder`, class = batch |
| `processed/tiles/{size}px_stride{stride}_scale{scale}/index.csv` | one row per tile: `path, batch, sample_id, detector, split, is_baseline, y, x, size, scale` |
| `processed/acquisition.csv` | step 5, one row per spot: `batch, sample_id, acq_status` (G-A / G-B / G-C) and the ten `acq_` values |

The split is by spot, never by tile, so tiles from one image can't end up on both sides. Same `seed` = same split for everyone. Images have different heights, so the tile count per image varies (52 or 39 at 512 px).

## From your own code

```python
from preprocessing import load_sample, iter_samples, tiles, PIXEL_SIZE_UM, BASELINE

sample = load_sample("Batch_1", "4ih2ggld")   # one spot
sample.bse, sample.se, sample.inlens          # 2D uint8 images, same size
sample.batch, sample.sample_id, sample.split, sample.is_baseline

for sample in iter_samples("Batch_3"):        # one at a time
    ...
```

Don't change `process_data.py` or `config.yaml` without telling the team.
