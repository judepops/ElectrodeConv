"""Shared code of the frozen foundation-model embedding families. Not a family itself (the file name starts with _).

    emb_dinov3l    vit_large_patch16_dinov3.lvd1689m        ViT-L/16, class token + 4 register tokens
    emb_dinov2l    vit_large_patch14_reg4_dinov2.lvd142m    ViT-L/14, class token + 4 register tokens
    emb_convnextb  convnext_base.dinov3_lvd1689m            ConvNeXt-B, 4 stages
    emb_micronet   MicroNet ResNet50 (trained on micrographs)   ResNet50, 4 stages

Nothing is fitted here: the networks are frozen and every number is a deterministic function of one Crop.

Input (the same for every model)
    One detector at a time, replicated to 3 channels, normalised with the model's own mean and std.
    raw view          grey level / 255
    anchored BSE      graphite units mapped linearly from the fixed range [-0.5, 3.0] to [0, 1] and clipped
    anchored Inlens   already rank-normalised to 0..1
    The picture is never interpolated, rotated or mirrored top-to-bottom. Coarser scales are integer block means.

Scales (scale_nm = 25 * factor)
    s1   448 px tiles of the 25 nm view      one tile = 11.2 um
    s2   448 px tiles of the 50 nm view      one tile = 22.4 um
    s4   the whole crop at 100 nm as one non-square input, cut centrally to a multiple of the patch size (or stride)
    s8   the whole crop at 200 nm, likewise
    Tiles cover the whole view: ceil(length / 448) tiles per axis with evenly spaced origins. Neighbouring tiles
    therefore overlap a little (4 px vertically and about 15 px horizontally at s1) or a lot (half a tile vertically
    at s2, where the view is only 668 px tall). Tile order is fixed; tile positions are never returned or used.

Mirror averaging (cfg["hflip"])
    The features of a tile and of its left-right mirror are averaged. Left-right is the in-plane direction, so the
    mirror is a legitimate second look; through-thickness (vertical) is never mirrored.

Profiles
    DEFAULT_CFG of each family is the full profile: raw and anchored views, scales s1 s2 s4 s8, mirror averaging.
    BANK_EMB_PROFILE=lite   anchored view only, no mirror averaging, scales s1 and s4. About 5 times cheaper
                            (on Apple MPS: 17 s against 91 s per crop version for DINOv3 ViT-L).
    BANK_EMB_TOKENS=0       do not save the token grids (emb_dinov3l only): saves 51 MB per crop version. By default
                            they are saved in both profiles, from one extra s2 pass that stops at block 11.
    BANK_EMB_DEVICE=cpu     force a device. Default: cuda, then mps, then cpu.
    BANK_EMB_BF16=0         float32 on cuda too. Default: bf16 autocast for the network's forward pass on cuda only;
                            the statistics are always computed in float32.
    One feature directory must be made with ONE profile on ONE kind of device. Lite and full give different numbers
    for the columns they share (lite has no mirror averaging), and bf16 moves a block by about 0.5 % of its length
    (up to 3 % for the last block's GeM) relative to float32: small, but not small against a robustness threshold.
    (Measured with bf16 autocast on the CPU, s8, one crop, all four models; cuda itself is untested.)
    The contract test compares the column set and the values with the stored run.
"""
import contextlib
import os

import numpy as np

from bank.core import PX_NM, QUANT_RANGE, FeatureResult

TAG = "mixed"            # every embedding statistic: a frozen network responds to material and to acquisition alike
PAIR = "BSExInlens"      # the detector label of the cross-detector cosines
LITE = {"profile": "lite", "views": ["anchored"], "tile_scales": [1], "whole_scales": [4], "hflip": False}
_LOADED = {}


# ----------------------------------------------------------------------------------------------------
# configuration
# ----------------------------------------------------------------------------------------------------
def full_cfg(**model):
    """The full profile of the brief plus the model's own entries. Every tunable number is in here."""
    cfg = {"profile": "full", "detectors": ["BSE", "Inlens"], "views": ["raw", "anchored"], "tile_px": 448,
           "tile_scales": [1, 2], "whole_scales": [4, 8], "hflip": True, "gem_p": 3.0, "bse_range": list(QUANT_RANGE["BSE"]),
           "keep_tiles_scale": 1, "keep_tiles_last": 2, "token_grid": None, "batch": {"cuda": 32, "mps": 8, "cpu": 4}}
    cfg.update(model)
    return cfg


