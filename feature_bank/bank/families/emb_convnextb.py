"""Frozen DINOv3 ConvNeXt-B features (`convnext_base.dinov3_lvd1689m`, the ungated timm mirror), BSE and Inlens.

A convolutional network distilled from the DINOv3 ViT-7B teacher. Unlike the transformers its features have a
limited support, so each stage probes its own length scale: the four stages are sampled every 4, 8, 16 and 32 px
(128, 256, 512 and 1024 channels). At s1 (25 nm) that is 0.1, 0.2, 0.4 and 0.8 um; multiply by 2, 4, 8 for s2, s4,
s8. The receptive field of a stage is several times its sampling step (7 x 7 depthwise kernels stacked), so
`length_um` is the sampling step: the finest length the stage resolves. Activations are the raw stage outputs
(signed, dimensionless). Inputs, scales, tiling, mirror averaging and the two profiles (full, and
BANK_EMB_PROFILE=lite) are described in bank/families/_emb_common.py. Whole-crop inputs are cut to 320 x 1728 px
at s4 and 160 x 864 px at s8 (multiples of 32).

Blocks, per detector (BSE, Inlens), view (raw, anchored), scale and stage k in {1, 2, 3, 4} (stage 1 is the
finest), averaged over the tiles of the crop (layer = convnextB.st<k>):
    st<k>_mean   channel means over positions: how much of each learned pattern the field holds.
    st<k>_std    channel standard deviations over positions: how unevenly each pattern is spread.
    st<k>_gem    generalised mean (p = 3) over positions, signed (cube root of the mean cube): weighted towards
                 rare, strongly responding positions.
    st1_gram, st2_gram   Gram matrix of stages 1 and 2 (mean over positions of the product of two channels, not
                 centred; upper triangle with the diagonal: 8256 and 32896 numbers). Which patterns occur together:
                 the classic texture descriptor. Units: activation squared. Length: 0.1 and 0.2 um at s1.
Scalars, per detector, view, scale and stage:
    st<k>_mean_norm     length of the channel-mean vector, mean over tiles.
    st<k>_spread        root of the summed channel variances: RMS distance of a position from its field mean.
    st<k>_tile_spread   s1 and s2 only: RMS distance of the tiles' channel means from the crop mean. Heterogeneity
                        between 11.2 um (s1) or 22.4 um (s2) fields.
    BSExInlens st<k>_mean_cos   cosine between the BSE and the Inlens channel-mean vector (-1..1).
Tile arrays:
    st3_mean_tiles, st4_mean_tiles   s1 only, (n_tiles, 512) and (n_tiles, 1024): channel means of every tile.

Tag: everything is `mixed`. Fine stages respond to noise and focus as readily as to material texture; the harness
decides per block from the perturbation runs. The raw view carries the black level and gain directly.
"""
from bank.families import _emb_common as common

FAMILY = "emb_convnextb"
TIER = 1
RUNS_ON = "gpu"
DEFAULT_CFG = common.full_cfg(model="convnext_base.dinov3_lvd1689m", kind="timm_cnn", short="convnextB", gram_stages=[1, 2])


def warmup(cfg):
    common.warmup(cfg)


def extract(crop, cfg):
    return common.extract_cnn(FAMILY, crop, cfg)
