"""
PDS data acquisition for AstroMineAI — Month 1, Slice 1.

Scope of this module (deliberately narrow):
    - Enumerate Dawn Framing Camera (FC2) and Dawn VIR products for the
      Vesta mission phase from the PDS Small Bodies Node (SBN) archive.
    - Download each product's data file *and* its accompanying .LBL label
      file (which carries mission/instrument/dataset/time/geometry
      metadata) into `datasets/raw/`.

Explicitly OUT of scope for this module (next Month 1 slices):
    - Spatial alignment between FC images and VIR cubes.
    - Labeling / ground-truth generation.
    - Train/val/test splitting.

See docs/scientific_integrity_checklist.md for the constraints this file
is written to satisfy, and configs/config.yaml for the verified PDS URLs
it reads from (no URL is hardcoded here — everything comes from config).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("pds_acquisition")

# Suffixes on VIR PRODUCT_ID that mark ancillary (non-cube) records rather
# than the primary spectral data cube for that observation.
_VIR_ANCILLARY_SUFFIXES = ("_HK", "_QQ")


@dataclass
class PDSProduct:
    """One acquired PDS data product: a data file plus its label."""

    product_id: str
    dataset_id: str
    instrument: str
    target: str
    volume_id: str
    start_time: Optional[str]
    stop_time: Optional[str]
    label_url: str
    data_url: str
    label_path: Optional[str] = None
    data_path: Optional[str] = None
    downloaded: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Config / HTTP plumbing
# --------------------------------------------------------------------------


def load_config(config_path: str | Path = "configs/config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_session(config: dict) -> requests.Session:
    acq_cfg = config.get("acquisition", {})
    retries = acq_cfg.get("retries", 3)
    backoff = acq_cfg.get("retry_backoff_seconds", 2)

    session = requests.Session()
    session.headers.update(
        {"User-Agent": acq_cfg.get("user_agent", "AstroMineAI-DataAcquisition/0.1")}
    )
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# --------------------------------------------------------------------------
# PDS3 INDEX.TAB parsing
# --------------------------------------------------------------------------


def _fetch_text(url: str, session: requests.Session, timeout: int) -> str:
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_index_table(
    index_url: str, session: requests.Session, timeout: int = 60
) -> list[dict]:
    """Parse a PDS3 INDEX.TAB (comma-separated, quoted, fixed-length rows).

    Returns a list of dicts keyed by the header row's column names, with
    every value stripped of the fixed-width padding whitespace PDS3 pads
    quoted strings with.
    """
    raw = _fetch_text(index_url, session, timeout)
    reader = csv.reader(io.StringIO(raw), skipinitialspace=True)
    rows = [ [c.strip() for c in row] for row in reader if row ]
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    records = []
    for row in rows[1:]:
        if len(row) != len(header):
            logger.warning("Skipping malformed index row (column mismatch): %r", row)
            continue
        records.append(dict(zip(header, row)))
    return records


def _parse_pds_time(raw: Optional[str]) -> Optional[datetime]:
    """Parse an INDEX.TAB START_TIME value. Dawn labels use two formats
    depending on instrument: day-of-year (FC, e.g. '2011-123T13:35:16.604')
    and calendar date (VIR, e.g. '2011-05-10T06:10:36.974')."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%jT%H:%M:%S.%f", "%Y-%jT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def filter_rows_by_phase(rows: list[dict], phase_window: dict) -> list[dict]:
    """Filter parsed INDEX.TAB rows to those whose START_TIME falls within
    `phase_window` = {'start': ISO date, 'stop': ISO date} (inclusive).

    This filters by real observation timestamp, not by guessing at each
    instrument's mission-phase directory-naming convention — FC's PDS3
    directories are day-of-year-dated (e.g. '2011272_HAMO') and VIR's are
    calendar-dated (e.g. '20110929_HAMO'); filtering on the row's own
    parsed START_TIME sidesteps needing to reconcile those two formats or
    re-derive per-volume directory paths, and works identically for both
    instruments. See configs/config.yaml's data.mission_phases for the
    real, verified phase date ranges this pulls from (confirmed against
    the live archive's directory listings — see docs/month1_log.md).
    """
    start = datetime.strptime(phase_window["start"], "%Y-%m-%d")
    stop = datetime.strptime(phase_window["stop"], "%Y-%m-%d")
    filtered = []
    for row in rows:
        row_time = _parse_pds_time(row.get("START_TIME"))
        if row_time is not None and start <= row_time <= stop:
            filtered.append(row)
    return filtered