def resolve(cfg):
    """The configuration actually used: cfg, with the lite overrides when BANK_EMB_PROFILE=lite."""
    cfg = dict(cfg)
    profile = os.environ.get("BANK_EMB_PROFILE", "").strip().lower()
    if profile == "lite":
        cfg.update(LITE)
    elif profile not in ("", "full"):
        raise ValueError(f"BANK_EMB_PROFILE={profile!r}: use full or lite")
    if os.environ.get("BANK_EMB_TOKENS", "").strip() == "0":
        cfg["token_grid"] = None
    return cfg


# ----------------------------------------------------------------------------------------------------
# models (loaded once per process)
# ----------------------------------------------------------------------------------------------------
class Loaded:
    """A frozen network on its device, with what is needed to feed it."""

    def __init__(self, net, kind, mean, std, multiple, strides, device):
        import torch
        self.net, self.kind, self.multiple, self.strides, self.device = net, kind, int(multiple), tuple(strides), device
        self.mean = torch.tensor(mean, dtype=torch.float32, device=device).view(1, 3, 1, 1)
        self.std = torch.tensor(std, dtype=torch.float32, device=device).view(1, 3, 1, 1)


def pick_device():
    import torch
    forced = os.environ.get("BANK_EMB_DEVICE", "").strip()
    if forced:
        return torch.device(forced)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load(cfg):
    """The network of cfg["model"], frozen, in eval mode, on the device. The first call downloads the weights."""
    key = cfg["model"]
    if key in _LOADED:
        return _LOADED[key]
    import torch
    device = pick_device()
    kind = cfg["kind"]
    if kind == "vit":
        import timm
        net = timm.create_model(cfg["model"], pretrained=True, num_classes=0, global_pool="token", dynamic_img_size=True)
        if not isinstance(net.norm, torch.nn.LayerNorm):
            raise RuntimeError(f"{cfg['model']}: expected a final LayerNorm to apply to the intermediate blocks")
        if len(net.blocks) <= max(cfg["layers"]) or net.num_prefix_tokens != 1 + cfg["n_register"]:
            raise RuntimeError(f"{cfg['model']}: {len(net.blocks)} blocks, {net.num_prefix_tokens} prefix tokens: not what cfg expects")
        mean, std = net.pretrained_cfg["mean"], net.pretrained_cfg["std"]
        multiple, strides = net.patch_embed.patch_size[0], (net.patch_embed.patch_size[0],)
    elif kind == "timm_cnn":
        import timm
        net = timm.create_model(cfg["model"], pretrained=True, num_classes=0)
        mean, std = net.pretrained_cfg["mean"], net.pretrained_cfg["std"]
        strides = tuple(int(f["reduction"]) for f in net.feature_info)
        multiple = strides[-1]
    elif kind == "resnet_url":
        import torchvision
        net = torchvision.models.resnet50(weights=None)
        state = torch.hub.load_state_dict_from_url(cfg["weights_url"], map_location="cpu", progress=False, weights_only=True)
        state = state.get("state_dict", state)
        state = {k: v for k, v in state.items() if not k.startswith("fc.")}        # the classifier head is not used
        bad = net.load_state_dict(state, strict=False)
        if bad.unexpected_keys or set(bad.missing_keys) - {"fc.weight", "fc.bias"}:
            raise RuntimeError(f"{cfg['model']}: weights do not fit a torchvision ResNet50: missing {bad.missing_keys[:5]}, "
                               f"unexpected {bad.unexpected_keys[:5]}")
        net.fc = torch.nn.Identity()
        mean, std, strides, multiple = cfg["mean"], cfg["std"], (4, 8, 16, 32), 32
    else:
        raise ValueError(f"unknown model kind {kind!r}")
    net = net.eval().requires_grad_(False).to(device)
    _LOADED[key] = Loaded(net, kind, mean, std, multiple, strides, device)
    return _LOADED[key]


def warmup(cfg):
    """Download the weights and put the network on the device, once per process."""
    load(resolve(cfg))


# ----------------------------------------------------------------------------------------------------
# picture -> network input
# ----------------------------------------------------------------------------------------------------
def model_input(crop, det, view, scale, cfg):
    """One detector, one view, one scale as float32 in 0..1 (before the model's own mean / std)."""
    a = np.asarray(crop.view(det, view, scale), np.float32)
    if view == "raw":
        return a / np.float32(255.0)
    if det == "BSE":
        lo, hi = cfg["bse_range"]
        return np.clip((a - np.float32(lo)) / np.float32(hi - lo), 0.0, 1.0)
    return np.clip(a, 0.0, 1.0)


