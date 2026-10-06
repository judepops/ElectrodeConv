"""Frozen MicroNet ResNet50 features (NASA `pretrained_microscopy_models`, weights v1.1), BSE and Inlens.

A ResNet50 trained to classify more than 100,000 micrographs by material class (Stuckner et al. 2022, MIT licence):
the one model here that has seen micrographs before. The weights are the public file that the
`pretrained_microscopy_models` package itself downloads (its URL helper for resnet50 / micronet / v1.1), loaded
into a plain torchvision ResNet50, so the package and its dependencies are not installed. Normalisation is the
ImageNet mean and std, as in the package's classification example.

The four residual stages are sampled every 4, 8, 16 and 32 px (256, 512, 1024 and 2048 channels). At s1 (25 nm)
that is 0.1, 0.2, 0.4 and 0.8 um; multiply by 2, 4, 8 for s2, s4, s8. The receptive field of a stage is several
times its sampling step, so `length_um` is the sampling step: the finest length the stage resolves. Activations
are stage outputs after the ReLU (non-negative, dimensionless). Inputs, scales, tiling, mirror averaging and the
two profiles (full, and BANK_EMB_PROFILE=lite) are described in bank/families/_emb_common.py. Whole-crop inputs
are cut to 320 x 1728 px at s4 and 160 x 864 px at s8 (multiples of 32).

Blocks, per detector (BSE, Inlens), view (raw, anchored), scale and stage k in {1, 2, 3, 4} (stage 1 is the
finest), averaged over the tiles of the crop (layer = micronetR50.st<k>):
    st<k>_mean   channel means over positions: how much of each learned pattern the field holds. st4_mean is the
                 network's usual 2048-number embedding.
    st<k>_std    channel standard deviations over positions: how unevenly each pattern is spread.
    st<k>_gem    generalised mean (p = 3) over positions: weighted towards rare, strongly responding positions.
    st1_gram     Gram matrix of stage 1 (mean over positions of the product of two channels, not centred; upper
                 triangle with the diagonal: 32896 numbers). Which patterns occur together. Units: activation
                 squared. Length: 0.1 um at s1.
Scalars, per detector, view, scale and stage:
    st<k>_mean_norm     length of the channel-mean vector, mean over tiles.
    st<k>_spread        root of the summed channel variances: RMS distance of a position from its field mean.
    st<k>_tile_spread   s1 and s2 only: RMS distance of the tiles' channel means from the crop mean. Heterogeneity
                        between 11.2 um (s1) or 22.4 um (s2) fields.
    BSExInlens st<k>_mean_cos   cosine between the BSE and the Inlens channel-mean vector (-1..1).
Tile arrays:
    st3_mean_tiles, st4_mean_tiles   s1 only, (n_tiles, 1024) and (n_tiles, 2048): channel means of every tile.

Tag: everything is `mixed`. Fine stages respond to noise and focus as readily as to material texture; the harness
decides per block from the perturbation runs. The raw view carries the black level and gain directly.
"""
from bank.families import _emb_common as common

FAMILY = "emb_micronet"
TIER = 1
RUNS_ON = "gpu"
DEFAULT_CFG = common.full_cfg(
    model="micronet_resnet50_v1.1", kind="resnet_url", short="micronetR50", gram_stages=[1],
    weights_url="https://nasa-public-data.s3.amazonaws.com/microscopy_segmentation_models/resnet50_pretrained_microscopynet_v1.1.pth.tar",
    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])


def warmup(cfg):
    common.warmup(cfg)


def extract(crop, cfg):
    return common.extract_cnn(FAMILY, crop, cfg)
