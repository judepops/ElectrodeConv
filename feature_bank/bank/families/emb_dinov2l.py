"""Frozen DINOv2 ViT-L/14 embeddings with registers (`vit_large_patch14_reg4_dinov2.lvd142m`, Apache-2.0), BSE and Inlens.

The predecessor of DINOv3, trained on 142 million curated pictures: a second, independently trained opinion on
the same crops. 24 blocks, 1024 channels, 14 px patches, 1 class token and 4 register tokens. Blocks 5, 11, 17 and
23 (counted from 0) are read out, each after the model's final LayerNorm, so the numbers are dimensionless
"normalised activations", about 1 per channel. The learned position grid (37 x 37) is resampled to each input's
token grid; the picture itself is never resampled. Inputs, scales, tiling, mirror averaging and the two profiles
(full, and BANK_EMB_PROFILE=lite) are described in bank/families/_emb_common.py.

One patch is 14 px: 0.35 um at s1 (25 nm), 0.7 um at s2, 1.4 um at s4, 2.8 um at s8. One input field is a 448 px
tile (32 x 32 patches; 11.2 um at s1, 22.4 um at s2) or the whole crop cut to 322 x 1736 px at s4 and
154 x 868 px at s8. Every token sees its whole field through attention, so `length_um` is the finest length a
statistic resolves (the patch) or the field it summarises (class and register tokens), not a hard support.

Blocks, per detector (BSE, Inlens), view (raw, anchored), scale and block b in {5, 11, 17, 23}; 1024 numbers each,
averaged over the tiles of the crop (layer = dinov2L.b<b>):
    b<b>_cls      class token: the model's summary of one field. Length: the field.
    b<b>_reg      mean of the 4 register tokens: global scratch memory of the field. Length: the field.
    b<b>_pmean    mean patch token: average local appearance. Length: one patch.
    b<b>_pstd     standard deviation of the patch tokens over the field, per channel: how varied the field is.
    b<b>_gem      generalised mean (p = 3) of the patch tokens, signed (cube root of the mean cube): like pmean but
                  weighted towards rare, strongly responding patches (bright grains, large voids).
Scalars, per detector, view, scale and block (same units):
    b<b>_cls_norm        length of the class token vector, mean over tiles.
    b<b>_patch_norm      mean length of a patch token vector.
    b<b>_patch_spread    root of the summed channel variances of the patch tokens: RMS distance of a patch from
                         its field mean. Texture heterogeneity at patch pitch within one field.
    b<b>_cls_patch_cos   cosine between class token and mean patch token (-1..1).
    b<b>_tile_spread     s1 and s2 only: RMS distance of the tiles' mean patch tokens from the crop mean.
                         Heterogeneity between 11.2 um (s1) or 22.4 um (s2) fields.
    BSExInlens b<b>_pmean_cos   cosine between the BSE and the Inlens mean patch token (-1..1).
Tile arrays:
    b17_pmean_tiles, b23_pmean_tiles   s1 only, (n_tiles, 1024): the mean patch token of every tile, for set kernels.

Tag: everything is `mixed`. The network was never told what is material and what is acquisition; it responds to
noise, blur and tone as readily as to voids and grains. The harness decides per block from the perturbation runs.
The raw view carries the black level and gain directly; the anchored view removes those two but not noise or focus.
"""
from bank.families import _emb_common as common

FAMILY = "emb_dinov2l"
TIER = 1
RUNS_ON = "gpu"
DEFAULT_CFG = common.full_cfg(model="vit_large_patch14_reg4_dinov2.lvd142m", kind="vit", short="dinov2L", layers=[5, 11, 17, 23],
                              n_register=4)


def warmup(cfg):
    common.warmup(cfg)


def extract(crop, cfg):
    return common.extract_vit(FAMILY, crop, cfg)