def _origins(length, size):
    if length < size:
        raise ValueError(f"view of {length} px is smaller than a {size} px tile")
    n = int(np.ceil(length / size))
    return [0] if n == 1 else [int(v) for v in np.rint(np.linspace(0, length - size, n))]


def cover_tiles(arr, size):
    """(n, size, size) tiles that cover the whole array, in a fixed order. Positions are not returned."""
    return np.stack([arr[y:y + size, x:x + size] for y in _origins(arr.shape[0], size) for x in _origins(arr.shape[1], size)])


def cut_to_multiple(arr, m):
    """The central part of the array whose sides are multiples of m."""
    h, w = (arr.shape[0] // m) * m, (arr.shape[1] // m) * m
    y, x = (arr.shape[0] - h) // 2, (arr.shape[1] - w) // 2
    return arr[y:y + h, x:x + w]


def inputs_at(crop, det, view, scale, cfg, L):
    """(n, H, W) inputs of one detector / view / scale: tiles at the tile scales, the whole crop otherwise."""
    x = model_input(crop, det, view, scale, cfg)
    if scale in cfg["tile_scales"]:
        return cover_tiles(x, cfg["tile_px"])
    return cut_to_multiple(x, L.multiple)[None]


def _batches(x, L, cfg):
    import torch
    step = int(cfg["batch"].get(L.device.type, 4))
    for i in range(0, len(x), step):
        t = torch.from_numpy(np.ascontiguousarray(x[i:i + step])).to(L.device)
        yield (t[:, None].expand(-1, 3, -1, -1) - L.mean) / L.std


def _autocast(L):
    """bf16 for the network's forward pass on cuda only. The statistics are always computed in float32, outside it."""
    import torch
    on = L.device.type == "cuda" and os.environ.get("BANK_EMB_BF16", "1").strip() != "0"
    return torch.autocast("cuda", dtype=torch.bfloat16) if on else contextlib.nullcontext()


def _looks(t, cfg):
    """The input and, with mirror averaging, its left-right mirror (the last axis is the in-plane direction)."""
    import torch
    return [t, torch.flip(t, dims=(-1,))] if cfg["hflip"] else [t]


def _gem(x, p, dim):
    """Signed generalised mean over `dim`: sign(m) |m|^(1/p) with m = mean(sign(x) |x|^p). Equal to the usual GeM for
    non-negative activations; for p = 3 it is the cube root of the mean cube, so it also works on signed tokens."""
    m = (x.sign() * x.abs().pow(p)).mean(dim)
    return m.sign() * m.abs().pow(1.0 / p)


def _collect(per_look):
    """Mean over the looks of one mini-batch -> {key: numpy}."""
    return {k: sum(look[k] for look in per_look).div(len(per_look)).float().cpu().numpy() for k in per_look[0]}


def _stack(parts):
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def _cos(a, b):
    return float(np.dot(a, b) / max(float(np.linalg.norm(a) * np.linalg.norm(b)), 1e-12))


def _rms_from_mean(v):
    """Root-mean-square distance of the rows of v from their mean (0 for a single row)."""
    return float(np.sqrt(((v - v.mean(0)) ** 2).sum(1).mean()))


# ----------------------------------------------------------------------------------------------------
# vision transformers
# ----------------------------------------------------------------------------------------------------
def _vit_blocks(L, t, blocks, stop_early=False):
    """[(patch tokens (b, n, c), prefix tokens (b, k, c))] per block index, float32, final LayerNorm applied."""
    with _autocast(L):
        out = L.net.forward_intermediates(t, indices=list(blocks), return_prefix_tokens=True, norm=True, stop_early=stop_early,
                                          output_fmt="NLC", intermediates_only=True)
    return [(patch.float(), prefix.float()) for patch, prefix in out]


def vit_stats(L, x, cfg):
    """x (n, H, W) in 0..1 -> {"b11_cls": (n, c), ..., "b11_pnorm": (n, 1)}: per-input pooled tokens of every block."""
    import torch
    parts = []
    with torch.inference_mode():
        for t in _batches(x, L, cfg):
            per_look = []
            for look in _looks(t, cfg):
                s = {}
                for b, (patch, prefix) in zip(cfg["layers"], _vit_blocks(L, look, cfg["layers"])):
                    s[f"b{b}_cls"] = prefix[:, 0]
                    if prefix.shape[1] > 1:
                        s[f"b{b}_reg"] = prefix[:, 1:].mean(1)
                    s[f"b{b}_pmean"] = patch.mean(1)
                    s[f"b{b}_pstd"] = patch.std(dim=1, correction=0)
                    s[f"b{b}_gem"] = _gem(patch, cfg["gem_p"], 1)
                    s[f"b{b}_pnorm"] = patch.norm(dim=-1).mean(1, keepdim=True)
                per_look.append(s)
            parts.append(_collect(per_look))
    return _stack(parts)


def vit_token_grid(L, x, block, cfg):
    """x (n, H, W) -> (n, gh * gw * c) float16: the patch tokens of one block, final LayerNorm applied, row-major."""
    import torch
    out = []
    with torch.inference_mode():
        for t in _batches(x, L, cfg):
            patch, _ = _vit_blocks(L, t, [block], stop_early=True)[0]
            out.append(patch.reshape(len(patch), -1).cpu().numpy().astype(np.float16))
    return np.concatenate(out)


def extract_vit(family, crop, cfg):
    cfg = resolve(cfg)
    L = load(cfg)
    res = FeatureResult(family)
    short, patch = cfg["short"], L.multiple
    keep = cfg["layers"][-cfg["keep_tiles_last"]:]
    for view in cfg["views"]:
        pooled = {}
        for det in cfg["detectors"]:
            for scale in cfg["tile_scales"] + cfg["whole_scales"]:
                x = inputs_at(crop, det, view, scale, cfg, L)
                s = vit_stats(L, x, cfg)
                nm = PX_NM * scale
                patch_um, field_um = patch * nm / 1000.0, min(x.shape[1:]) * nm / 1000.0
                for b in cfg["layers"]:
                    layer = f"{short}.b{b}"
                    for stat, length in (("cls", field_um), ("reg", field_um), ("pmean", patch_um), ("pstd", patch_um), ("gem", patch_um)):
                        if f"b{b}_{stat}" in s:
                            res.block(det, view, nm, f"b{b}_{stat}", s[f"b{b}_{stat}"].mean(0), length_um=length, layer=layer, tag=TAG)
                    cls, pmean = s[f"b{b}_cls"], s[f"b{b}_pmean"]
                    res.scalar(det, view, nm, f"b{b}_cls_norm", np.linalg.norm(cls, axis=1).mean(), length_um=field_um, layer=layer, tag=TAG)
                    res.scalar(det, view, nm, f"b{b}_patch_norm", s[f"b{b}_pnorm"].mean(), length_um=patch_um, layer=layer, tag=TAG)
                    res.scalar(det, view, nm, f"b{b}_patch_spread", np.sqrt((s[f"b{b}_pstd"] ** 2).sum(1)).mean(),
                               length_um=patch_um, layer=layer, tag=TAG)
                    res.scalar(det, view, nm, f"b{b}_cls_patch_cos", np.mean([_cos(c, p) for c, p in zip(cls, pmean)]),
                               length_um=field_um, layer=layer, tag=TAG)
                    if scale in cfg["tile_scales"]:
                        res.scalar(det, view, nm, f"b{b}_tile_spread", _rms_from_mean(pmean), length_um=field_um, layer=layer, tag=TAG)
                        if scale == cfg["keep_tiles_scale"] and b in keep:
                            res.tile_block(det, view, nm, f"b{b}_pmean_tiles", pmean, length_um=patch_um, layer=layer, tag=TAG)
                    pooled[det, scale, b] = pmean.mean(0)
        _pair_cosines(res, pooled, view, cfg, lambda b: (f"b{b}_pmean_cos", f"{short}.b{b}"), patch)
    grid = cfg.get("token_grid")
    if grid:
        nm = PX_NM * grid["scale"]
        for det in cfg["detectors"]:
            x = cover_tiles(model_input(crop, det, grid["view"], grid["scale"], cfg), cfg["tile_px"])
            tokens = vit_token_grid(L, x, grid["block"], cfg)
            g = x.shape[1] // patch
            name = res._add("tiles", det, grid["view"], nm, f"b{grid['block']}_tokens_{g}x{g}x{tokens.shape[1] // (g * g)}",
                            patch * nm / 1000.0, f"{short}.b{grid['block']}", TAG)
            res.tiles[name] = tokens                      # float16 on purpose: FeatureResult.tile_block would store float32
    return res


def _pair_cosines(res, pooled, view, cfg, naming, unit_px):
    """Cosine between the BSE and the Inlens crop-level vector of every scale and layer (if both detectors ran)."""
    if not all(d in cfg["detectors"] for d in ("BSE", "Inlens")):
        return
    for (det, scale, key), v in pooled.items():
        if det != "BSE":
            continue
        stat, layer = naming(key)
        nm = PX_NM * scale
        stride = unit_px[key] if isinstance(unit_px, dict) else unit_px
        res.scalar(PAIR, view, nm, stat, _cos(v, pooled["Inlens", scale, key]), length_um=stride * nm / 1000.0, layer=layer, tag=TAG)


# ----------------------------------------------------------------------------------------------------
# convolutional networks
# ----------------------------------------------------------------------------------------------------
def _cnn_stages(L, t):
    """The 4 stage outputs (b, c, h, w), float32, finest first."""
    with _autocast(L):
        if L.kind == "timm_cnn":
            out = L.net.forward_intermediates(t, indices=[0, 1, 2, 3], intermediates_only=True)
        else:
            m = L.net
            y = m.maxpool(m.relu(m.bn1(m.conv1(t))))
            out = []
            for stage in (m.layer1, m.layer2, m.layer3, m.layer4):
                y = stage(y)
                out.append(y)
    return [f.float() for f in out]


def cnn_stats(L, x, cfg):
    """x (n, H, W) in 0..1 -> {"st1_mean": (n, c), "st1_std", "st1_gem", "st1_gram": (n, c, c), ...} per input."""
    import torch
    parts = []
    with torch.inference_mode():
        for t in _batches(x, L, cfg):
            per_look = []
            for look in _looks(t, cfg):
                s = {}
                for k, feat in enumerate(_cnn_stages(L, look), 1):
                    f = feat.flatten(2)                                           # (b, c, h * w)
                    s[f"st{k}_mean"] = f.mean(2)
                    s[f"st{k}_std"] = f.std(dim=2, correction=0)
                    s[f"st{k}_gem"] = _gem(f, cfg["gem_p"], 2)
                    if k in cfg["gram_stages"]:
                        s[f"st{k}_gram"] = torch.bmm(f, f.transpose(1, 2)) / f.shape[2]
                per_look.append(s)
            parts.append(_collect(per_look))
    return _stack(parts)


def extract_cnn(family, crop, cfg):
    cfg = resolve(cfg)
    L = load(cfg)
    res = FeatureResult(family)
    short = cfg["short"]
    stride_of = {k: stride for k, stride in enumerate(L.strides, 1)}
    keep = sorted(stride_of)[-cfg["keep_tiles_last"]:]
    for view in cfg["views"]:
        pooled = {}
        for det in cfg["detectors"]:
            for scale in cfg["tile_scales"] + cfg["whole_scales"]:
                x = inputs_at(crop, det, view, scale, cfg, L)
                s = cnn_stats(L, x, cfg)
                nm = PX_NM * scale
                field_um = min(x.shape[1:]) * nm / 1000.0
                for k, stride in stride_of.items():
                    layer, length = f"{short}.st{k}", stride * nm / 1000.0
                    mean, std = s[f"st{k}_mean"], s[f"st{k}_std"]
                    for stat in ("mean", "std", "gem"):
                        res.block(det, view, nm, f"st{k}_{stat}", s[f"st{k}_{stat}"].mean(0), length_um=length, layer=layer, tag=TAG)
                    if k in cfg["gram_stages"]:
                        gram = s[f"st{k}_gram"].mean(0)
                        res.block(det, view, nm, f"st{k}_gram", gram[np.triu_indices(len(gram))], length_um=length, layer=layer, tag=TAG)
                    res.scalar(det, view, nm, f"st{k}_mean_norm", np.linalg.norm(mean, axis=1).mean(), length_um=length, layer=layer, tag=TAG)
                    res.scalar(det, view, nm, f"st{k}_spread", np.sqrt((std ** 2).sum(1)).mean(), length_um=length, layer=layer, tag=TAG)
                    if scale in cfg["tile_scales"]:
                        res.scalar(det, view, nm, f"st{k}_tile_spread", _rms_from_mean(mean), length_um=field_um, layer=layer, tag=TAG)
                        if scale == cfg["keep_tiles_scale"] and k in keep:
                            res.tile_block(det, view, nm, f"st{k}_mean_tiles", mean, length_um=length, layer=layer, tag=TAG)
                    pooled[det, scale, k] = mean.mean(0)
        _pair_cosines(res, pooled, view, cfg, lambda k: (f"st{k}_mean_cos", f"{short}.st{k}"), stride_of)
    return res
