"""
Global-mosaic dataset, Stage 3: tile the FC mosaic, label each tile from
the real VIR Band I center raster, and assign region-block splits.

Real, documented rules (fixed here, not tuned after seeing results):
  - Tile size: 224x224 px at FC's native 74.1778 px/deg resolution
    (~3.0213 deg per side) -- one scale, as this task's "e.g." permits;
    a second scale is flagged as a documented future option, not
    pursued here (see docs/mosaic_experiment_log.md).
  - Drop a tile if > 20% of its real FC pixels are nodata (FC
    nodata=0 -- confirmed via rasterio, see ml/data/mosaic_reader.py).
  - Label = majority real VIR label-class within the tile's real
    footprint (both mosaics are true equirectangular/plate-carree on the
    same sphere, so a rectangular FC tile maps to an exact rectangular
    window in VIR pixel space -- only the 2 opposite corners need
    converting, not every pixel). Drop a tile if < 60% of its covering
    VIR label pixels agree on the majority class ("low label purity") --
    60% is a real majority with a margin, not a bare ~34% plurality a
    3-class near-tie could produce; not tuned to any later result.
  - Region-block (20 deg) split, with a one-tile buffer: any tile whose
    center falls within one tile-width of a block boundary is dropped
    entirely (assigned to no split), per ml/utils/mosaic_splits.py.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_labels import CLASS_NAMES, classify_band1_center  # noqa: E402
from ml.data.mosaic_reader import fc_pixel_to_lonlat, open_fc_mosaic, read_vir_mosaic, vir_lonlat_to_pixel  # noqa: E402
from ml.utils.mosaic_splits import MIN_BLOCK_SIZE_DEG, assign_block_splits, is_buffered_out, region_block_for  # noqa: E402

FC_PATH = "datasets/mosaic/raw/fc/Vesta_Dawn_FC_HAMO_Mosaic_Global_74ppd.tif"
VIR_BI_CENTER_PATH = "datasets/mosaic/raw/vir/VMT_MOSAIC-BI_CENTER_1.IMG"
TILES_DIR = Path("datasets/mosaic/tiles")
MANIFEST_PATH = Path("datasets/mosaic/manifests/tile_manifest.csv")

TILE_PX = 224
NODATA_FRAC_MAX = 0.20
LABEL_PURITY_MIN = 0.60
BLOCK_SIZE_DEG = MIN_BLOCK_SIZE_DEG  # 20 deg, the minimum this experiment's rules allow
SPLIT_SEED = 42


def main() -> int:
    print("Loading real FC mosaic (full array)...")
    fc_meta, fc_ds = open_fc_mosaic(FC_PATH)
    fc_array = fc_ds.read(1)
    fc_ds.close()

    tile_size_deg = TILE_PX / 74.1778  # real FC resolution, not re-derived per tile
    print(f"Tile size: {TILE_PX}px = {tile_size_deg:.4f} deg/side")

    print("Loading real VIR Band I center mosaic + classifying every valid pixel...")
    vir_mosaic = read_vir_mosaic(VIR_BI_CENTER_PATH)
    vir_labels = classify_band1_center(vir_mosaic.data)  # int8, -1 = nodata

    n_rows = fc_meta.height // TILE_PX
    n_cols = fc_meta.width // TILE_PX
    print(f"Candidate tile grid: {n_rows} x {n_cols} = {n_rows * n_cols} tiles")

    records = []
    dropped = {"nodata": 0, "no_vir_coverage": 0, "low_purity": 0}
    kept_tiles = []  # (row0, col0, label, purity, center_lat, center_lon)

    for ti in range(n_rows):
        row0 = ti * TILE_PX
        for tj in range(n_cols):
            col0 = tj * TILE_PX
            fc_tile = fc_array[row0:row0 + TILE_PX, col0:col0 + TILE_PX]
            nodata_frac = float((fc_tile == 0).mean())
            if nodata_frac > NODATA_FRAC_MAX:
                dropped["nodata"] += 1
                continue

            lon_a, lat_a = fc_pixel_to_lonlat(fc_meta, float(row0), float(col0))
            lon_b, lat_b = fc_pixel_to_lonlat(fc_meta, float(row0 + TILE_PX), float(col0 + TILE_PX))
            center_lon, center_lat = fc_pixel_to_lonlat(fc_meta, row0 + TILE_PX / 2.0, col0 + TILE_PX / 2.0)

            line_a, sample_a = vir_lonlat_to_pixel(vir_mosaic.label, lon_a, lat_a)
            line_b, sample_b = vir_lonlat_to_pixel(vir_mosaic.label, lon_b, lat_b)
            l0, l1 = sorted((int(round(line_a)), int(round(line_b))))
            s0, s1 = sorted((int(round(sample_a)), int(round(sample_b))))
            l0, l1 = max(0, l0), min(vir_mosaic.label.lines, max(l1, l0 + 1))
            s0, s1 = max(0, s0), min(vir_mosaic.label.samples, max(s1, s0 + 1))

            vir_window = vir_labels[l0:l1, s0:s1]
            valid = vir_window[vir_window >= 0]
            if valid.size == 0:
                dropped["no_vir_coverage"] += 1
                continue

            counts = np.bincount(valid, minlength=len(CLASS_NAMES))
            majority_label = int(counts.argmax())
            purity = float(counts[majority_label] / valid.size)
            if purity < LABEL_PURITY_MIN:
                dropped["low_purity"] += 1
                continue

            kept_tiles.append((row0, col0, majority_label, purity, center_lat, center_lon, nodata_frac, valid.size))

    print(f"\nKept {len(kept_tiles)} tiles; dropped {dropped}")

    # Real region-block split, with buffer -- applied to the KEPT tiles only.
    blocks_for_split = []
    buffered_flags = []
    for (_, _, _, _, lat, lon, _, _) in kept_tiles:
        buffered_flags.append(is_buffered_out(lat, lon % 360.0, BLOCK_SIZE_DEG, tile_size_deg))
        blocks_for_split.append(region_block_for(lat, lon, BLOCK_SIZE_DEG))

    non_buffered_blocks = [b for b, buf in zip(blocks_for_split, buffered_flags) if not buf]
    split_map = assign_block_splits(non_buffered_blocks, 0.70, 0.15, 0.15, seed=SPLIT_SEED)

    n_buffered_out = sum(buffered_flags)
    print(f"Buffered out (within one tile-width of a block boundary): {n_buffered_out} tiles")

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    class_split_counts: dict[tuple[str, str], int] = {}
    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tile_id", "row0", "col0", "label", "label_name", "label_purity",
                          "center_lat", "center_lon", "nodata_frac", "region_block_lat", "region_block_lon", "split", "path"])
        for idx, ((row0, col0, label, purity, lat, lon, nodata_frac, n_valid), block, buffered) in enumerate(
            zip(kept_tiles, blocks_for_split, buffered_flags)
        ):
            if buffered:
                split = "buffered_out"
            else:
                split = split_map[block]

            tile_id = f"tile_{idx:05d}"
            out_path = TILES_DIR / split / CLASS_NAMES[label] / f"{tile_id}.png"
            if split != "buffered_out":
                out_path.parent.mkdir(parents=True, exist_ok=True)
                fc_tile = fc_array[row0:row0 + TILE_PX, col0:col0 + TILE_PX]
                Image.fromarray(fc_tile).save(out_path)
                class_split_counts[(split, CLASS_NAMES[label])] = class_split_counts.get((split, CLASS_NAMES[label]), 0) + 1

            writer.writerow([tile_id, row0, col0, label, CLASS_NAMES[label], f"{purity:.4f}",
                              f"{lat:.6f}", f"{lon:.6f}", f"{nodata_frac:.4f}", block.lat_block, block.lon_block,
                              split, str(out_path) if split != "buffered_out" else ""])

    print(f"\nWrote real tile manifest to {MANIFEST_PATH} ({len(kept_tiles)} rows)")
    print("\nReal class counts per split:")
    for split in ("train", "val", "test"):
        counts = {name: class_split_counts.get((split, name), 0) for name in CLASS_NAMES}
        total = sum(counts.values())
        print(f"  {split}: total={total} {counts}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
