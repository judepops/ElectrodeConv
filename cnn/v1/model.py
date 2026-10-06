"""Step 2a: the encoder with a segmentation head and a contrastive projection head. Plain torch, no torchvision.

    net = MaterialNet()
    out = net(x)                       # x (B, 3, H, W): [bse, inlens, se]
    out["seg"]                         # (B, 3, H, W) material-map logits
    out["z"]                           # {"bse": (B, 128), "inlens": ..., "se": ...} L2-normalised projections (contrastive)
    out["feat"]                        # {"bse": (B, 2 x last width), ...} pooled bottleneck, mean+std (the embedding)

One shared encoder processes each detector image separately as a 1-channel input, after a per-detector 1x1
adapter. The contrastive loss then compares like with like across detectors; the segmentation decoder sees all
three detectors' features concatenated (U-Net skips).

The encoder's kernel setup is configurable (ARCHS below, `MaterialNet(arch="k5")`): kernel size, a large first-layer
("stem") kernel, dilation in the deeper stages, the number of stages and the width. The default `base` is 3x3
kernels, 5 stages, stride 2 by max-pool: receptive field at the bottleneck > 400 px = the 1-10 um particle scale at
25 nm/px. The decoder always uses 3x3 (it only has to paint the map back).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from cnn.common import DETECTORS, N_CLASSES

WIDTHS = (32, 64, 128, 256, 256)
PROJ_DIM = 128

# Encoder kernel setups compared by sweep.py. Every key is optional (defaults = base).
#   k        kernel size of every encoder conv          stem      kernel of the very first conv (stage 0)
#   dil      dilation of the 2nd conv in each stage     widths    channels per stage (len = number of stages)
ARCHS = {
    "base":     {},                                                     # 3x3 everywhere, 5 stages
    "k5":       {"k": 5},                                               # 5x5 everywhere
    "k7":       {"k": 7},                                               # 7x7 everywhere
    "stem7":    {"stem": 7},                                            # 7x7 first layer, then 3x3
    "dilated":  {"dil": (1, 1, 2, 4, 8)},                               # 3x3, growing dilation: bigger context, same params
    "deep6":    {"widths": (32, 64, 128, 256, 256, 256)},               # one more stage: bottleneck at 1/32
    "shallow4": {"widths": (32, 64, 128, 256)},                         # one fewer: more local texture, smaller context
    "wide":     {"widths": (64, 128, 256, 512, 512)},                   # 3x3, 2x channels
    # ImageNet-pretrained torchvision encoders, fine-tuned (train.py gives the encoder a 10x lower learning rate)
    "resnet18":     {"pretrained": "resnet18"},
    "resnet34":     {"pretrained": "resnet34"},
    "resnet50":     {"pretrained": "resnet50"},
    "convnext_t":   {"pretrained": "convnext_tiny"},
}


def norm(c):
    """GroupNorm: no running statistics, so train and eval behave the same (BatchNorm's running averages take
    hundreds of steps to settle and gave 0.2 held-out accuracy at 0.87 train accuracy in the smoke run)."""
    return nn.GroupNorm(min(8, c), c)


def conv_block(cin, cout, k=3, k_first=None, dil=1):
    """Two convs + GroupNorm + GELU. k_first: kernel of the first conv (stem); dil: dilation of the second."""
    k1 = k_first or k
    return nn.Sequential(
        nn.Conv2d(cin, cout, k1, padding=k1 // 2, bias=False), norm(cout), nn.GELU(),
        nn.Conv2d(cout, cout, k, padding=dil * (k // 2), dilation=dil, bias=False), norm(cout), nn.GELU(),
    )


def resolve_arch(arch):
    """'k5' or a dict -> full dict {k, stem, dil, widths} (or {pretrained} for a torchvision backbone)."""
    a = dict(ARCHS[arch]) if isinstance(arch, str) else dict(arch or {})
    if a.get("pretrained"):
        return {"pretrained": a["pretrained"]}
    widths = tuple(a.get("widths", WIDTHS))
    dil = tuple(a.get("dil", (1,) * len(widths)))
    assert len(dil) == len(widths), "dil needs one entry per stage"
    return {"k": int(a.get("k", 3)), "stem": a.get("stem"), "dil": dil, "widths": widths}


class Encoder(nn.Module):
    """1-channel image -> list of feature maps at strides 1, 2, 4, 8, 16 (last = bottleneck)."""

    def __init__(self, widths=WIDTHS, k=3, stem=None, dil=None):
        super().__init__()
        self.stages = nn.ModuleList()
        dil = dil or (1,) * len(widths)
        cin = 1
        for i, w in enumerate(widths):
            block = conv_block(cin, w, k=k, k_first=stem if i == 0 else None, dil=dil[i])
            self.stages.append(nn.Sequential(nn.MaxPool2d(2) if i else nn.Identity(), block))
            cin = w
        self.out_dim = widths[-1]
        # a pooling projection with no normalisation after it: GroupNorm+GELU right before global average pooling
        # made every tile's pooled vector the same constant (std 6e-5 across tiles in the smoke run), which
        # collapses the contrastive loss to chance. This 1x1 conv sits after the norm, so the pooled descriptor
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


class PretrainedEncoder(nn.Module):
    """A torchvision ImageNet backbone as a multi-scale encoder (same interface as Encoder: list of feature maps,
    `pooled`, `widths`). Input: 3-channel, roughly ImageNet-normalised (MaterialNet's adapters do that)."""

    def __init__(self, name):
        super().__init__()
        import torchvision.models as tvm
        net = getattr(tvm, name)(weights="DEFAULT")
        if name.startswith("resnet"):
            self.blocks = nn.ModuleList([
                nn.Sequential(net.conv1, net.bn1, net.relu),          # stride 2
                nn.Sequential(net.maxpool, net.layer1),               # 4
                net.layer2, net.layer3, net.layer4])                  # 8, 16, 32
            c = [64, 64, 128, 256, 512] if name in ("resnet18", "resnet34") else [64, 256, 512, 1024, 2048]
        elif name.startswith("convnext"):
            f = net.features
            self.blocks = nn.ModuleList([nn.Sequential(f[0], f[1]), nn.Sequential(f[2], f[3]),
                                         nn.Sequential(f[4], f[5]), nn.Sequential(f[6], f[7])])   # 4, 8, 16, 32
            c = [96, 192, 384, 768]
        else:
            raise ValueError(f"no multi-scale recipe for {name}")
        self.widths = tuple(c)
        self.out_dim = c[-1]
        self.pool_proj = nn.Conv2d(c[-1], c[-1], 1)

    def forward(self, x):
        feats = []
        for b in self.blocks:
            x = b(x)
            feats.append(x)
        return feats

    def pooled(self, bottleneck):
        p = self.pool_proj(bottleneck)
        return torch.cat([p.mean(dim=(2, 3)), p.std(dim=(2, 3))], 1)


class Decoder(nn.Module):
    """U-Net decoder over the concatenated (3 detectors) skip features -> class logits at full resolution."""

    def __init__(self, widths=WIDTHS, n_det=len(DETECTORS), n_classes=N_CLASSES):
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


def net_from_config(cfg: dict) -> "MaterialNet":
    """The network a run's config.json describes (arch, and whether it had a material-map decoder: w_seg > 0)."""
    return MaterialNet(cfg.get("arch", "base"), with_decoder=float(cfg.get("w_seg", 1.0)) > 0)


class MaterialNet(nn.Module):
    def __init__(self, arch="base", detectors=DETECTORS, proj_dim=PROJ_DIM, n_classes=N_CLASSES, with_decoder=True):
        """with_decoder=False: contrastive only, no material-map head (the "no material classification" setup)."""
        super().__init__()
        self.arch = resolve_arch(arch)
        self.detectors = tuple(detectors)
        self.pretrained = bool(self.arch.get("pretrained"))
        if self.pretrained:
            # 1 -> 3 channels, initialised to an ImageNet-style normalisation of each detector (BSE is in graphite
            # units 0..~2.6, Inlens / SE in 0..1); learnable afterwards
            self.adapters = nn.ModuleDict({d: nn.Conv2d(1, 3, 1) for d in self.detectors})
            for d, conv in self.adapters.items():
                scale = 1 / 2.6 if d == "bse" else 1.0
                nn.init.constant_(conv.weight, scale / 0.226)
                nn.init.constant_(conv.bias, -0.449 / 0.226)
            self.encoder = PretrainedEncoder(self.arch["pretrained"])
            widths = self.encoder.widths
        else:
            widths = self.arch["widths"]
            self.adapters = nn.ModuleDict({d: nn.Conv2d(1, 1, 1) for d in self.detectors})   # per-detector gain/bias
            self.encoder = Encoder(widths, self.arch["k"], self.arch["stem"], self.arch["dil"])
        self.decoder = Decoder(widths, len(self.detectors), n_classes) if with_decoder else None
        self.feat_dim = 2 * widths[-1]
        # BatchNorm first: at init every tile's pooled vector shares one big common direction, so all z point the
        # same way (cosine 0.997) and NT-Xent sits at ln(batch) for the first ~100 steps (or forever, on short runs).
        # Standardising each feature across the batch removes that common part, so tile differences drive z from step 1.
        self.proj = nn.Sequential(nn.BatchNorm1d(self.feat_dim), nn.Linear(self.feat_dim, widths[-1]), nn.GELU(),
                                  nn.Linear(widths[-1], proj_dim))

    def encode(self, x):
        """x (B, n_det, H, W) -> per-detector skip lists."""
        return {d: self.encoder(self.adapters[d](x[:, i:i + 1])) for i, d in enumerate(self.detectors)}

    def forward(self, x, seg=True):
        skips = self.encode(x)
        feat = {d: self.encoder.pooled(skips[d][-1]) for d in self.detectors}
        z = {d: F.normalize(self.proj(feat[d]), dim=1) for d in self.detectors}
        out = {"feat": feat, "z": z}
        if seg and self.decoder is not None:
            fused = [torch.cat([skips[d][i] for d in self.detectors], 1) for i in range(len(skips[self.detectors[0]]))]
            seg = self.decoder(fused)
            if seg.shape[-2:] != x.shape[-2:]:          # pretrained encoders start at stride 2 or 4
                seg = F.interpolate(seg, size=x.shape[-2:], mode="bilinear", align_corners=False)
            out["seg"] = seg
        return out


def nt_xent(za, zb, temperature=0.1):
    """Symmetric InfoNCE between two L2-normalised views of the same tiles (positives on the diagonal).
    -> (loss, top-1 retrieval accuracy a->b)."""
    logits = za @ zb.t() / temperature
    target = torch.arange(len(za), device=za.device)
    loss = 0.5 * (F.cross_entropy(logits, target) + F.cross_entropy(logits.t(), target))
    acc = (logits.argmax(1) == target).float().mean()
    return loss, acc


def contrastive_loss(z: dict, pairs=(("bse", "inlens"), ("bse", "se"), ("inlens", "se")), temperature=0.1):
    losses, accs = [], {}
    for a, b in pairs:
        if a in z and b in z:
            l, acc = nt_xent(z[a], z[b], temperature)
            losses.append(l)
            accs[f"{a}-{b}"] = acc.item()
    return torch.stack(losses).mean(), accs


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
