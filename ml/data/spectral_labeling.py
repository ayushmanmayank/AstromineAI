"""
VIR-only compositional label scheme for AstroMineAI — Month 1, Slice 3
(Part B/C of the data-audit-and-labeling pass).

STRICT RULE (see docs/scientific_integrity_checklist.md): every label
here comes from VIR spectral band parameters. FC imagery is never read,
inspected, or otherwise consulted anywhere in this module — the image is
model input, never a label signal. If you are reading this file wondering
whether it would be faster to just look at the cropped PNG and eyeball a
class, don't: that impulse is exactly the shortcut the checklist forbids,
because it makes the label unreproducible and untraceable to a rule.

Scientific basis
-----------------
Dawn VIR Vesta spectra of HED (howardite-eucrite-diogenite) terrain show
two diagnostic pyroxene absorption features:
  - "Band I", ~0.9-1.0 micron (Fe2+ crystal-field absorption). Its center
    wavelength shifts redward (longer wavelength) as pyroxene Ca-content
    increases: low-Ca orthopyroxene (diogenite-like) centers shorter,
    high-Ca clinopyroxene (eucrite-like) centers longer, with mixed
    (howardite-like) material in between.
  - "Band II", ~1.9-2.0 micron, shifts the same direction for the same
    reason, and its area relative to Band I (the "Band Area Ratio", BAR)
    is the classic two-band diagnostic in pyroxene/HED literature.
This is the general, well-established direction of the Band I/II center
shift with pyroxene chemistry described in Dawn-VIR Vesta literature
(e.g. De Sanctis et al. 2012, Science; Ammannito et al. 2013, M&PS) and
earlier lab pyroxene systematics (Gaffey 1976; Cloutis & Gaffey 1991).

IMPORTANT HONESTY NOTE on the thresholds below: they are first-pass,
literature-informed starting points recalled from general Dawn VIR / HED
pyroxene literature, NOT independently fit to this project's own data —
that's impossible with the current sample size (see docs/month1_log.md,
Part A: N=0 surviving pairs). They are written down explicitly, with
their exact values, specifically so they're auditable and can be
recalibrated the moment real labeled spectra exist. Treat them as a
documented starting point, not a validated cutoff.

Channel constraint
-------------------
Dawn VIR's two channels don't both cover the same band: the VIS channel
(~0.25-1.07 micron) covers Band I but not Band II; the IR channel
(~1.02-5.0 micron) covers Band II but not Band I. spatial_alignment.py
pairs an FC image against a VIS spectrum OR an IR spectrum independently
(not a matched VIS+IR pair for the same observation), so this module
scores whichever band the given spectrum's channel actually covers,
rather than requiring both. A full Band Area Ratio (which needs both
bands from the same observation, matched by SPACECRAFT_CLOCK_START_COUNT)
would be a real refinement for a future pass — flagged here, not built,
since it would mean changing how spatial_alignment.py pairs products,
which is out of scope for this pass.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ml.utils.metadata_schema import SampleMetadata

logger = logging.getLogger("spectral_labeling")

LABEL_SCHEME_VERSION = "VIR band-center threshold v1"

# First-pass thresholds (see module docstring's honesty note). Band center
# in microns. "depth_floor" is a data-quality gate: below this continuum-
# removed depth, the absorption feature is too shallow/noisy to trust a
# center-wavelength fit, and the sample is classified INDETERMINATE_LABEL
# rather than assigned a compositional guess.
BAND_I_WINDOW_UM = (0.75, 1.05)     # search window for the Band I minimum
BAND_I_SHOULDERS_UM = (0.75, 1.05)  # continuum tie points
BAND_I_DEPTH_FLOOR = 0.02
BAND_I_THRESHOLDS_UM = {
    "diogenite_like": (0.0, 0.92),
    "howardite_like": (0.92, 0.95),
    "eucrite_like": (0.95, 999.0),
}

BAND_II_WINDOW_UM = (1.65, 2.50)
BAND_II_SHOULDERS_UM = (1.65, 2.50)
BAND_II_DEPTH_FLOOR = 0.02
BAND_II_THRESHOLDS_UM = {
    "diogenite_like": (0.0, 1.97),
    "howardite_like": (1.97, 2.00),
    "eucrite_like": (2.00, 999.0),
}

INDETERMINATE_LABEL = "indeterminate_weak_feature"


# --------------------------------------------------------------------------
# QUBE reading
# --------------------------------------------------------------------------

_UNIT_RE = re.compile(r"<[^>]*>\s*$")


def _get_scalar(text: str, key: str) -> Optional[str]:
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*(.+)$", text)
    if not m:
        return None
    raw = _UNIT_RE.sub("", m.group(1).strip()).strip().strip('"').strip()
    return raw or None


def _get_int_array(text: str, key: str) -> Optional[list[int]]:
    m = re.search(rf"{re.escape(key)}\s*=\s*\((.*?)\)", text, re.S)
    if not m:
        return None
    return [int(float(x.strip())) for x in m.group(1).split(",") if x.strip()]


def _get_float_array(text: str, key: str) -> Optional[list[float]]:
    m = re.search(rf"{re.escape(key)}\s*=\s*\((.*?)\)", text, re.S)
    if not m:
        return None
    return [float(x.strip()) for x in m.group(1).split(",") if x.strip()]


@dataclass
class QubeSpectrum:
    product_id: str
    dataset_id: str
    channel: str                # 'VIS' or 'IR'
    is_calibrated: bool         # RDR (radiance) vs EDR (raw instrument DN)
    wavelengths_um: np.ndarray  # ascending
    mean_spectrum: np.ndarray   # same length, spatial mean, NaN where invalid


def read_vir_qube(label_path: str | Path) -> Optional[QubeSpectrum]:
    """Read a VIR .LBL + companion .QUB, return the spatially-averaged
    spectrum. Real binary parsing (BAND, SAMPLE, LINE axis order; 16-bit
    big-endian core samples) against the DWNVVIR_*1A volume's PDS3 QUBE
    format — not a stub.
    """
    label_path = Path(label_path)
    try:
        text = label_path.read_text(encoding="ascii", errors="replace")
    except OSError as exc:
        logger.warning("Could not read VIR label %s: %s", label_path, exc)
        return None

    qube_name = _get_scalar(text, "^QUBE")
    if not qube_name:
        logger.warning("%s has no ^QUBE pointer", label_path)
        return None
    qube_path = label_path.parent / qube_name.strip('"')

    core_items = _get_int_array(text, "CORE_ITEMS")
    if not core_items or len(core_items) != 3:
        logger.warning("%s: could not parse CORE_ITEMS", label_path)
        return None
    n_bands, n_samples, n_lines = core_items  # AXIS_NAME = (BAND, SAMPLE, LINE)

    core_null = _get_scalar(text, "CORE_NULL")
    core_null = float(core_null) if core_null else -32768.0

    band_centers = _get_float_array(text, "BAND_BIN_CENTER")
    if not band_centers or len(band_centers) != n_bands:
        logger.warning("%s: BAND_BIN_CENTER missing or length mismatch", label_path)
        return None

    channel = _get_scalar(text, "CHANNEL_ID") or "UNKNOWN"

    # Core sample dtype varies by processing level: raw (EDR) volumes use
    # 2-byte MSB_INTEGER instrument DN; calibrated (RDR) volumes use
    # 4-byte IEEE_REAL physical radiance. Read it from the label rather
    # than assuming — confirmed both forms exist in our own downloaded
    # sample (DWNVVIR_*1A vs DWNVVIR_*1B).
    item_bytes = int(_get_scalar(text, "CORE_ITEM_BYTES") or 2)
    item_type = (_get_scalar(text, "CORE_ITEM_TYPE") or "MSB_INTEGER").upper()
    dtype_map = {
        ("MSB_INTEGER", 2): ">i2",
        ("LSB_INTEGER", 2): "<i2",
        ("MSB_INTEGER", 4): ">i4",
        ("LSB_INTEGER", 4): "<i4",
        ("IEEE_REAL", 4): ">f4",
        ("PC_REAL", 4): "<f4",
        ("IEEE_REAL", 8): ">f8",
        ("PC_REAL", 8): "<f8",
    }
    dtype = dtype_map.get((item_type, item_bytes))
    if dtype is None:
        logger.warning("%s: unsupported CORE_ITEM_TYPE/BYTES %s/%d", label_path, item_type, item_bytes)
        return None

    try:
        raw = np.fromfile(str(qube_path), dtype=dtype)
    except OSError as exc:
        logger.warning("Could not read QUBE data %s: %s", qube_path, exc)
        return None

    expected = n_bands * n_samples * n_lines
    if raw.size != expected:
        logger.warning(
            "%s: QUBE size mismatch (got %d values, expected %d = %d bands x %d samples x %d lines)",
            qube_path, raw.size, expected, n_bands, n_samples, n_lines,
        )
        return None

    # BAND fastest-varying -> reshape (lines, samples, bands) in C order.
    cube = raw.reshape(n_lines, n_samples, n_bands).astype(np.float64)
    valid = cube > (core_null + 1.0)  # anything at/near the null/saturation sentinel is invalid
    cube_masked = np.where(valid, cube, np.nan)

    with np.errstate(all="ignore"):
        mean_spectrum = np.nanmean(cube_masked, axis=(0, 1))

    wavelengths = np.asarray(band_centers, dtype=np.float64)
    order = np.argsort(wavelengths)

    dataset_id = _get_scalar(text, "DATA_SET_ID") or ""
    # RDR (calibrated, spectral radiance) vs EDR (raw instrument DN) — see
    # this module's docstring: band-depth/center analysis assumes
    # roughly-reflectance-shaped input, which raw DN is not.
    is_calibrated = "-RDR-" in dataset_id or (_get_scalar(text, "PRODUCT_TYPE") or "").upper() == "RDR"

    return QubeSpectrum(
        product_id=_get_scalar(text, "PRODUCT_ID") or label_path.stem,
        dataset_id=dataset_id,
        channel=channel,
        is_calibrated=is_calibrated,
        wavelengths_um=wavelengths[order],
        mean_spectrum=mean_spectrum[order],
    )


# --------------------------------------------------------------------------
# Band parameters
# --------------------------------------------------------------------------


def compute_band_depth(wavelengths: np.ndarray, spectrum: np.ndarray, left_um: float, right_um: float) -> Optional[float]:
    """Continuum-removed band depth at the local reflectance minimum
    between left_um and right_um (Clark & Roush 1984 style linear
    continuum removal). Returns None if the window is out of range or
    all-NaN."""
    mask = (wavelengths >= left_um) & (wavelengths <= right_um)
    if not np.any(mask) or np.all(np.isnan(spectrum[mask])):
        return None
    w = wavelengths[mask]
    s = spectrum[mask]
    r_left, r_right = s[0], s[-1]
    if np.isnan(r_left) or np.isnan(r_right):
        return None
    continuum = r_left + (w - w[0]) / (w[-1] - w[0]) * (r_right - r_left)
    with np.errstate(invalid="ignore", divide="ignore"):
        removed = np.where(continuum > 0, s / continuum, np.nan)
    if np.all(np.isnan(removed)):
        return None
    min_val = np.nanmin(removed)
    return float(1.0 - min_val)


def compute_band_center(wavelengths: np.ndarray, spectrum: np.ndarray, left_um: float, right_um: float) -> Optional[float]:
    """Sub-pixel band-center wavelength: locate the continuum-removed
    minimum, then fit a parabola to it and its two neighbors for a
    sub-sample estimate (standard band-center-fitting technique).
    Returns None if there's no valid interior minimum to fit."""
    mask = (wavelengths >= left_um) & (wavelengths <= right_um)
    w = wavelengths[mask]
    s = spectrum[mask]
    if len(w) < 3 or np.all(np.isnan(s)):
        return None
    r_left, r_right = s[0], s[-1]
    if np.isnan(r_left) or np.isnan(r_right):
        return None
    continuum = r_left + (w - w[0]) / (w[-1] - w[0]) * (r_right - r_left)
    with np.errstate(invalid="ignore", divide="ignore"):
        removed = np.where(continuum > 0, s / continuum, np.nan)

    valid_idx = np.where(~np.isnan(removed))[0]
    if len(valid_idx) < 3:
        return None
    i = valid_idx[np.nanargmin(removed[valid_idx])]
    if i == 0 or i == len(removed) - 1:
        return float(w[i])  # minimum at the window edge; no interior parabola to fit

    x0, x1, x2 = w[i - 1], w[i], w[i + 1]
    y0, y1, y2 = removed[i - 1], removed[i], removed[i + 1]
    denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
    if denom == 0 or np.isnan(y0) or np.isnan(y2):
        return float(x1)
    a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
    b = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / denom
    if a == 0:
        return float(x1)
    vertex = -b / (2 * a)
    if not (x0 <= vertex <= x2):
        return float(x1)  # parabola vertex fell outside the 3-point window; fall back to the raw minimum
    return float(vertex)


