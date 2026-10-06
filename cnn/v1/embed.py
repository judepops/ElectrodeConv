"""Step 3: embeddings for every tile and every spot from a trained checkpoint.

    python cnn/v1/embed.py --name run1 [--ckpt best.pt] [--maps 12]
Writes cnn/processed/<name>/embeddings.npz:
    tile_feat  (n_tiles, 3 x feat_dim)   pooled bottleneck features, [bse | inlens | se]   <- the embedding
    tile_z     (n_tiles, 3 x 128)        the L2-normalised contrastive projections, same order
    tile_batch, tile_sample_id, tile_session, tile_row, tile_col
    site_feat  (n_spots, 3 x feat_dim)   mean over the spot's tiles; site_z likewise
    batch, sample_id, session             spot rows, sorted by (batch, sample_id) (the order downstream scoring expects)
and <name>/maps/<batch>_<id>_rRcCC.png: BSE | target map | predicted map for a few tiles (sanity / demo).
Full 512 x 512 tiles, no augmentation, eval mode.
"""
from __future__ import annotations

import os as _os
_os.environ.setdefault("LOSSLARP_MASKS", "harmonise")   # the masks V1 was trained on; seg3 also works
import argparse
import sys
from pathlib import Path

import os

import numpy as np

os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")   # cap Apple-GPU memory (see train.py)
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cnn.common import DETECTORS, pick_device, run_dir  # noqa: E402
from cnn.v1.data import TileDataset, collate, tile_index  # noqa: E402
from cnn.v1.model import net_from_config  # noqa: E402

PALETTE = np.array([[0, 0, 0], [120, 120, 120], [255, 200, 0]], np.uint8)   # pore black, graphite grey, Si yellow


def save_map_png(path, bse, target, pred):
    from PIL import Image
    g = np.clip(bse / 2.6, 0, 1)
    img = np.concatenate([np.stack([g, g, g], -1) * 255, PALETTE[target], PALETTE[pred]], 1).astype(np.uint8)
    Image.fromarray(img).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--ckpt", default="best.pt")
    ap.add_argument("--batch", type=int, default=2, help="full 512 x 512 tiles: 2 fits ~3.5 GB on a 16 GB Mac")
    ap.add_argument("--maps", type=int, default=12, help="how many example map PNGs to write")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()
    device = pick_device(a.device)
    out = run_dir(a.name)
    ck = torch.load(out / a.ckpt, map_location="cpu", weights_only=False)
    net = net_from_config(ck["config"]).to(device)
    net.load_state_dict(ck["model"])
    net.eval()
    idx = tile_index()
    dl = DataLoader(TileDataset(idx, augment=False), a.batch, shuffle=False, num_workers=a.workers, collate_fn=collate)
    feats, zs, infos = [], [], []
    (out / "maps").mkdir(exist_ok=True)
    map_every = max(1, len(idx) // max(a.maps, 1))
    n_seen = 0
    with torch.no_grad():
        for x, y, info in dl:
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                o = net(x.to(device))
            feats.append(torch.cat([o["feat"][d] for d in DETECTORS], 1).float().cpu().numpy())
            zs.append(torch.cat([o["z"][d] for d in DETECTORS], 1).float().cpu().numpy())
            infos += info
            pred = o["seg"].argmax(1).cpu().numpy() if "seg" in o else None   # no decoder: contrastive-only run
            for j in range(len(x)):
                if pred is not None and (n_seen + j) % map_every == 0:
                    i = info[j]
                    save_map_png(out / "maps" / f"{i['batch']}_{i['sample_id']}_r{i['row']}c{i['col']:02d}.png",
                                 x[j, 0].numpy(), y[j].numpy(), pred[j])
            n_seen += len(x)
            print(f"\r{n_seen}/{len(idx)} tiles", end="", flush=True)
    print()
    tile_feat, tile_z = np.concatenate(feats), np.concatenate(zs)
    tb = np.array([i["batch"] for i in infos])
    ts = np.array([i["sample_id"] for i in infos])
    tsess = np.array([i["session"] for i in infos], np.int32)
    spots = sorted(set(zip(tb, ts)))
    site_feat = np.stack([tile_feat[(tb == b) & (ts == s)].mean(0) for b, s in spots])
    site_z = np.stack([tile_z[(tb == b) & (ts == s)].mean(0) for b, s in spots])
    sess = np.array([tsess[(tb == b) & (ts == s)][0] for b, s in spots], np.int32)
    np.savez(out / "embeddings.npz", tile_feat=tile_feat, tile_z=tile_z, tile_batch=tb, tile_sample_id=ts,
             tile_session=tsess, tile_row=np.array([i["row"] for i in infos], np.int16),
             tile_col=np.array([i["col"] for i in infos], np.int16), site_feat=site_feat, site_z=site_z,
             batch=np.array([b for b, _ in spots]), sample_id=np.array([s for _, s in spots]), session=sess,
             ckpt=np.array(a.ckpt), epoch=np.array(ck.get("epoch", -1)))
    print(f"wrote {out / 'embeddings.npz'}: tile_feat {tile_feat.shape}, site_feat {site_feat.shape}, "
          f"{len(list((out / 'maps').glob('*.png')))} map PNGs (checkpoint epoch {ck.get('epoch')})")


if __name__ == "__main__":
    main()
