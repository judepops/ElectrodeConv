"""Step 2a: the encoder and the material-map decoder that `cnn/supcon.py`'s FusionNet is built from. Plain torch.

    from cnn.model import net_from_config
    net = net_from_config(json.load(open("processed/supcon/v2/full/config.json")))
    out = net(x)                       # x (B, 3, H, W): [bse, inlens, se] as ONE 3-channel image (early fusion)
    out["feat"]                        # (B, 2 x last width) pooled bottleneck, mean + std: the embedding (512 for k7)
    out["z"]                           # (B, 128) L2-normalised projection, what the supervised contrastive loss sees
    out["logits"]                      # (B, 3) batch logits of the cross-entropy head
    out["seg"]                         # (B, 3, H, W) material-map logits, only when the run had a decoder (w_seg > 0)

The encoder's kernel setup is configurable (ARCHS below): kernel size, a large first-layer ("stem") kernel,
dilation in the deeper stages, the number of stages and the width. `base` is 3x3 kernels, 5 stages, stride 2 by
max-pool: receptive field at the bottleneck > 400 px = the 1-10 um particle scale at 25 nm/px. The default run uses
`k7`. The decoder always uses 3x3 (it only has to paint the map back).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from cnn.common import N_CLASSES

WIDTHS = (32, 64, 128, 256, 256)

# Encoder kernel setups (all trained from scratch). Every key is optional (defaults = base).
#   k        kernel size of every encoder conv          stem      kernel of the very first conv (stage 0)
#   dil      dilation of the 2nd conv in each stage     widths    channels per stage (len = number of stages)
ARCHS = {
    "base":     {},                                                     # 3x3 everywhere, 5 stages
    "k5":       {"k": 5},                                               # 5x5 everywhere
    "k7":       {"k": 7},                                               # 7x7 everywhere (the default)
    "stem7":    {"stem": 7},                                            # 7x7 first layer, then 3x3
    "dilated":  {"dil": (1, 1, 2, 4, 8)},                               # 3x3, growing dilation: bigger context, same params
    "deep6":    {"widths": (32, 64, 128, 256, 256, 256)},               # one more stage: bottleneck at 1/32
    "shallow4": {"widths": (32, 64, 128, 256)},                         # one fewer: more local texture, smaller context
    "wide":     {"widths": (64, 128, 256, 512, 512)},                   # 3x3, 2x channels
}


def norm(c):
    """GroupNorm: no running statistics, so train and eval behave the same (BatchNorm's running averages take
    hundreds of steps to settle and gave 0.2 held-out accuracy at 0.87 train accuracy in an early smoke run)."""
    return nn.GroupNorm(min(8, c), c)


def conv_block(cin, cout, k=3, k_first=None, dil=1):
    """Two convs + GroupNorm + GELU. k_first: kernel of the first conv (stem); dil: dilation of the second."""
    k1 = k_first or k
    return nn.Sequential(
        nn.Conv2d(cin, cout, k1, padding=k1 // 2, bias=False), norm(cout), nn.GELU(),
        nn.Conv2d(cout, cout, k, padding=dil * (k // 2), dilation=dil, bias=False), norm(cout), nn.GELU(),
    )


def resolve_arch(arch):
    """'k5' or a dict -> full dict {k, stem, dil, widths}."""
    a = dict(ARCHS[arch]) if isinstance(arch, str) else dict(arch or {})
    widths = tuple(a.get("widths", WIDTHS))
    dil = tuple(a.get("dil", (1,) * len(widths)))
    assert len(dil) == len(widths), "dil needs one entry per stage"
    return {"k": int(a.get("k", 3)), "stem": a.get("stem"), "dil": dil, "widths": widths}


class Encoder(nn.Module):
    """(B, in_ch, H, W) image -> list of feature maps at strides 1, 2, 4, 8, 16 (last = bottleneck)."""

    def __init__(self, widths=WIDTHS, k=3, stem=None, dil=None, in_ch=1):
        super().__init__()
        self.stages = nn.ModuleList()
        dil = dil or (1,) * len(widths)
        cin = in_ch                                   # 3 for early fusion (the three detectors as channels)
        for i, w in enumerate(widths):
            block = conv_block(cin, w, k=k, k_first=stem if i == 0 else None, dil=dil[i])
            self.stages.append(nn.Sequential(nn.MaxPool2d(2) if i else nn.Identity(), block))
            cin = w
        self.out_dim = widths[-1]
        # a pooling projection with no normalisation after it: GroupNorm+GELU right before global average pooling
        # made every tile's pooled vector the same constant (std 6e-5 across tiles in a smoke run), which
        # collapses a contrastive loss to chance. This 1x1 conv sits after the norm, so the pooled descriptor
        # can differ between tiles.
        self.pool_proj = nn.Conv2d(widths[-1], widths[-1], 1)

    def forward(self, x):
        feats = []
        for s in self.stages:
            x = s(x)
            feats.append(x)
        return feats

    def pooled(self, bottleneck):
        """(B, C, h, w) -> (B, 2C): spatial mean and std of the projected bottleneck (tile identity survives pooling)."""
        p = self.pool_proj(bottleneck)
        return torch.cat([p.mean(dim=(2, 3)), p.std(dim=(2, 3))], 1)


class Decoder(nn.Module):
    """U-Net decoder over the encoder's skip features -> class logits at full resolution. `n_det` > 1 means the
    skips are `n_det` encoders' features concatenated (1 for FusionNet)."""

    def __init__(self, widths=WIDTHS, n_det=1, n_classes=N_CLASSES):
        super().__init__()
        ws = [w * n_det for w in widths]
        self.ups = nn.ModuleList()
        cin = ws[-1]
        for w in reversed(ws[:-1]):
            self.ups.append(conv_block(cin + w, w // n_det))
            cin = w // n_det
        self.head = nn.Conv2d(cin, n_classes, 1)

    def forward(self, skips):                   # skips: list over stages of (B, C*n_det, h, w)
        x = skips[-1]
        for up, skip in zip(self.ups, reversed(skips[:-1])):
            x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
            x = up(torch.cat([x, skip], 1))
        return self.head(x)


def net_from_config(cfg: dict):
    """The FusionNet a run's config.json describes (arch, and whether it had a material-map decoder: w_seg > 0)."""
    from cnn.supcon import FusionNet                # lazy: supcon.py imports this module
    return FusionNet(cfg.get("arch", "k7"), with_decoder=float(cfg.get("w_seg", 0)) > 0)


def seg_metrics(logits, target, n_classes=N_CLASSES):
    """-> (pixel accuracy, mean IoU over classes present in target)."""
    pred = logits.argmax(1)
    acc = (pred == target).float().mean().item()
    ious = []
    for c in range(n_classes):
        t, p = target == c, pred == c
        union = (t | p).sum().item()
        if t.sum().item():
            ious.append((t & p).sum().item() / max(union, 1))
    return acc, float(sum(ious) / max(len(ious), 1))
