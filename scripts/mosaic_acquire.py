"""
Global-mosaic dataset, Stage 1 (GATE A): acquisition + manifest.

Downloads (if not already present) the real FC global mosaic (USGS
Astrogeology) and the real VIR derived band-parameter global mosaics
(PDS Small Bodies Node), then writes a manifest recording the exact real
URL, byte size, and sha256 of each file -- the only acquisition artifact
committed to git (the actual raster files live under datasets/mosaic/,
which is gitignored, per this task's explicit instruction).

Real sources, verified live before being hardcoded here (see
docs/handoff/STATUS.md's session entry and docs/FINAL_REPORT.md's
"Global-mosaic experiment" section for the full verification account):

  FC (USGS Astrogeology Vesta Dawn FC HAMO Global Mosaic, 74 ppd):
    https://planetarymaps.usgs.gov/mosaic/Vesta_Dawn_FC_HAMO_Mosaic_Global_74ppd.tif
    Simple cylindrical, positive-east, -180..180, 74.1778 px/deg, 8-bit.
    Per USGS's own map page: shifted 150 deg eastward from the original
    Dawn-Claudia file so Claudia crater sits at 146E, to align with the
    IAU-approved "Claudia Double Prime" (== SPICE Vesta body-fixed
    rotating) frame -- i.e. this file's own longitude VALUES are already
    real Claudia-Double-Prime/SPICE longitudes, not an independent scale.

  VIR (PDS Small Bodies Node, DAWN-A-VIR-5-DDR-MOSAIC-V1.0, "Dawn VIR
  Derived Vesta Global Mosaics V1.0"): 4 self-labeled PDS3 .IMG rasters
  (Band I/II center + depth), equirectangular, planetocentric,
  positive-east, CENTER_LONGITUDE=180 in the label's own 0-360 scale,
  ~44.506 px/deg, 32-bit float, nodata -1e32 (CORE_NULL 0xFF7FFFFB and
  sibling saturation-constant bit patterns). The volume's own CATALOG
  (VIR_DDR_VESTA_MOSAICS_DS.CAT) states explicitly: "The maps are
  centered at latitude 0.0 and longitude 330.0 in the IAU-compliant
  Claudia double prime system. This corresponds to 180.0 longitude in
  the system used in publications" -- i.e. the label's own longitude
  values are offset from the real Claudia-Double-Prime/SPICE frame (the
  same frame the FC file is already expressed in) by a real, documented
  150-degree shift: claudia_lon = (label_lon + 150) mod 360. This is
  checked empirically, not just trusted, in scripts/mosaic_crater_check.py.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import NamedTuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
MOSAIC_DIR = REPO_ROOT / "datasets" / "mosaic"
RAW_FC_DIR = MOSAIC_DIR / "raw" / "fc"
RAW_VIR_DIR = MOSAIC_DIR / "raw" / "vir"
MANIFEST_PATH = REPO_ROOT / "datasets" / "mosaic" / "manifests" / "acquisition_manifest.json"


class SourceFile(NamedTuple):
    url: str
    local_path: Path
    note: str


FC_SOURCES = [
    SourceFile(
        url="https://planetarymaps.usgs.gov/mosaic/Vesta_Dawn_FC_HAMO_Mosaic_Global_74ppd.tif",
        local_path=RAW_FC_DIR / "Vesta_Dawn_FC_HAMO_Mosaic_Global_74ppd.tif",
        note="USGS Astrogeology FC HAMO global mosaic, 74.1778 px/deg, simple cylindrical, "
             "positive-east -180..180, Claudia-Double-Prime-aligned (Claudia crater at 146E).",
    ),
]

VIR_BASE = "https://sbnarchive.psi.edu/pds3/dawn/vir/DWNVVIR_2/DATA/"
VIR_SOURCES = [
    SourceFile(
        url=VIR_BASE + fname,
        local_path=RAW_VIR_DIR / fname,
        note=f"DAWN-A-VIR-5-DDR-MOSAIC-V1.0 ({desc}), self-labeled PDS3 IMG, "
             "equirectangular, planetocentric, positive-east, CENTER_LONGITUDE=180 (label scale).",
    )
    for fname, desc in [
        ("VMT_MOSAIC-BI_CENTER_1.IMG", "Band I center"),
        ("VMT_MOSAIC-BI_DEPTH_1.IMG", "Band I depth"),
        ("VMT_MOSAIC-BII_CENTER_1.IMG", "Band II center"),
        ("VMT_MOSAIC-BII_DEPTH_1.IMG", "Band II depth"),
    ]
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(source: SourceFile, timeout: int = 600) -> None:
    source.local_path.parent.mkdir(parents=True, exist_ok=True)
    if source.local_path.exists():
        print(f"Already have {source.local_path}, skipping download.")
        return
    print(f"Downloading {source.url} -> {source.local_path}")
    with requests.get(source.url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with open(source.local_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)


def build_manifest(sources: list[SourceFile]) -> list[dict]:
    entries = []
    for source in sources:
        if not source.local_path.exists():
            entries.append({
                "url": source.url,
                "local_path": str(source.local_path.relative_to(REPO_ROOT)),
                "status": "MISSING",
                "note": source.note,
            })
            continue
        size = source.local_path.stat().st_size
        digest = _sha256(source.local_path)
        entries.append({
            "url": source.url,
            "local_path": str(source.local_path.relative_to(REPO_ROOT)),
            "size_bytes": size,
            "sha256": digest,
            "status": "OK",
            "note": source.note,
        })
        print(f"{source.local_path.name}: {size} bytes, sha256={digest}")
    return entries


def main() -> int:
    for source in FC_SOURCES + VIR_SOURCES:
        download(source)

    manifest = {
        "fc_mosaic": build_manifest(FC_SOURCES),
        "vir_mosaics": build_manifest(VIR_SOURCES),
    }

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\nWrote manifest to {MANIFEST_PATH}")

    any_missing = any(e["status"] == "MISSING" for group in manifest.values() for e in group)
    if any_missing:
        print("\nGATE A: FAIL -- one or more real sources could not be acquired. See manifest for details.")
        return 1
    print("\nGATE A: PASS -- all real sources acquired and checksummed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
