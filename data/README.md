# data

The input images are **not in this repository**. They are Polaron's, released to hackathon teams, and Polaron
described them as costing more than £50,000 to collect. `.gitignore` keeps `data/Batch_*/` out of git; ask Polaron
before sharing them.

## Layout the code expects

```
data/
  Batch_1/   7 spots
  Batch_2/   7 spots
  Batch_3/  17 spots  (the baseline: what the supplier promised)
    img_<spot id>_BSE.tif
    img_<spot id>_Inlens.tif
    img_<spot id>_ETD.tif      (or _SE.tif: the same detector under another name, four spots)
```

Put the folders here, or point `LOSSLARP_DATA_DIR` at them. The feature bank reads the same folders:
`export LOSSLARP_DATA_DIR=$PWD/data` before running anything in `feature_bank/`.

## What the images are

| | |
|---|---|
| Material | Cross-sections of a lithium-ion anode: graphite flakes (dark), silicon particles (bright), pores between them |
| Spots | 31, each imaged by three co-registered detectors: 93 files, about 1.6 GB |
| Size | 7000 px wide, 1612 to 2316 px tall, 25.0 nm per pixel: 175 µm by 40 to 58 µm |
| Format | 8-bit TIFF saved as RGB with three near-identical channels. Read channel 0: some files carry a thin marker line in the green channel at one edge |
| Detectors | `BSE` backscattered electrons (brightness follows atomic number: composition). `Inlens` secondary electrons from the surface (edges, fine texture). `ETD` / `SE` side-mounted secondary electrons (relief) |
| Metadata | Microscope settings were stripped; pixel size is in the TIFF resolution tag |

## How the batches were made

Polaron cut about 20 large images into crops and grouped the crops into three batches on features of its own.
The 31 spots come from 13 of those source images ("sessions", told apart by image height). Eighteen spots are
neighbours in longer strips, and three strips cross batch folders. See `experiments/data_audit/` for the map and
the evidence.

## Held-back images

Two further sets were released during the event and are not on disk here: three test spots (`3e122cbj`,
`fn0mhxef`, `xrv9xvzb`; true batches 2, 1 and 3) and six evaluation spots used for judging. Their embeddings and
the model's calls are in `models/` and `cnn/results/`.
