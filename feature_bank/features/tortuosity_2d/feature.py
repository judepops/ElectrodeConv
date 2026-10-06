"""tortuosity_2d: 2D tortuosity factor of the solid phase, through-plane (vertical) and in-plane (horizontal).

Ledger: ledger/entries/tortuosity_2d.yaml. Image: harmonised BSE masks from features/_common (void vs solid).
Columns (dimensionless, 1 = straight paths):
    tortuosity_2d_solid_tau_y        through-plane (top -> bottom; the current collector is at the bottom)
    tortuosity_2d_solid_tau_x        in-plane (left -> right)
    tortuosity_2d_solid_anisotropy   tau_y / tau_x, median over tiles (> 1 = harder to cross the coating)

Method: cut the harmonised crop into square tiles, average-pool by `scale` and re-threshold, solve steady-state
diffusion (Laplace, 4-neighbour finite volumes) through the solid with c = 1 on one face, c = 0 on the opposite
face and no flux elsewhere, keep only solid clusters touching both faces, then tau = solid fraction / (D_eff / D),
TauFactor's definition. Report the median over tiles.

Why the solid and not the pores: at ~10 % porosity the pore phase never spans a tile in 2D (it is connected in
3D, through the slice), so 2D ionic tortuosity is infinite everywhere and says nothing. The solid's tortuosity is
set by how the pores are shaped and oriented: flat, horizontally elongated pores (calendering aligns flakes and
squashes pores) block vertical paths more than horizontal ones, so the anisotropy is a 2D proxy for the
through-plane tortuosity anisotropy that limits rate capability in 3D (Ebner et al. 2014). Always label it 2D.
"""
import numpy as np
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

from features import feature, load_config
from features._common.harmonise import harmonised

CFG = load_config(__file__)


def tau_top_bottom(phase):
    """Tortuosity factor of `phase` (bool, True conducts) from row 0 to the last row. inf if nothing spans."""
    h, w = phase.shape
    labels, _ = ndi.label(phase)
    spanning = np.intersect1d(labels[0][labels[0] > 0], labels[-1][labels[-1] > 0])
    if spanning.size == 0:
        return np.inf
    keep = np.isin(labels, spanning)
    idx = np.full(phase.shape, -1)
    idx[keep] = np.arange(keep.sum())
    vert, horiz = keep[:-1] & keep[1:], keep[:, :-1] & keep[:, 1:]
    a = np.concatenate([idx[:-1][vert], idx[:, :-1][horiz]])          # every conducting link, once
    b = np.concatenate([idx[1:][vert], idx[:, 1:][horiz]])
    n = int(keep.sum())
    degree = np.bincount(np.concatenate([a, b]), minlength=n)
    lap = coo_matrix((np.concatenate([-np.ones(2 * len(a)), degree]),
                      (np.concatenate([a, b, np.arange(n)]), np.concatenate([b, a, np.arange(n)]))), shape=(n, n)).tocsr()
    row = np.broadcast_to(np.arange(h)[:, None], phase.shape)[keep]
    fixed = (row == 0) | (row == h - 1)
    c = (row == 0).astype(float)                                      # c = 1 on top, 0 on bottom
    free = ~fixed
    c[free] = spsolve(lap[free][:, free].tocsc(), -lap[free][:, fixed] @ c[fixed])
    first = vert[0]                                                   # links between row 0 and row 1
    flux = float((c[idx[0][first]] - c[idx[1][first]]).sum())
    open_flux = w / (h - 1)                                           # same tile, all conducting
    return float(phase.mean() / (flux / open_flux)) if flux > 0 else np.inf


def pooled(mask, f):
    h, w = mask.shape[0] // f * f, mask.shape[1] // f * f
    return mask[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3)) >= 0.5


@feature
def tortuosity_2d(sample):
    solid = pooled(harmonised(sample).solid, CFG["scale"])
    side = solid.shape[0]                                             # square tiles, full crop height
    taus = []
    for x in range(0, solid.shape[1] - side + 1, side):
        tile = solid[:, x:x + side]
        taus.append((tau_top_bottom(tile), tau_top_bottom(tile.T)))
    ty, tx = np.array(taus).T
    ok = np.isfinite(ty) & np.isfinite(tx)
    if not ok.any():
        return {"solid_tau_y": np.nan, "solid_tau_x": np.nan, "solid_anisotropy": np.nan}
    return {"solid_tau_y": float(np.median(ty[ok])), "solid_tau_x": float(np.median(tx[ok])),
            "solid_anisotropy": float(np.median(ty[ok] / tx[ok]))}
