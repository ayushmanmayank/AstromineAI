"""
Global-mosaic dataset: readers for the real FC (USGS GeoTIFF) and VIR
(PDS3 self-labeled .IMG) global mosaics, plus the coordinate-transform
helpers used to cross-check their longitude conventions against each
other (see scripts/mosaic_crater_check.py).

Both real formats were inspected directly before writing this (not
assumed): FC is an 8-bit GeoTIFF with an embedded planetary CRS
(SimpleCylindrical Vesta, equirectangular, central_meridian=0, sphere
radius 255000 m); VIR is a self-labeled PDS3 image (label attached as
the file's own first record) with 32-bit big-endian IEEE float samples
(confirmed empirically: big-endian gives physically sane 0.91-0.96 um
Band I center values and an exact match to the label's own
MISSING_CONSTANT=-1e32 nodata sentinel; little-endian gives garbage).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import rasterio
except ImportError:  # pragma: no cover - rasterio is a hard requirement for FC reading
    rasterio = None


# --------------------------------------------------------------------------
# VIR: self-labeled PDS3 .IMG mosaics
# --------------------------------------------------------------------------

_KV_RE = re.compile(r"(?m)^\s*([A-Z_0-9]+)\s*=\s*(.+?)\s*$")


def _parse_pds3_label(text: str) -> dict:
    """Minimal flat key/value parser for this project's self-labeled PDS3
    mosaic files -- good enough for the scalar fields these rasters use
    (nested OBJECT/END_OBJECT blocks are not modeled; later duplicate
    keys inside IMAGE_MAP_PROJECTION, e.g. a second occurrence of a name
    already seen in the outer label, simply overwrite, which is fine here
    since none of the keys this module reads collide across blocks)."""
    values: dict[str, str] = {}
    for match in _KV_RE.finditer(text):
        key, raw = match.group(1), match.group(2).strip()
        raw = raw.strip('"')
        # strip a trailing unit comment like "<degree>" or "<pixel/degree>"
        raw = re.sub(r"<[^>]*>\s*$", "", raw).strip()
        values[key] = raw
    return values


@dataclass
class Pds3MosaicLabel:
    label_records: int
    record_bytes: int
    lines: int
    samples: int
    sample_bits: int
    sample_type: str
    missing_constant: float
    map_resolution_px_per_deg: float
    center_longitude_deg: float
    center_latitude_deg: float
    line_projection_offset_px: float
    sample_projection_offset_px: float
    description: str

    @classmethod
    def parse(cls, text: str) -> "Pds3MosaicLabel":
        v = _parse_pds3_label(text)
        return cls(
            label_records=int(v["LABEL_RECORDS"]),
            record_bytes=int(v["RECORD_BYTES"]),
            lines=int(v["LINES"]),
            samples=int(v["LINE_SAMPLES"]),
            sample_bits=int(v["SAMPLE_BITS"]),
            sample_type=v["SAMPLE_TYPE"],
            missing_constant=float(v["MISSING_CONSTANT"]),
            map_resolution_px_per_deg=float(v["MAP_RESOLUTION"]),
            center_longitude_deg=float(v["CENTER_LONGITUDE"]),
            center_latitude_deg=float(v["CENTER_LATITUDE"]),
            line_projection_offset_px=float(v["LINE_PROJECTION_OFFSET"]),
            sample_projection_offset_px=float(v["SAMPLE_PROJECTION_OFFSET"]),
            description=v.get("DESCRIPTION", ""),
        )


@dataclass
class VirMosaic:
    label: Pds3MosaicLabel
    data: np.ndarray  # (lines, samples) float32, NaN where nodata
    path: Path


def read_vir_mosaic(path: str | Path) -> VirMosaic:
    path = Path(path)
    with open(path, "rb") as fh:
        header = fh.read(64096)  # real RECORD_BYTES for these 4 files, read generically below
        label_text = header.decode("ascii", errors="replace")
        label = Pds3MosaicLabel.parse(label_text)
        fh.seek(label.label_records * label.record_bytes)
        raw = fh.read(label.lines * label.samples * (label.sample_bits // 8))

    dtype = {(32, "IEEE_REAL"): ">f4"}.get((label.sample_bits, label.sample_type))
    if dtype is None:
        raise ValueError(f"Unsupported VIR mosaic sample format: {label.sample_bits}-bit {label.sample_type}")

    arr = np.frombuffer(raw, dtype=dtype).reshape(label.lines, label.samples).astype(np.float32)
    # Real nodata/saturation sentinels: MISSING_CONSTANT plus the 4 special
    # bit-pattern floats the label also declares (CORE_NULL and the 4
    # saturation constants) -- all of these decode to NaN or a value very
    # close to -1e32/+1e32 when read as IEEE_REAL, so a tolerant comparison
    # against the documented MISSING_CONSTANT catches the real nodata cells.
    nodata_mask = ~np.isfinite(arr) | (np.abs(arr - label.missing_constant) < 1.0) | (np.abs(arr) > 1.0e30)
    arr = np.where(nodata_mask, np.nan, arr)
    return VirMosaic(label=label, data=arr, path=path)


# Empirically confirmed (scripts/mosaic_crater_check.py), not assumed: the
# PDS3 SIS leaves the sign of the sample-vs-longitude relationship
# implementation-defined for POSITIVE_LONGITUDE_DIRECTION=EAST equirectangular
# data, so both candidate signs were tested -- WITH the real +(-150) degree
# offset below already applied first (an earlier draft tested signs without
# the offset applied, got the opposite, wrong answer, and was caught and
# corrected here before being relied on for anything) -- against a real,
# literature-documented feature (Rheasilvia's diogenite-rich signature:
# De Sanctis et al. 2012, same citation basis as this project's own
# Slice 11). Result: lon_sign=-1 recovers a local Band I center 0.56 std
# below the real global mean (shorter wavelength = more diogenite-like, as
# the literature predicts); lon_sign=+1 shows no such deviation (+0.21 std,
# indistinguishable from background). -1 is confirmed correct.
_VIR_LON_SIGN = -1

# Empirically-sourced from the volume's own CATALOG/VIR_DDR_VESTA_MOSAICS_DS.CAT
# (quoted in scripts/mosaic_acquire.py's docstring): "centered at ... longitude
# 330.0 in the IAU-compliant Claudia double prime system. This corresponds to
# 180.0 longitude in the system used in publications" -- i.e. label_lon =
# (claudia_lon - 150) mod 360, the same real frame FC's file is already
# expressed in (see ml.data.mosaic_reader module docstring).
_VIR_LABEL_LON_OFFSET_DEG = -150.0


def vir_lonlat_to_pixel(label: Pds3MosaicLabel, claudia_lon_deg: float, lat_deg: float) -> tuple[float, float]:
    """Real PDS3 EQUIRECTANGULAR pixel<->lonlat formula (CENTER_LATITUDE=0
    for this data, so the cos(center_lat) scale factor is 1), taking a
    longitude in the same real Claudia-Double-Prime/SPICE frame FC's file
    natively uses -- converts internally to VIR's own label-scale
    longitude (real, documented +150 degree offset) and applies the
    empirically-confirmed sign convention, so callers never need to think
    about either.

    Returns (line, sample), 1-indexed to match the label's own convention.
    """
    label_lon_deg = (claudia_lon_deg + _VIR_LABEL_LON_OFFSET_DEG) % 360.0
    sample = (
        label.sample_projection_offset_px + 1
        + _VIR_LON_SIGN * (label_lon_deg - label.center_longitude_deg) * label.map_resolution_px_per_deg
    )
    line = label.line_projection_offset_px + 1 - (lat_deg - label.center_latitude_deg) * label.map_resolution_px_per_deg
    return line, sample


# --------------------------------------------------------------------------
# FC: USGS GeoTIFF global mosaic
# --------------------------------------------------------------------------


@dataclass
class FcMosaic:
    path: Path
    sphere_radius_m: float
    transform: "rasterio.Affine"
    width: int
    height: int


def open_fc_mosaic(path: str | Path):
    """Returns (FcMosaic metadata, open rasterio dataset) -- caller is
    responsible for closing the dataset (or using it as a context
    manager); kept separate from VIR's eager-load reader because the FC
    file is read by window (tile-sized crops), never loaded whole."""
    if rasterio is None:
        raise ImportError("rasterio is required to read the FC GeoTIFF mosaic (see requirements.txt)")
    ds = rasterio.open(str(path))
    # Real sphere radius, read from the embedded CRS rather than hardcoded
    # (confirmed 255000 m -- matches VIR label's own A/B/C_AXIS_RADIUS).
    radius_m = ds.crs.to_dict().get("R") if ds.crs else None
    if radius_m is None:
        # rasterio's generic CRS dict doesn't always surface a custom
        # spheroid's radius; parse it from the WKT SPHEROID clause instead.
        wkt = ds.crs.to_wkt()
        m = re.search(r"SPHEROID\[[^,]+,\s*([0-9.]+)", wkt)
        radius_m = float(m.group(1)) if m else 255000.0
    meta = FcMosaic(path=Path(path), sphere_radius_m=float(radius_m), transform=ds.transform, width=ds.width, height=ds.height)
    return meta, ds


def fc_lonlat_to_pixel(meta: FcMosaic, lon_deg: float, lat_deg: float) -> tuple[float, float]:
    """FC's embedded CRS is a true equirectangular/plate-carree projection
    (central_meridian=0, standard_parallel=0) on a sphere -- x = R*lon_rad,
    y = R*lat_rad -- then the GeoTIFF's own affine transform maps
    projected (x, y) meters to (col, row) pixels. Longitude here is
    already in the file's native Claudia-Double-Prime-aligned scale (see
    module docstring and scripts/mosaic_acquire.py) -- no sign ambiguity,
    unlike VIR's label-scale longitude.
    """
    # FC's file domain is -180..180; wrap any input (e.g. a real gazetteer
    # coordinate given as 0..360) into that range before projecting.
    lon_deg = ((lon_deg + 180) % 360) - 180
    x = meta.sphere_radius_m * np.deg2rad(lon_deg)
    y = meta.sphere_radius_m * np.deg2rad(lat_deg)
    inv = ~meta.transform
    col, row = inv * (x, y)
    return row, col