def _resolve_url(base_url: str, file_spec: str) -> str:
    """Join a PDS volume base_url with a FILE_SPECIFICATION_NAME.

    FILE_SPECIFICATION_NAME values look like '/DATA/FITS/.../FOO.LBL' —
    the leading slash is relative to the *volume* root (base_url), not an
    absolute path on the server, so a plain urljoin would discard the
    volume path. Strip the leading slash and join explicitly instead.
    """
    return urljoin(base_url if base_url.endswith("/") else base_url + "/", file_spec.lstrip("/"))


def _local_path_for(output_dir: Path, volume_id: str, file_spec: str) -> Path:
    """Mirror the PDS volume's internal directory structure on local disk."""
    return output_dir / volume_id / Path(file_spec.lstrip("/"))


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------


def _download_file(
    url: str, dest_path: Path, session: requests.Session, timeout: int
) -> tuple[bool, Optional[str]]:
    """Download `url` to `dest_path`, skipping if already present and non-empty."""
    try:
        if dest_path.exists() and dest_path.stat().st_size > 0:
            logger.debug("Already have %s, skipping", dest_path)
            return True, None

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with session.get(url, timeout=timeout, stream=True) as resp:
            resp.raise_for_status()
            tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")
            with open(tmp_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        fh.write(chunk)
            if tmp_path.stat().st_size == 0:
                tmp_path.unlink(missing_ok=True)
                return False, f"downloaded 0 bytes from {url}"
            tmp_path.replace(dest_path)
        return True, None
    except requests.RequestException as exc:
        return False, str(exc)


def _write_manifest(products: list[PDSProduct], manifest_path: Path) -> None:
    """Append-write a JSONL manifest recording metadata for each product.

    This is a convenience index on top of the retained .LBL files — it
    does NOT replace them. The .LBL files remain the authoritative,
    original PDS metadata record for each product and are never deleted.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "a", encoding="utf-8") as fh:
        for product in products:
            fh.write(json.dumps(product.to_dict()) + "\n")


# --------------------------------------------------------------------------
# Public fetch functions
# --------------------------------------------------------------------------


def fetch_framing_camera_images(
    config: dict,
    limit: Optional[int] = None,
    level: Optional[str] = None,
    phase: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[PDSProduct]:
    """Fetch Dawn FC2 Vesta images (+ .LBL files) per configs/config.yaml.

    Parameters
    ----------
    config: the loaded configs/config.yaml dict.
    limit: only download the first `limit` products (for smoke-testing).
    level: 'raw' or 'calibrated'; defaults to config's declared default.
    phase: a key into config's data.mission_phases (e.g. 'hamo_cycle1'),
        or None for no phase filtering (chronologically first `limit`
        rows in the volume, which as of Month 1 Slice 2 means approach-
        phase OpNav frames with no footprint geometry — see
        docs/month1_log.md). Filters INDEX.TAB rows by real START_TIME,
        not by guessing at a phase directory name.
    """
    src_cfg = config["data"]["sources"]["dawn_fc_vesta"]
    level = level or src_cfg.get("level", "calibrated")
    sub_cfg = src_cfg[level]

    acq_cfg = config.get("acquisition", {})
    timeout = acq_cfg.get("request_timeout_seconds", 60)
    session = session or _build_session(config)

    raw_dir = Path(config["data"]["raw_dir"]) / "dawn_fc_vesta"

    logger.info(
        "Fetching Dawn FC2 Vesta images: dataset_id=%s volume_id=%s level=%s phase=%s",
        sub_cfg["dataset_id"], sub_cfg["volume_id"], level, phase,
    )
    rows = parse_index_table(sub_cfg["index_url"], session, timeout)
    logger.info("INDEX.TAB lists %d FC products for volume %s", len(rows), sub_cfg["volume_id"])

    if phase is not None:
        phase_window = config["data"]["mission_phases"][phase]
        rows = filter_rows_by_phase(rows, phase_window)
        logger.info("%d FC rows fall within phase=%s (%s to %s)", len(rows), phase, phase_window["start"], phase_window["stop"])

    if limit is not None:
        rows = rows[:limit]

    products: list[PDSProduct] = []
    for row in rows:
        file_spec = row["FILE_SPECIFICATION_NAME"]  # points at the .LBL
        label_url = _resolve_url(sub_cfg["base_url"], file_spec)
        data_url = label_url.rsplit(".", 1)[0] + ".FIT"
        label_path = _local_path_for(raw_dir, sub_cfg["volume_id"], file_spec)
        data_path = label_path.with_suffix(".FIT")

        product = PDSProduct(
            product_id=row.get("PRODUCT_ID", ""),
            dataset_id=row.get("DATA_SET_ID", sub_cfg["dataset_id"]),
            instrument=row.get("INSTRUMENT_ID", src_cfg.get("instrument", "FC2")),
            target=src_cfg.get("target", "VESTA"),
            volume_id=row.get("VOLUME_ID", sub_cfg["volume_id"]),
            start_time=row.get("START_TIME"),
            stop_time=row.get("STOP_TIME"),
            label_url=label_url,
            data_url=data_url,
            label_path=str(label_path),
            data_path=str(data_path),
        )

        ok_label, err_label = _download_file(label_url, label_path, session, timeout)
        ok_data, err_data = _download_file(data_url, data_path, session, timeout)
        product.downloaded = ok_label and ok_data
        if not product.downloaded:
            product.error = err_label or err_data
            logger.warning("Failed to fully download FC product %s: %s", product.product_id, product.error)
        products.append(product)

    _write_manifest(products, raw_dir / "manifest.jsonl")
    return products


def fetch_vir_spectra(
    config: dict,
    limit: Optional[int] = None,
    level: Optional[str] = None,
    channels: Optional[Iterable[str]] = None,
    phase: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[PDSProduct]:
    """Fetch Dawn VIR Vesta spectral cubes (+ .LBL files) per config.

    Parameters
    ----------
    config: the loaded configs/config.yaml dict.
    limit: only download the first `limit` products *per channel*.
    level: 'raw' (EDR, *1A volumes) or 'calibrated' (RDR, *1B volumes);
        defaults to config's declared default ('raw' — DWNVVIR_V1A /
        DWNVVIR_I1A, per the verified sources in configs/config.yaml).
    channels: subset of {'ir', 'vis'}; defaults to config's declared channels.
    phase: a key into config's data.mission_phases (e.g. 'hamo_cycle1'),
        or None for no phase filtering — see fetch_framing_camera_images().
    """
    src_cfg = config["data"]["sources"]["dawn_vir_vesta"]
    level = level or src_cfg.get("level", "raw")
    channels = list(channels) if channels else src_cfg.get("channels", ["ir", "vis"])

    acq_cfg = config.get("acquisition", {})
    timeout = acq_cfg.get("request_timeout_seconds", 60)
    session = session or _build_session(config)

    raw_dir = Path(config["data"]["raw_dir"]) / "dawn_vir_vesta"

    all_products: list[PDSProduct] = []
    for channel in channels:
        sub_cfg = src_cfg[level][channel]
        logger.info(
            "Fetching Dawn VIR Vesta spectra: channel=%s dataset_id=%s volume_id=%s level=%s",
            channel, sub_cfg["dataset_id"], sub_cfg["volume_id"], level,
        )
        rows = parse_index_table(sub_cfg["index_url"], session, timeout)
        logger.info(
            "INDEX.TAB lists %d VIR %s rows for volume %s",
            len(rows), channel, sub_cfg["volume_id"],
        )

        # Keep only primary spectral-cube records; drop housekeeping (_HK)
        # and quaternion/pointing (_QQ) ancillary rows, which are not cubes.
        science_rows = [
            r for r in rows
            if not r.get("PRODUCT_ID", "").rstrip().endswith(_VIR_ANCILLARY_SUFFIXES)
        ]
        logger.info(
            "%d of %d VIR %s rows are primary spectral cubes (rest are HK/QQ ancillary)",
            len(science_rows), len(rows), channel,
        )

        if phase is not None:
            phase_window = config["data"]["mission_phases"][phase]
            science_rows = filter_rows_by_phase(science_rows, phase_window)
            logger.info(
                "%d VIR %s rows fall within phase=%s (%s to %s)",
                len(science_rows), channel, phase, phase_window["start"], phase_window["stop"],
            )

        if limit is not None:
            science_rows = science_rows[:limit]

        for row in science_rows:
            file_spec = row["FILE_SPECIFICATION_NAME"]  # points at the .LBL
            label_url = _resolve_url(sub_cfg["base_url"], file_spec)
            data_url = label_url.rsplit(".", 1)[0] + ".QUB"
            label_path = _local_path_for(raw_dir, sub_cfg["volume_id"], file_spec)
            data_path = label_path.with_suffix(".QUB")

            product = PDSProduct(
                product_id=row.get("PRODUCT_ID", ""),
                dataset_id=row.get("DATA_SET_ID", sub_cfg["dataset_id"]),
                instrument=f"VIR-{channel.upper()}",
                target=src_cfg.get("target", "VESTA"),
                volume_id=row.get("VOLUME_ID", sub_cfg["volume_id"]),
                start_time=row.get("START_TIME"),
                stop_time=row.get("STOP_TIME"),
                label_url=label_url,
                data_url=data_url,
                label_path=str(label_path),
                data_path=str(data_path),
            )

            ok_label, err_label = _download_file(label_url, label_path, session, timeout)
            ok_data, err_data = _download_file(data_url, data_path, session, timeout)
            product.downloaded = ok_label and ok_data
            if not product.downloaded:
                product.error = err_label or err_data
                logger.warning("Failed to fully download VIR product %s: %s", product.product_id, product.error)
            all_products.append(product)

    _write_manifest(all_products, raw_dir / "manifest.jsonl")
    return all_products


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument(
        "--instrument", choices=["fc", "vir", "both"], default="both",
        help="Which instrument to pull. Default: both.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only fetch the first N products (per instrument/channel). Use a small "
             "value first to validate the pipeline before a full pull.",
    )
    parser.add_argument(
        "--phase", default=None,
        help="A key into config's data.mission_phases (e.g. 'hamo_cycle1') to filter "
             "products by real observation time, instead of taking the chronologically "
             "first N rows in the volume (which is approach-phase OpNav data with no "
             "footprint geometry — see docs/month1_log.md).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    session = _build_session(config)

    fc_products: list[PDSProduct] = []
    vir_products: list[PDSProduct] = []

    t0 = time.time()
    if args.instrument in ("fc", "both"):
        fc_products = fetch_framing_camera_images(config, limit=args.limit, phase=args.phase, session=session)
    if args.instrument in ("vir", "both"):
        vir_products = fetch_vir_spectra(config, limit=args.limit, phase=args.phase, session=session)
    elapsed = time.time() - t0

    fc_ok = sum(1 for p in fc_products if p.downloaded)
    vir_ok = sum(1 for p in vir_products if p.downloaded)

    logger.info(
        "Done in %.1fs — FC images: %d/%d downloaded, VIR cubes: %d/%d downloaded",
        elapsed, fc_ok, len(fc_products), vir_ok, len(vir_products),
    )

    failures = [p for p in (fc_products + vir_products) if not p.downloaded]
    if failures:
        logger.warning("%d product(s) failed to download fully:", len(failures))
        for p in failures[:20]:
            logger.warning("  %s: %s", p.product_id, p.error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
