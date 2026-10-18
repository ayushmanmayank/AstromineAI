"""
Global-mosaic dataset v2, Stage 1 (Gate C): reader for the real Dawn
FC2 color-filter global mosaics (sbnarchive.psi.edu
`DAWN-A-FC2-5-MOSAIC-V1.0`, volume DWNVFC2_2, DATA/HAMO_COLOR/).

New, separate file (per this task's "new work goes in new files"
rule) -- does not modify `ml/data/mosaic_reader.py` (not in this task's
protected-file list, but left untouched anyway since this is additive,
new-format support, not a change to anything `final/mosaic-dataset`
already committed). Reuses that module's existing
`Pds3MosaicLabel`/`_parse_pds3_label`/`VirMosaic` via import rather
than duplicating them, since this is the *same* real label schema,
confirmed directly (not assumed) by reading the real attached label of
`VE_HAMO_00N_330E_CYL_FILT5.IMG` via an HTTP byte-range request before
any full download: `LINES`, `LINE_SAMPLES`, `SAMPLE_BITS`,
`SAMPLE_TYPE`, `MISSING_CONSTANT`, `MAP_RESOLUTION`,
`CENTER_LONGITUDE`, `CENTER_LATITUDE`, `LINE_PROJECTION_OFFSET`,
`SAMPLE_PROJECTION_OFFSET` are all present with the same meaning as
VIR's label. Same sphere (`A_AXIS_RADIUS=255.0 km`, matching FC's own
GeoTIFF CRS and VIR's label), same `SIMPLE_CYLINDRICAL` projection,
same Claudia-Double-Prime-aligned frame, same
`MISSING_CONSTANT=-1.0E+32` nodata sentinel convention, and a near-
identical `MAP_RESOLUTION` (74.17649 px/deg vs the primary FC HAMO
74ppd mosaic's 74.1778 px/deg -- a real, tiny reprocessing difference
between this color volume and the clear-filter 74ppd GeoTIFF, not an
error).

The ONE real difference from VIR's file that matters for reading:
these files' attached ASCII label is larger than VIR's fixed
64096-byte header (`RECORD_BYTES=106812`, `LABEL_RECORDS=2` here, i.e.
213624 bytes) -- `read_pds3_scalar_mosaic()` below discovers the real
header size from the file itself (a first small probe read) rather
than assuming a fixed size, so it works for either file's real
`RECORD_BYTES`/`LABEL_RECORDS` combination.

Real FC2 filter wavelengths, read directly from each file's own
`CENTER_FILTER_WAVELENGTH` field via `read_center_filter_wavelength_nm()`
below (an initial assumption based on a remembered generic Dawn FC
filter table -- F5=758nm, F7=917nm, F8=965nm -- was wrong and was
caught and discarded before any full download relied on it; a quick
byte-range probe of every real file's own label gave the true,
label-confirmed table instead): F2=555nm, **F3=749nm**, **F4=917nm**,
**F5=965nm**, F6=829nm, F7=653nm, F8=438nm. The task's "750/920 nm,
965/750 nm" ratio recipe therefore maps to **F3/F4** and **F5/F3**
using these real, label-confirmed wavelengths -- not F5/F7/F8 as
initially (wrongly) assumed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ml.data.mosaic_reader import Pds3MosaicLabel, VirMosaic, _parse_pds3_label

# Real, label-confirmed sample-format support (same convention as
# ml/data/mosaic_reader.py's read_vir_mosaic -- extended here only with
# the endianness actually found in these FC2 color files, verified
# empirically in scripts/mosaic_color_check.py before being relied on,
# exactly like VIR's big-endian confirmation).
_DTYPE_MAP = {(32, "IEEE_REAL"): ">f4"}


def read_pds3_scalar_mosaic(path: str | Path) -> VirMosaic:
    """Generalized reader for this project's self-labeled PDS3 mosaic
    files with a single scalar band (32-bit IEEE float): first probes a
    small prefix of the file to discover the real `LABEL_RECORDS` /
    `RECORD_BYTES` (rather than assuming VIR's fixed 64096-byte header
    size, which is too small for these FC2 color files' real 213624-byte
    header), then reads exactly that many bytes as the real ASCII
    label, then the real big-endian float32 image data immediately
    following it. Returns a `VirMosaic` (the existing, generically-named
    container from `ml/data/mosaic_reader.py` -- its field names are
    not VIR-specific)."""
    path = Path(path)
    with open(path, "rb") as fh:
        probe = fh.read(20_000)
        probe_values = _parse_pds3_label(probe.decode("ascii", errors="replace"))
        label_records = int(probe_values["LABEL_RECORDS"])
        record_bytes = int(probe_values["RECORD_BYTES"])
        header_bytes = label_records * record_bytes

        fh.seek(0)
        header = fh.read(header_bytes)
        label = Pds3MosaicLabel.parse(header.decode("ascii", errors="replace"))

        fh.seek(header_bytes)
        raw = fh.read(label.lines * label.samples * (label.sample_bits // 8))

    dtype = _DTYPE_MAP.get((label.sample_bits, label.sample_type))
    if dtype is None:
        raise ValueError(f"Unsupported PDS3 mosaic sample format: {label.sample_bits}-bit {label.sample_type}")

    arr = np.frombuffer(raw, dtype=dtype).reshape(label.lines, label.samples).astype(np.float32)
    nodata_mask = ~np.isfinite(arr) | (np.abs(arr - label.missing_constant) < 1.0) | (np.abs(arr) > 1.0e30)
    arr = np.where(nodata_mask, np.nan, arr)
    return VirMosaic(label=label, data=arr, path=path)


def read_center_filter_wavelength_nm(path: str | Path) -> float:
    """Reads the real `CENTER_FILTER_WAVELENGTH` field directly from a
    FC2 color-filter mosaic's own attached label -- never assumed from a
    generic Dawn FC filter table, per this project's established
    "verify, don't assume" discipline (mirrors the empirical longitude-
    sign confirmation already done for VIR in `ml/data/mosaic_reader.py`)."""
    path = Path(path)
    with open(path, "rb") as fh:
        probe = fh.read(20_000)
    values = _parse_pds3_label(probe.decode("ascii", errors="replace"))
    return float(values["CENTER_FILTER_WAVELENGTH"])
