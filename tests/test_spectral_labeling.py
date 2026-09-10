"""
Regression tests for Month 1 Slice 13 -- the fix for the band-center
instability Slice 12 diagnosed in compute_band_center().

Uses a self-contained synthetic Band II window (not real downloaded PDS
files, matching this test suite's existing hermetic style -- see
tests/test_spatial_alignment.py) built to reproduce the exact failure
mode Slice 12 found on real HAMO/LAMO data: two near-tied local minima
roughly 0.2 um apart (here at 1.957 and 2.165 um, the same real cluster
wavelengths), on the same ~0.0095 um grid spacing as VIR's real
BAND_BIN_CENTER. compute_band_center() (left unmodified) is used here
only as a documented "before" reference -- it is not the function under
test.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.data.spectral_labeling import (
    compute_band_center,
    compute_band_center_v2,
)

BAND_II_WINDOW_UM = (1.65, 2.50)
_GRID_SPACING_UM = 0.0095  # matches VIR's real IR BAND_BIN_CENTER spacing near 2 um (Slice 12, step 1)


def _synthetic_wavelengths() -> np.ndarray:
    return np.arange(BAND_II_WINDOW_UM[0], BAND_II_WINDOW_UM[1] + 1e-9, _GRID_SPACING_UM)


def _gaussian_dip(w: np.ndarray, center: float, width: float, depth: float) -> np.ndarray:
    return depth * np.exp(-0.5 * ((w - center) / width) ** 2)


def _two_near_tied_minima_spectrum(d1: float = 0.37, d2: float = 0.372, width: float = 0.06) -> tuple[np.ndarray, np.ndarray]:
    """A synthetic continuum-removed-equivalent curve (endpoints ~1.0, so
    compute_band_center()'s own linear continuum removal is a no-op) with
    two nearly-equal-depth absorption dips at the real 1.957/2.165 um
    cluster wavelengths Slice 12 found -- d1/d2 differing by ~0.5%,
    comfortably inside the <2% margin Slice 12 measured on real spectra."""
    w = _synthetic_wavelengths()
    spectrum = 1.0 - _gaussian_dip(w, 1.957, width, d1) - _gaussian_dip(w, 2.165, width, d2)
    return w, spectrum


def _single_clean_minimum_spectrum(true_center: float = 1.95, depth: float = 0.35, width: float = 0.12) -> tuple[np.ndarray, np.ndarray]:
    """A single, broad, unambiguous absorption feature -- no near-tied
    competing minimum anywhere in the window."""
    w = _synthetic_wavelengths()
    spectrum = (1.0 - _gaussian_dip(w, true_center, width, depth))
    return w, spectrum


class TestPerturbationStability:
    """Direct regression test for Slice 12's finding: compute_band_center()
    discretely snaps between two real cluster values under realistic
    noise; compute_band_center_v2() must not."""

    @pytest.mark.parametrize("noise_frac", [0.001, 0.005, 0.01])
    def test_v2_output_spread_stays_tight_under_noise(self, noise_frac):
        w, spectrum = _two_near_tied_minima_spectrum()
        centers = []
        for seed in range(20):
            rng = np.random.default_rng(seed)
            noisy = spectrum + rng.normal(0, noise_frac, size=spectrum.shape)
            result = compute_band_center_v2(w, noisy, *BAND_II_WINDOW_UM)
            assert result is not None
            centers.append(result.center_um)

        spread = max(centers) - min(centers)
        # The old method's spread on this exact synthetic case is ~0.21-0.23 um
        # (a hard jump between the two ~0.2 um-separated cluster values) at
        # every one of these noise levels -- see test below. v2 must stay
        # well under that, growing only gradually with noise amplitude.
        assert spread < 0.15, (
            f"compute_band_center_v2 output spread {spread:.4f} um at "
            f"{noise_frac*100:.1f}% noise is not tight -- possible regression "
            f"of the Slice 13 fix"
        )

    def test_v1_reproduces_the_diagnosed_jump_on_this_synthetic_case(self):
        """Not a test of new code -- documents that this synthetic fixture
        actually reproduces Slice 12's diagnosed failure mode on the
        unmodified, protected compute_band_center(), so the "v2 stays
        tight" assertions above are a meaningful contrast, not a test
        against a strawman."""
        w, spectrum = _two_near_tied_minima_spectrum()
        centers = []
        for seed in range(20):
            rng = np.random.default_rng(seed)
            noisy = spectrum + rng.normal(0, 0.005, size=spectrum.shape)
            centers.append(compute_band_center(w, noisy, *BAND_II_WINDOW_UM))
        spread = max(centers) - min(centers)
        assert spread > 0.15, (
            "expected the unmodified compute_band_center() to reproduce a "
            "large discrete jump on this synthetic near-tied-minima fixture"
        )


class TestSingleMinimumCorrectness:
    """compute_band_center_v2() must still find the obvious real minimum,
    unambiguously, on a spectrum with no near-tied competitor."""

    def test_v2_finds_the_true_center_and_reports_unambiguous(self):
        true_center = 1.95
        w, spectrum = _single_clean_minimum_spectrum(true_center=true_center)
        result = compute_band_center_v2(w, spectrum, *BAND_II_WINDOW_UM)
        assert result is not None
        assert abs(result.center_um - true_center) < 0.01
        assert result.ambiguous is False
        assert result.n_candidates == 1
        assert result.confidence == pytest.approx(1.0)

    def test_v2_matches_v1_on_a_clean_single_minimum(self):
        """On an unambiguous feature, the fix should not change the
        answer -- both methods are fitting the same single local minimum."""
        w, spectrum = _single_clean_minimum_spectrum()
        old = compute_band_center(w, spectrum, *BAND_II_WINDOW_UM)
        new = compute_band_center_v2(w, spectrum, *BAND_II_WINDOW_UM)
        assert new is not None and old is not None
        assert abs(new.center_um - old) < 1e-6