def _classify_by_thresholds(center_um: float, thresholds: dict) -> str:
    for label, (lo, hi) in thresholds.items():
        if lo <= center_um < hi:
            return label
    return INDETERMINATE_LABEL


def classify_spectrum(qube: QubeSpectrum) -> tuple[str, str]:
    """Classify one VIR spectrum. Returns (label, label_source).

    label_source names the exact band, window, and threshold-set version
    used, so every label is traceable back to a specific, reproducible
    rule (required by docs/scientific_integrity_checklist.md).
    """
    if not qube.is_calibrated:
        return (
            INDETERMINATE_LABEL,
            f"raw/EDR VIR product ({qube.dataset_id}) is uncalibrated instrument DN, not "
            f"reflectance-like data — not valid input for continuum-removed band analysis, "
            f"{LABEL_SCHEME_VERSION}",
        )

    channel = (qube.channel or "").strip().upper()

    if channel == "VIS":
        depth = compute_band_depth(qube.wavelengths_um, qube.mean_spectrum, *BAND_I_SHOULDERS_UM)
        if depth is None or depth < BAND_I_DEPTH_FLOOR:
            return INDETERMINATE_LABEL, f"VIR VIS Band I depth < floor ({BAND_I_DEPTH_FLOOR}), {LABEL_SCHEME_VERSION}"
        center = compute_band_center(qube.wavelengths_um, qube.mean_spectrum, *BAND_I_WINDOW_UM)
        if center is None:
            return INDETERMINATE_LABEL, f"VIR VIS Band I center unfittable, {LABEL_SCHEME_VERSION}"
        label = _classify_by_thresholds(center, BAND_I_THRESHOLDS_UM)
        return label, f"VIR VIS Band I (~0.9-1.0um) center-wavelength threshold, {LABEL_SCHEME_VERSION}"

    if channel == "IR":
        depth = compute_band_depth(qube.wavelengths_um, qube.mean_spectrum, *BAND_II_SHOULDERS_UM)
        if depth is None or depth < BAND_II_DEPTH_FLOOR:
            return INDETERMINATE_LABEL, f"VIR IR Band II depth < floor ({BAND_II_DEPTH_FLOOR}), {LABEL_SCHEME_VERSION}"
        center = compute_band_center(qube.wavelengths_um, qube.mean_spectrum, *BAND_II_WINDOW_UM)
        if center is None:
            return INDETERMINATE_LABEL, f"VIR IR Band II center unfittable, {LABEL_SCHEME_VERSION}"
        label = _classify_by_thresholds(center, BAND_II_THRESHOLDS_UM)
        return label, f"VIR IR Band II (~1.9-2.0um) center-wavelength threshold, {LABEL_SCHEME_VERSION}"

    return INDETERMINATE_LABEL, f"VIR channel {qube.channel!r} not VIS or IR, {LABEL_SCHEME_VERSION}"


# --------------------------------------------------------------------------
# Driver over SampleMetadata
# --------------------------------------------------------------------------


def label_sample_metadata(records: list[SampleMetadata]) -> list[SampleMetadata]:
    """Assign .label / .label_source on every record from its VIR spectrum
    only (spectrum_label_path). FC image fields are never read here.

    Mutates and returns `records`. With 0 records this is a logged no-op.
    """
    if not records:
        logger.warning(
            "label_sample_metadata() called with 0 records — nothing to label. "
            "No labels can be derived until spatial_alignment.py produces surviving pairs."
        )
        return records

    for record in records:
        qube = read_vir_qube(record.spectrum_label_path)
        if qube is None:
            record.label = INDETERMINATE_LABEL
            record.label_source = f"VIR QUBE unreadable, {LABEL_SCHEME_VERSION}"
            continue
        label, source = classify_spectrum(qube)
        record.label = label
        record.label_source = source

    return records
