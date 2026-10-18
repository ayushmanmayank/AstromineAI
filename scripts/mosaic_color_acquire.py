"""
Global-mosaic dataset v2, Stage 1 (Gate C): record real sha256/size for
the real FC2 color-filter mosaics already downloaded to
datasets/mosaic/raw/fc_color/ (F3/F4/F5 -- see
ml/data/mosaic_color_reader.py and scripts/mosaic_color_check.py for
why these three and not F5/F7/F8, an initial, wrong assumption caught
before being relied on). Writes
datasets/mosaic/manifests/color_acquisition_manifest.json -- a new,
separate manifest; final/mosaic-dataset's own acquisition_manifest.json
is left untouched.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_color_reader import read_center_filter_wavelength_nm  # noqa: E402

COLOR_DIR = Path("datasets/mosaic/raw/fc_color")
FILES = {
    "F3": "VE_HAMO_00N_330E_CYL_FILT3.IMG",
    "F4": "VE_HAMO_00N_330E_CYL_FILT4.IMG",
    "F5": "VE_HAMO_00N_330E_CYL_FILT5.IMG",
}
SOURCE_URL_TEMPLATE = "https://sbnarchive.psi.edu/pds3/dawn/fc/DWNVFC2_2/DATA/HAMO_COLOR/{fname}"
OUT_PATH = Path("datasets/mosaic/manifests/color_acquisition_manifest.json")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    entries = {}
    for name, fname in FILES.items():
        path = COLOR_DIR / fname
        if not path.exists():
            print(f"MISSING: {path} -- run the download first")
            return 1
        size = path.stat().st_size
        sha = sha256_of(path)
        wave = read_center_filter_wavelength_nm(path)
        entries[name] = {
            "filename": fname,
            "url": SOURCE_URL_TEMPLATE.format(fname=fname),
            "size_bytes": size,
            "sha256": sha,
            "center_wavelength_nm": wave,
        }
        print(f"{name}: {fname} size={size} sha256={sha} wavelength={wave:.0f}nm")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset": "DAWN-A-FC2-5-MOSAIC-V1.0",
        "volume": "DWNVFC2_2",
        "description": "Dawn FC2 High Level (2/3) Vesta Encounter Mosaics, real cylindrical "
                        "color-filter global mosaics (F3/F4/F5), used for Stage 1 Gate C's "
                        "color-ratio confound screen.",
        "files": entries,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\nWrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
