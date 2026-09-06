"""
Spatial alignment for AstroMineAI — Month 1, Slice 2.

Pairs Dawn FC Vesta images against Dawn VIR Vesta spectral cubes by real
body-fixed-frame footprint overlap (+ time proximity as a secondary
signal), keeps only pairs above a configured confidence threshold, crops
each surviving FC image to the overlap region, and records full
provenance for every surviving pair via SampleMetadata.

Scope of this module (deliberately narrow):
    - Spatial correspondence between already-downloaded FC images and VIR
      cubes. It does NOT re-download anything (see ml/data/pds_acquisition.py)
      and does NOT assign compositional labels (see docs/scientific_integrity_checklist.md —
      that is a later slice, after the data audit).

Geometry is read directly from each product's PDS3 .LBL file — no SPICE
kernels are loaded here. This has a real consequence, observed against
the actual downloaded sample: some products (in particular, the FC
approach-phase OpNav frames pulled during the acquisition smoke test)
simply do not carry computed surface footprint fields in their label
(MINIMUM_LATITUDE etc. are "N/A") — see docs/month1_log.md for what that
meant for this run. When a product's footprint can't be read, it is
treated as missing, not guessed at.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

from ml.utils.metadata_schema import SampleMetadata, write_metadata_csv

logger = logging.getLogger("spatial_alignment")


# --------------------------------------------------------------------------
# PDS3 label field extraction
#
# We do NOT write a general PDS3 parser (nested OBJECT/GROUP structures,
# multi-line quoted strings, etc.). We only need a fixed set of top-level
# keyword=value fields, which is a much narrower, verifiable problem — and
# every regex below was checked against real downloaded .LBL files, not
# assumed. See docs/month1_log.md for which fields were actually present.
# --------------------------------------------------------------------------

_UNIT_RE = re.compile(r"<[^>]*>\s*$")


def _get_scalar(text: str, key: str) -> Optional[str]:
    """Extract a single-line 'KEY = value [<unit>]' field.

    Returns None if the key is absent OR its value is the PDS3 "N/A"
    sentinel — both mean "not usable", and callers must not tell them
    apart from real data.
    """
    m = re.search(rf"(?m)^{re.escape(key)}\s*=\s*(.+)$", text)
    if not m:
        return None
    raw = m.group(1).strip()
    raw = _UNIT_RE.sub("", raw).strip()
    if raw.startswith('"'):
        raw = raw[1:]
        if raw.endswith('"'):
            raw = raw[:-1]
        raw = raw.strip()
    if raw in ("N/A", "", "UNK"):
        return None
    return raw


def _get_float(text: str, key: str) -> Optional[float]:
    raw = _get_scalar(text, key)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _get_array(text: str, key: str) -> Optional[list[Optional[float]]]:
    """Extract a parenthesized, comma-separated array field (possibly
    spanning multiple lines), e.g. RETICLE_POINT_LATITUDE = ( ... )."""
    m = re.search(rf"{re.escape(key)}\s*=\s*\((.*?)\)", text, re.S)
    if not m:
        return None
    values: list[Optional[float]] = []
    for item in m.group(1).split(","):
        item = _UNIT_RE.sub("", item).strip().strip('"').strip()
        if item in ("N/A", ""):
            values.append(None)
            continue
        try:
            values.append(float(item))
        except ValueError:
            values.append(None)
    return values


def _parse_pds_time(raw: Optional[str]) -> Optional[datetime]:
    """Parse a PDS3 time string. Dawn labels use two formats:
    - day-of-year: '2011-123T13:35:16.604'  (FC)
    - calendar:    '2011-05-10T06:10:36.974' (VIR)
    """
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%jT%H:%M:%S.%f", "%Y-%jT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.debug("Could not parse PDS time value: %r", raw)
    return None


# --------------------------------------------------------------------------
# Geometry loading
# --------------------------------------------------------------------------


@dataclass
class ProductGeometry:
    label_path: str
    product_id: Optional[str]
    dataset_id: Optional[str]
    instrument_id: Optional[str]
    instrument_host: Optional[str]
    mission_name: Optional[str]
    target_name: Optional[str]
    start_time: Optional[str]
    stop_time: Optional[str]
    footprint: Optional[dict]        # {min_lat, max_lat, west_lon, east_lon}
    footprint_source: Optional[str]  # 'bounding_box' | 'reticle_corners_bbox' | None


def _standardize_footprint_lon(west_lon: float, east_lon: float, instrument_id: Optional[str]) -> tuple[float, float]:
    """Convert a product's raw WESTERNMOST_LONGITUDE/EASTERNMOST_LONGITUDE
    into standard, increasing-eastward (west <= east, modulo a genuine
    Prime-Meridian wrap) form — instrument-aware, because FC and VIR do
    NOT share one convention in this archive. Evidence (see
    docs/month1_log.md, Slice 7, for the full writeup):

    - Real sample, 20/20 each, from actual downloaded HAMO .LBL files:
      every FC product has WESTERNMOST_LONGITUDE < EASTERNMOST_LONGITUDE
      (CENTER_LONGITUDE always between); every VIR product has
      WESTERNMOST_LONGITUDE > EASTERNMOST_LONGITUDE (CENTER_LONGITUDE
      always between the two, just the other way round). This is a
      clean, 100%-consistent split by instrument, not noise.
    - Documentation (DWNVFC2_1B/DOCUMENT/SIS/DAWN_FC_SIS_20131216.HTM):
      explicitly states "CENTER_LONGITUDE ... Center pixel planetocentric
      EAST longitude" and "SUB_SPACECRAFT_LONGITUDE ... planetocentric
      east" for FC — i.e. FC's own SIS explicitly confirms east-increasing,
      matching the empirical pattern exactly.
    - VIR's SIS (DWNVVIR_V1B/DOCUMENT/SIS/DAWN_VIR_SIS_V1_8.HTM) states
      CENTER_LONGITUDE/SUB_SPACECRAFT_LONGITUDE are "planetocentric"
      (without VIR's doc ever writing the word "east" next to it, unlike
      FC's) — which, read via the same doc's general definition
      ("planetocentric... longitudes increase toward the east"), would
      imply VIR's WESTERNMOST/EASTERNMOST should ALSO be east-increasing.
      They empirically are not (20/20 real samples). This is a real,
      unresolved apparent inconsistency in VIR's own documentation/
      pipeline (not papered over here) — the fix below follows the
      empirical pattern, which is unambiguous and internally
      self-consistent (CENTER_LONGITUDE always lands between the two
      raw values either way), over the ambiguous prose.
    - A worked real example that motivated this whole fix (FC product
      0007106 vs VIR product VIR_VIS_1B_1_370617178, ~2h10m apart in a
      HAMO cycle-1 pair with real latitude overlap): treating VIR's raw
      values as already-standard (as the previous version of this
      function did, inferred from too small a sample) inflates VIR's
      true ~14.86 degree span into a nonsensical, un-inflated-for-FC-only
      comparison; the deeper problem this surfaced was that FC's OWN
      ~18.69 degree span was getting inflated to ~341 degrees by
      wrongly applying a VIR-shaped correction to FC. See
      tests/test_spatial_alignment.py for the regression test built from
      this exact pair.

    Returns (west_lon, east_lon) unchanged for FC (and for any unrecognized
    instrument — logged, not silently guessed at), and swapped for VIR.
    """
    instrument = (instrument_id or "").strip().upper()
    if instrument.startswith("VIR"):
        return east_lon, west_lon
    if instrument.startswith("FC"):
        return west_lon, east_lon
    logger.warning(
        "Unrecognized instrument_id %r for longitude standardization — leaving "
        "WESTERNMOST/EASTERNMOST_LONGITUDE as-is rather than guessing which "
        "convention applies", instrument_id,
    )
    return west_lon, east_lon


def load_geometry(label_path: str | Path) -> Optional[ProductGeometry]:
    """Read one PDS3 .LBL file and extract identity/time/footprint fields.

    Returns None only if the label file is missing or unreadable —
    i.e. a genuine failure to load. A label that parses fine but simply
    has no footprint fields (all "N/A") still returns a ProductGeometry,
    just with `footprint=None`; `compute_footprint_overlap()` is what
    decides such a pair can't be scored.
    """
    label_path = Path(label_path)
    try:
        text = label_path.read_text(encoding="ascii", errors="replace")
    except OSError as exc:
        logger.warning("Could not read label %s: %s", label_path, exc)
        return None

    if "PDS_VERSION_ID" not in text:
        logger.warning("%s does not look like a PDS3 label; skipping", label_path)
        return None

    # Footprint, preference order:
    #   1) explicit bounding box (MINIMUM/MAXIMUM_LATITUDE, WEST/EASTERNMOST_LONGITUDE)
    #      — this is what's actually populated on the VIR products in our sample.
    #   2) FC's RETICLE_POINT_LATITUDE/LONGITUDE corner array, reduced to its
    #      bounding box (a documented approximation of the true quadrilateral,
    #      not a fabrication — noted explicitly wherever it's used).
    min_lat = _get_float(text, "MINIMUM_LATITUDE")
    max_lat = _get_float(text, "MAXIMUM_LATITUDE")
    west_lon = _get_float(text, "WESTERNMOST_LONGITUDE")
    east_lon = _get_float(text, "EASTERNMOST_LONGITUDE")

    instrument_id = _get_scalar(text, "INSTRUMENT_ID")

    footprint = None
    footprint_source = None
    if None not in (min_lat, max_lat, west_lon, east_lon):
        west_lon, east_lon = _standardize_footprint_lon(west_lon, east_lon, instrument_id)
        footprint = {
            "min_lat": min_lat, "max_lat": max_lat,
            "west_lon": west_lon, "east_lon": east_lon,
        }
        footprint_source = "bounding_box"
    else:
        ret_lats = _get_array(text, "RETICLE_POINT_LATITUDE")
        ret_lons = _get_array(text, "RETICLE_POINT_LONGITUDE")
        lats = [v for v in (ret_lats or []) if v is not None]
        lons = [v for v in (ret_lons or []) if v is not None]
        if lats and lons:
            footprint = {
                "min_lat": min(lats), "max_lat": max(lats),
                "west_lon": min(lons), "east_lon": max(lons),
            }
            footprint_source = "reticle_corners_bbox"

    return ProductGeometry(
        label_path=str(label_path),
        product_id=_get_scalar(text, "PRODUCT_ID"),
        dataset_id=_get_scalar(text, "DATA_SET_ID"),
        instrument_id=instrument_id,
        instrument_host=_get_scalar(text, "INSTRUMENT_HOST_ID") or _get_scalar(text, "INSTRUMENT_HOST_NAME"),
        mission_name=_get_scalar(text, "MISSION_NAME") or "DAWN",
        target_name=_get_scalar(text, "TARGET_NAME"),
        start_time=_get_scalar(text, "START_TIME"),
        stop_time=_get_scalar(text, "STOP_TIME"),
        footprint=footprint,
        footprint_source=footprint_source,
    )


# --------------------------------------------------------------------------
# Overlap / confidence
# --------------------------------------------------------------------------


def _split_wrapping_interval(lo: float, hi: float) -> list[tuple[float, float]]:
    """Split a (possibly wrapping-through-360) increasing interval
    [lo, hi) into 1 or 2 non-wrapping [lo, hi) parts."""
    if hi >= lo:
        return [(lo, hi)]
    return [(lo, 360.0), (0.0, hi)]


def _footprint_overlap_details(a: dict, b: dict) -> Optional[dict]:
    """Real overlap between two lat/lon footprints.

    `a['west_lon']`/`a['east_lon']` (and `b`'s) are expected to already be
    in standard, increasing-eastward form — `load_geometry()` /
    `_standardize_footprint_lon()` is what makes that true per-instrument
    before a footprint dict ever reaches this function (FC and VIR do NOT
    share one raw convention; see that function's docstring for the real
    evidence). This function only handles a genuine Prime-Meridian wrap
    in the now-standard frame (west_lon > east_lon after standardization).

    Returns None if not computable (degenerate/zero-extent footprint).
    Otherwise returns a dict with:
      - iou: intersection / union (degree^2 area, equirectangular
        approximation — doesn't scale longitude by cos(latitude); an
        approximation applying similarly to both boxes, not exact).
      - overlap_coefficient: intersection / min(area_a, area_b) — the
        Szymkiewicz-Simpson coefficient, i.e. what fraction of the
        *smaller* footprint is covered. Unlike IoU, this doesn't
        automatically penalize a real, fully-contained match just
        because one footprint (typically the FC frame) is much larger
        than the other (typically the VIR spectrum) — see
        `compute_footprint_overlap()` for how this is combined with an
        explicit size-ratio penalty instead.
      - size_ratio: max(area_a, area_b) / min(area_a, area_b), >= 1.
      - overlap_bbox: the overlap region as {min_lat, max_lat, west_lon,
        east_lon} in the original (native) longitude convention, for
        cropping/metadata. If the intersection is split across more than
        one longitude segment (a rare double-wrap edge case), the single
        largest segment is reported, not merged — documented
        simplification, not fabricated.
    """
    lat_lo = max(a["min_lat"], b["min_lat"])
    lat_hi = min(a["max_lat"], b["max_lat"])
    lat_overlap = max(0.0, lat_hi - lat_lo)

    ax_w, ax_e = a["west_lon"] % 360.0, a["east_lon"] % 360.0
    bx_w, bx_e = b["west_lon"] % 360.0, b["east_lon"] % 360.0
    a_parts = _split_wrapping_interval(ax_w, ax_e)
    b_parts = _split_wrapping_interval(bx_w, bx_e)

    lon_overlap_total = 0.0
    best_segment = None
    best_len = 0.0
    for pa_lo, pa_hi in a_parts:
        for pb_lo, pb_hi in b_parts:
            lo, hi = max(pa_lo, pb_lo), min(pa_hi, pb_hi)
            if hi > lo:
                lon_overlap_total += hi - lo
                if hi - lo > best_len:
                    best_len = hi - lo
                    best_segment = (lo, hi)

    lon_span_a = sum(hi - lo for lo, hi in a_parts)
    lon_span_b = sum(hi - lo for lo, hi in b_parts)
    if lat_overlap <= 0 or lon_overlap_total <= 0 or lon_span_a <= 0 or lon_span_b <= 0:
        area_a = max(0.0, a["max_lat"] - a["min_lat"]) * lon_span_a
        area_b = max(0.0, b["max_lat"] - b["min_lat"]) * lon_span_b
        if area_a <= 0 or area_b <= 0:
            return None
        return {
            "iou": 0.0, "overlap_coefficient": 0.0, "size_ratio": max(area_a, area_b) / min(area_a, area_b),
            "overlap_bbox": None,
        }

    inter_area = lat_overlap * lon_overlap_total
    area_a = (a["max_lat"] - a["min_lat"]) * lon_span_a
    area_b = (b["max_lat"] - b["min_lat"]) * lon_span_b
    union_area = area_a + area_b - inter_area
    if union_area <= 0 or best_segment is None:
        return None

    min_area, max_area = min(area_a, area_b), max(area_a, area_b)
    overlap_bbox = {
        "min_lat": lat_lo, "max_lat": lat_hi,
        "west_lon": best_segment[0], "east_lon": best_segment[1],
    }
    return {
        "iou": max(0.0, min(1.0, inter_area / union_area)),
        "overlap_coefficient": max(0.0, min(1.0, inter_area / min_area)),
        "size_ratio": max_area / min_area if min_area > 0 else float("inf"),
        "overlap_bbox": overlap_bbox,
    }


def _time_proximity_factor(t1: Optional[str], t2: Optional[str], max_time_delta_hours: float) -> tuple[Optional[float], Optional[float]]:
    """Returns (factor in [0,1], |delta seconds|), or (None, None) if either
    time is unparseable. factor=1.0 at delta=0, decays linearly to 0.0 at
    max_time_delta_hours, and is clamped at 0 beyond that."""
    dt1, dt2 = _parse_pds_time(t1), _parse_pds_time(t2)
    if dt1 is None or dt2 is None:
        return None, None
    delta_seconds = abs((dt1 - dt2).total_seconds())
    max_seconds = max_time_delta_hours * 3600.0
    factor = max(0.0, 1.0 - (delta_seconds / max_seconds)) if max_seconds > 0 else 0.0
    return factor, delta_seconds


def compute_footprint_overlap(
    image_geometry: Optional[ProductGeometry],
    spectrum_geometry: Optional[ProductGeometry],
    max_time_delta_hours: float = 24.0,
) -> Optional[float]:
    """Confidence in [0,1] that `image_geometry` and `spectrum_geometry`
    observe overlapping ground, or None if it can't be reliably computed.

    spatial_score = overlap_coefficient * size_ratio_penalty
    confidence    = spatial_score * (0.5 + 0.5 * time_factor)

    Why overlap_coefficient (intersection / smaller-footprint-area)
    instead of plain IoU: an FC image frame and a single VIR spectrum
    footprint are routinely very different sizes (e.g. a whole-disk
    approach-phase FC frame vs. a single narrow VIR scan). Plain IoU
    divides by the *union*, which is dominated by whichever footprint is
    larger — so a spectrum that's genuinely, fully contained inside a
    much bigger image frame would still score a tiny IoU purely from the
    size mismatch, not from any real positional uncertainty. That's not
    what "confidence this pair corresponds" should mean.

    But dropping size out of the score entirely would be wrong too: a
    single giant image footprint could then trivially "fully contain",
    and score maximally against, dozens of unrelated small spectra
    anywhere within it — that's not a spatially *specific* match either.
    `size_ratio_penalty = min(area)/max(area)` (in (0, 1]) explicitly
    discounts confidence as the size mismatch grows, so a same-sized,
    fully-overlapping pair scores near 1.0, while a fully-contained but
    wildly size-mismatched pair scores low, without IoU's harsher
    union-dominated penalty for containment alone.

    NOTE: the size-ratio penalty's exact strength (here, a plain linear
    multiply — not softened) is a placeholder, not a validated choice —
    there is no real surviving pair yet to look at the actual image/
    spectrum footprint-area-ratio distribution and calibrate against
    (see docs/month1_log.md). Once real pairs exist, re-examine this.

    Time proximity remains a secondary signal only: it can discount an
    overlapping pair down to half its spatial score, never invent
    confidence for a pair with no computed spatial overlap.
    """
    if image_geometry is None or spectrum_geometry is None:
        return None
    if image_geometry.footprint is None or spectrum_geometry.footprint is None:
        return None

    details = _footprint_overlap_details(image_geometry.footprint, spectrum_geometry.footprint)
    if details is None:
        return None
    if details["overlap_coefficient"] == 0.0:
        return 0.0

    size_ratio_penalty = 1.0 / details["size_ratio"] if details["size_ratio"] > 0 else 0.0
    spatial_score = details["overlap_coefficient"] * size_ratio_penalty

    time_factor, _delta_seconds = _time_proximity_factor(
        image_geometry.start_time, spectrum_geometry.start_time, max_time_delta_hours
    )
    if time_factor is None:
        return None

    confidence = spatial_score * (0.5 + 0.5 * time_factor)
    return max(0.0, min(1.0, confidence))


# --------------------------------------------------------------------------
# Cropping
# --------------------------------------------------------------------------


def _crop_fc_image_to_overlap(
    fc_data_path: str | Path,
    image_footprint: dict,
    overlap_bbox: dict,
    out_png_path: str | Path,
) -> bool:
    """Crop the FC frame to the pixel region corresponding to `overlap_bbox`
    and save it as a PNG.

    IMPORTANT APPROXIMATION: FC labels in this archive do not carry a
    per-pixel lat/lon backplane (that would require running SPICE, which
    is out of scope here). This function instead assumes the image's full
    frame maps *linearly* onto its label-reported footprint bounding box
    (north at the top, west at the left) to translate the overlap
    lat/lon box into a pixel row/column box. This ignores camera twist/
    north-azimuth rotation and lens distortion, so it is only a first
    approximation of the true crop region — good enough to produce a
    plausible region crop, not a substitute for real backplane-based
    reprojection. Flagged here and in docs/month1_log.md, not hidden.
    """
    from astropy.io import fits
    from PIL import Image

    try:
        with fits.open(str(fc_data_path)) as hdul:
            image_hdu = next((h for h in hdul if getattr(h, "data", None) is not None), None)
            if image_hdu is None:
                logger.warning("No image data found in %s", fc_data_path)
                return False
            data = np.asarray(image_hdu.data, dtype=np.float64)
    except Exception as exc:  # noqa: BLE001 - report and skip, don't crash the batch
        logger.warning("Failed to read FITS data from %s: %s", fc_data_path, exc)
        return False

    if data.ndim != 2:
        logger.warning("Unexpected FC image ndim=%d for %s", data.ndim, fc_data_path)
        return False

    n_lines, n_samples = data.shape

    fp = image_footprint
    lat_span = fp["max_lat"] - fp["min_lat"]
    # image_footprint / overlap_bbox are already standardized, increasing-
    # eastward longitude (see _standardize_footprint_lon()) — the image's
    # forward (west -> east) angular span is just east_lon - west_lon,
    # wrapping through 0/360 only on a genuine Prime-Meridian crossing.
    fp_west, fp_east = fp["west_lon"] % 360.0, fp["east_lon"] % 360.0
    lon_span = (fp_east - fp_west) % 360.0
    if lat_span <= 0 or lon_span <= 0:
        logger.warning("Degenerate image footprint for %s; skipping crop", fc_data_path)
        return False

    # north at row 0 -> row increases as latitude decreases
    row_start = (fp["max_lat"] - overlap_bbox["max_lat"]) / lat_span * n_lines
    row_stop = (fp["max_lat"] - overlap_bbox["min_lat"]) / lat_span * n_lines
    ov_west, ov_east = overlap_bbox["west_lon"] % 360.0, overlap_bbox["east_lon"] % 360.0
    col_start = ((ov_west - fp_west) % 360.0) / lon_span * n_samples
    col_stop = ((ov_east - fp_west) % 360.0) / lon_span * n_samples

    r0, r1 = sorted((int(round(row_start)), int(round(row_stop))))
    c0, c1 = sorted((int(round(col_start)), int(round(col_stop))))
    r0, r1 = max(0, r0), min(n_lines, max(r1, r0 + 1))
    c0, c1 = max(0, c0), min(n_samples, max(c1, c0 + 1))

    crop = data[r0:r1, c0:c1]
    if crop.size == 0:
        logger.warning("Empty crop region computed for %s", fc_data_path)
        return False

    # Min-max stretch to 8-bit for a viewable PNG (FC calibrated data is
    # radiance in W/(m^2 sr), not natively 0-255).
    finite = crop[np.isfinite(crop)]
    if finite.size == 0:
        logger.warning("Crop region for %s has no finite pixels", fc_data_path)
        return False
    lo, hi = np.percentile(finite, [1, 99])
    if hi <= lo:
        lo, hi = float(finite.min()), float(finite.max() or 1.0)
    stretched = np.clip((crop - lo) / max(hi - lo, 1e-12), 0.0, 1.0)
    img_8bit = (stretched * 255).astype(np.uint8)

    out_png_path = Path(out_png_path)
    out_png_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img_8bit, mode="L").save(out_png_path)
    return True


# --------------------------------------------------------------------------
# align_dataset
# --------------------------------------------------------------------------


def _load_manifest(manifest_path: str | Path) -> list[dict]:
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        return []
    records = []
    with open(manifest_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def align_dataset(
    image_products: list[dict],
    spectrum_products: list[dict],
    min_confidence: float,
    processed_dir: str | Path = "datasets/processed",
    max_time_delta_hours: float = 24.0,
) -> list[SampleMetadata]:
    """Pair every FC image against candidate VIR spectra, keep pairs whose
    correspondence confidence >= min_confidence, crop + save survivors,
    and return their SampleMetadata records (also nothing is written for
    rejected pairs — this function doesn't log every rejected candidate,
    callers/CLI report aggregate counts).

    `image_products` / `spectrum_products`: dicts with at least
    'label_path' and 'data_path' (the shape written by
    pds_acquisition.py's manifest.jsonl — this function doesn't care
    where they came from, only that those two keys resolve to real files).
    """
    processed_dir = Path(processed_dir)

    # Pre-load geometry once per product (avoid re-parsing labels per-pair).
    image_geoms = []
    for prod in image_products:
        geom = load_geometry(prod["label_path"])
        image_geoms.append((prod, geom))

    spectrum_geoms = []
    for prod in spectrum_products:
        geom = load_geometry(prod["label_path"])
        spectrum_geoms.append((prod, geom))

    n_image_footprints = sum(1 for _, g in image_geoms if g and g.footprint)
    n_spectrum_footprints = sum(1 for _, g in spectrum_geoms if g and g.footprint)
    logger.info(
        "Loaded geometry for %d/%d FC images (%d with usable footprint) and "
        "%d/%d VIR spectra (%d with usable footprint)",
        len(image_geoms), len(image_products), n_image_footprints,
        len(spectrum_geoms), len(spectrum_products), n_spectrum_footprints,
    )

    survivors: list[SampleMetadata] = []
    n_candidates_in_time_window = 0
    n_scored = 0

    for img_prod, img_geom in image_geoms:
        if img_geom is None:
            continue
        img_time = _parse_pds_time(img_geom.start_time)

        for spec_prod, spec_geom in spectrum_geoms:
            if spec_geom is None:
                continue
            spec_time = _parse_pds_time(spec_geom.start_time)

            # Rough time-window pre-filter, before any geometry math, to
            # keep this tractable at scale (per task instructions).
            if img_time is not None and spec_time is not None:
                delta_hours = abs((img_time - spec_time).total_seconds()) / 3600.0
                if delta_hours > max_time_delta_hours:
                    continue
            n_candidates_in_time_window += 1

            confidence = compute_footprint_overlap(img_geom, spec_geom, max_time_delta_hours)
            if confidence is None:
                continue
            n_scored += 1
            if confidence < min_confidence:
                continue

            # Recompute the full overlap details for cropping/metadata (we
            # only have the scalar confidence from compute_footprint_overlap).
            fp_a, fp_b = img_geom.footprint, spec_geom.footprint
            details = _footprint_overlap_details(fp_a, fp_b)
            if details is None or details["overlap_bbox"] is None:
                logger.warning("Overlap bbox recompute failed for a pair that scored >0; skipping")
                continue
            overlap = details["overlap_bbox"]
            region_id = f"{img_geom.product_id}__{spec_geom.product_id}"
            out_png = processed_dir / f"{region_id}.png"

            if not _crop_fc_image_to_overlap(img_prod["data_path"], fp_a, overlap, out_png):
                logger.warning("Skipping pair %s: crop failed", region_id)
                continue

            _, delta_seconds = _time_proximity_factor(img_geom.start_time, spec_geom.start_time, max_time_delta_hours)
            iou = details["iou"]

            survivors.append(SampleMetadata(
                region_id=region_id,
                mission=img_geom.mission_name or "DAWN",
                image_instrument=img_geom.instrument_id or "FC2",
                spectrum_instrument=spec_geom.instrument_id or "VIR",
                image_dataset_id=img_geom.dataset_id or "",
                spectrum_dataset_id=spec_geom.dataset_id or "",
                image_product_id=img_geom.product_id or "",
                spectrum_product_id=spec_geom.product_id or "",
                target=img_geom.target_name or spec_geom.target_name or "",
                min_latitude=overlap["min_lat"],
                max_latitude=overlap["max_lat"],
                west_longitude=overlap["west_lon"],
                east_longitude=overlap["east_lon"],
                center_latitude=(overlap["min_lat"] + overlap["max_lat"]) / 2,
                center_longitude=(overlap["west_lon"] + overlap["east_lon"]) / 2,
                image_start_time=img_geom.start_time or "",
                spectrum_start_time=spec_geom.start_time or "",
                time_delta_seconds=delta_seconds if delta_seconds is not None else -1.0,
                spatial_iou=iou,
                correspondence_confidence=confidence,
                image_path=str(out_png),
                spectrum_path=spec_prod["data_path"],
                image_label_path=img_prod["label_path"],
                spectrum_label_path=spec_prod["label_path"],
            ))

    logger.info(
        "Alignment: %d FC x %d VIR candidates fell inside the %.1fh time window; "
        "%d pairs had computable overlap; %d/%d survived confidence >= %.2f",
        n_candidates_in_time_window, max_time_delta_hours, max_time_delta_hours,
        n_scored, len(survivors), n_scored, min_confidence,
    )
    return survivors


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    with open(args.config, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    raw_dir = Path(config["data"]["raw_dir"])
    min_confidence = config["data"]["min_spatial_correspondence_confidence"]
    max_time_delta_hours = config["data"].get("max_time_delta_hours", 24.0)

    image_products = _load_manifest(raw_dir / "dawn_fc_vesta" / "manifest.jsonl")
    spectrum_products = _load_manifest(raw_dir / "dawn_vir_vesta" / "manifest.jsonl")
    # Only score products that actually downloaded successfully.
    image_products = [p for p in image_products if p.get("downloaded")]
    spectrum_products = [p for p in spectrum_products if p.get("downloaded")]

    logger.info(
        "Loaded %d downloaded FC image products and %d downloaded VIR spectrum products from manifests",
        len(image_products), len(spectrum_products),
    )

    survivors = align_dataset(
        image_products, spectrum_products, min_confidence,
        processed_dir=Path(config["data"].get("processed_dir", "datasets/processed")),
        max_time_delta_hours=max_time_delta_hours,
    )

    metadata_path = Path(config["data"].get("metadata_dir", "datasets/metadata")) / "sample_metadata.csv"
    write_metadata_csv(survivors, metadata_path)

    logger.info(
        "Done: %d FC images, %d VIR spectra considered; %d pairs survived "
        "confidence >= %.2f; written to %s",
        len(image_products), len(spectrum_products), len(survivors),
        min_confidence, metadata_path,
    )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
