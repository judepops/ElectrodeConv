"""V1, the label-free encoder (checkpoint cnn/processed/v_k7_con02/best.pt), kept for inference only.

One shared encoder runs on each detector image separately (after a per-detector 1x1 gain/bias), the spot embedding
is [bse | inlens | se] of the mean + SD pooled bottleneck (3 x 512 = 1536 for k7). It was trained with a material
map and a cross-detector contrastive loss and never saw a batch label. Training code lives in git history
(commit 3e0261c, cnn/train.py); classify.py only needs the forward pass.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from cnn.common import DETECTORS, N_CLASSES
from cnn.model import Decoder, Encoder, resolve_arch


class V1Net(nn.Module):
    def __init__(self, arch="k7", detectors=DETECTORS, proj_dim=128, with_decoder=True):
        super().__init__()
        a = resolve_arch(arch)
        widths = a["widths"]
        self.detectors = tuple(detectors)
        self.adapters = nn.ModuleDict({d: nn.Conv2d(1, 1, 1) for d in self.detectors})
        self.encoder = Encoder(widths, a["k"], a["stem"], a["dil"])
        self.decoder = Decoder(widths, len(self.detectors), N_CLASSES) if with_decoder else None
        self.feat_dim = 2 * widths[-1]
        self.proj = nn.Sequential(nn.BatchNorm1d(self.feat_dim), nn.Linear(self.feat_dim, widths[-1]), nn.GELU(),
                                  nn.Linear(widths[-1], proj_dim))

    def forward(self, x):
        """x (B, 3, H, W) [bse, inlens, se] -> (B, 3 x feat_dim) spot-ready tile embedding."""
        feats = [self.encoder.pooled(self.encoder(self.adapters[d](x[:, i:i + 1]))[-1]) for i, d in enumerate(self.detectors)]
        return torch.cat(feats, 1)


def load_v1(path, device):
    ck = torch.load(path, map_location="cpu", weights_only=False)
    cfg = ck["config"]
    net = V1Net(cfg.get("arch", "k7"), with_decoder=float(cfg.get("w_seg", 1.0)) > 0)
    net.load_state_dict(ck["model"])
    return net.to(device).eval()
