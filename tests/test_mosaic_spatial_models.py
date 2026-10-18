"""Tests for ml/utils/mosaic_spatial_models.py -- real spatial-prior
model candidates for the global-mosaic v3 task."""

from __future__ import annotations

import numpy as np

from ml.utils.mosaic_spatial_models import (
    GreatCircleKernelSmoother,
    GreatCircleKNN,
    build_positional_features,
    build_tabular_features,
    great_circle_distance_rad,
    tune_and_fit_kernel_smoother,
    tune_and_fit_knn,
)


def test_great_circle_distance_zero_for_same_point():
    d = great_circle_distance_rad(10.0, 20.0, 10.0, 20.0)
    assert abs(d) < 1e-9


def test_great_circle_distance_antipodal_is_pi():
    d = great_circle_distance_rad(0.0, 0.0, 0.0, 180.0)
    assert abs(d - np.pi) < 1e-6


def test_great_circle_distance_quarter_globe():
    # North pole to equator is a quarter of a great circle (pi/2 rad).
    d = great_circle_distance_rad(90.0, 0.0, 0.0, 0.0)
    assert abs(d - np.pi / 2) < 1e-6


def test_build_tabular_features_shape():
    X = build_tabular_features(np.array([1.0, 2.0]), np.array([10.0, -10.0]), np.array([0.0, 180.0]))
    assert X.shape == (2, 4)


def test_build_positional_features_shape():
    X = build_positional_features(np.array([10.0, -10.0]), np.array([0.0, 180.0]))
    assert X.shape == (2, 3)


def test_knn_predicts_nearest_class():
    # Two tight clusters of training points, far apart on the sphere;
    # a query point near cluster A's center should be classified A.
    train_lat = np.array([0.0, 0.1, -0.1, 80.0, 80.1, 79.9])
    train_lon = np.array([0.0, 0.1, -0.1, 0.0, 0.1, -0.1])
    train_y = np.array([0, 0, 0, 1, 1, 1])
    model = GreatCircleKNN(k=3, n_classes=2).fit(train_lat, train_lon, train_y)
    pred = model.predict(np.array([0.05]), np.array([0.0]))
    assert pred[0] == 0


def test_kernel_smoother_predicts_nearest_class():
    train_lat = np.array([0.0, 0.1, -0.1, 80.0, 80.1, 79.9])
    train_lon = np.array([0.0, 0.1, -0.1, 0.0, 0.1, -0.1])
    train_y = np.array([0, 0, 0, 1, 1, 1])
    model = GreatCircleKernelSmoother(bandwidth_deg=5.0, n_classes=2).fit(train_lat, train_lon, train_y)
    pred = model.predict(np.array([0.05]), np.array([0.0]))
    assert pred[0] == 0


def test_kernel_smoother_far_point_falls_back_to_uniform_ish():
    # With a tiny bandwidth, a query far from all training points should
    # get (near-)uniform probabilities rather than crash or pick a
    # class arbitrarily.
    train_lat = np.array([0.0, 0.1])
    train_lon = np.array([0.0, 0.1])
    train_y = np.array([0, 1])
    model = GreatCircleKernelSmoother(bandwidth_deg=0.001, n_classes=2).fit(train_lat, train_lon, train_y)
    probs = model.predict_proba(np.array([89.0]), np.array([179.0]))
    assert abs(probs[0, 0] - 0.5) < 1e-6


def test_tune_and_fit_knn_is_deterministic():
    rng = np.random.default_rng(0)
    n = 60
    lat = rng.uniform(-80, 80, n)
    lon = rng.uniform(0, 360, n)
    y = (lat > 0).astype(int)
    split = 40
    r1 = tune_and_fit_knn(lat[:split], lon[:split], y[:split], lat[split:], lon[split:], y[split:], n_classes=2)
    r2 = tune_and_fit_knn(lat[:split], lon[:split], y[:split], lat[split:], lon[split:], y[split:], n_classes=2)
    assert r1.hyperparam == r2.hyperparam


def test_tune_and_fit_kernel_smoother_is_deterministic():
    rng = np.random.default_rng(0)
    n = 60
    lat = rng.uniform(-80, 80, n)
    lon = rng.uniform(0, 360, n)
    y = (lat > 0).astype(int)
    split = 40
    r1 = tune_and_fit_kernel_smoother(lat[:split], lon[:split], y[:split], lat[split:], lon[split:], y[split:], n_classes=2)
    r2 = tune_and_fit_kernel_smoother(lat[:split], lon[:split], y[:split], lat[split:], lon[split:], y[split:], n_classes=2)
    assert r1.hyperparam == r2.hyperparam
