"""
Global-mosaic dataset v3: real spatial-prior model candidates.

**What these models measure, stated as plainly as every other label
scheme in this project: a spatial-prior model predicts a tile's real
VIR Band I tertile class from its real tile-center LOCATION (and, for
some candidates, its real mean FC albedo). It is NOT a composition-
from-image model and must never be described as one** -- it cannot
classify an unlocated image, since (lat, lon) is a required input, not
an incidental one.

New, separate module (per this task's "new work goes in new files"
rule). Reuses nothing from ml/utils/mosaic_cv.py's splitting logic
directly (that module is imported, not modified, by the driver script
that calls these functions) -- this module only implements the model
candidates themselves:

  - random forest / gradient boosting on [albedo, lat, sin(lon), cos(lon)]
    (same real feature recipe as every trivial baseline in this project)
  - k-NN on (lat, sin(lon), cos(lon)) only, per this task's own spec,
    with k tuned on an inner validation split
  - a great-circle-distance kernel smoother on the sphere (lat, lon
    only): a Gaussian-kernel-weighted vote over real training points by
    real great-circle distance, with the kernel bandwidth tuned on an
    inner validation split -- the "kernel smoother" alternative this
    task's own brief explicitly offers in place of a full Gaussian
    Process classifier (simpler, faster, and honestly described as a
    kernel smoother, not oversold as a true GP).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score

EARTH_LIKE_RADIUS = 1.0  # great-circle distance computed in radians; radius cancels in ratios


def great_circle_distance_rad(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Real haversine great-circle angular distance (radians) between
    two real (lat, lon) arrays (degrees in, broadcasting as given)."""
    lat1r, lon1r, lat2r, lon2r = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2.0) ** 2
    a = np.clip(a, 0.0, 1.0)
    return 2.0 * np.arcsin(np.sqrt(a))


def build_tabular_features(albedo: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    lon_rad = np.deg2rad(lon)
    return np.column_stack([albedo, lat, np.sin(lon_rad), np.cos(lon_rad)])


def build_positional_features(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    lon_rad = np.deg2rad(lon)
    return np.column_stack([lat, np.sin(lon_rad), np.cos(lon_rad)])


class GreatCircleKernelSmoother:
    """Real Gaussian-kernel-weighted vote over real training points by
    real great-circle distance (degrees-equivalent bandwidth). Not a
    true Gaussian Process -- a simpler, faster kernel smoother, as this
    task's own brief explicitly allows in place of one."""

    def __init__(self, bandwidth_deg: float, n_classes: int):
        self.bandwidth_rad = np.deg2rad(bandwidth_deg)
        self.n_classes = n_classes
        self.train_lat = None
        self.train_lon = None
        self.train_y = None

    def fit(self, lat: np.ndarray, lon: np.ndarray, y: np.ndarray) -> "GreatCircleKernelSmoother":
        self.train_lat = np.asarray(lat, dtype=np.float64)
        self.train_lon = np.asarray(lon, dtype=np.float64)
        self.train_y = np.asarray(y, dtype=np.int64)
        return self

    def predict_proba(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        lat, lon = np.asarray(lat, dtype=np.float64), np.asarray(lon, dtype=np.float64)
        probs = np.zeros((len(lat), self.n_classes))
        for i in range(len(lat)):
            d = great_circle_distance_rad(lat[i], lon[i], self.train_lat, self.train_lon)
            w = np.exp(-0.5 * (d / self.bandwidth_rad) ** 2)
            w_sum = w.sum()
            if w_sum < 1e-12:
                probs[i] = 1.0 / self.n_classes
                continue
            for c in range(self.n_classes):
                probs[i, c] = w[self.train_y == c].sum() / w_sum
        return probs

    def predict(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        return self.predict_proba(lat, lon).argmax(axis=1)


class GreatCircleKNN:
    """Real k-NN on (lat, lon) only, using real great-circle distance
    (not naive Euclidean on sin/cos features, so neighbor selection
    respects real spherical geometry), per this task's own spec."""

    def __init__(self, k: int, n_classes: int):
        self.k = k
        self.n_classes = n_classes
        self.train_lat = None
        self.train_lon = None
        self.train_y = None

    def fit(self, lat: np.ndarray, lon: np.ndarray, y: np.ndarray) -> "GreatCircleKNN":
        self.train_lat = np.asarray(lat, dtype=np.float64)
        self.train_lon = np.asarray(lon, dtype=np.float64)
        self.train_y = np.asarray(y, dtype=np.int64)
        return self

    def predict_proba(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        lat, lon = np.asarray(lat, dtype=np.float64), np.asarray(lon, dtype=np.float64)
        probs = np.zeros((len(lat), self.n_classes))
        k = min(self.k, len(self.train_lat))
        for i in range(len(lat)):
            d = great_circle_distance_rad(lat[i], lon[i], self.train_lat, self.train_lon)
            nearest = np.argpartition(d, k - 1)[:k]
            labels = self.train_y[nearest]
            counts = np.bincount(labels, minlength=self.n_classes)
            probs[i] = counts / counts.sum()
        return probs

    def predict(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        return self.predict_proba(lat, lon).argmax(axis=1)


@dataclass
class TunedResult:
    name: str
    hyperparam: object
    model: object


def tune_and_fit_knn(train_lat, train_lon, train_y, val_lat, val_lon, val_y, n_classes: int,
                      k_candidates=(3, 5, 7, 10, 15, 20, 30, 50)) -> TunedResult:
    best = None
    for k in k_candidates:
        if k >= len(train_lat):
            continue
        model = GreatCircleKNN(k=k, n_classes=n_classes).fit(train_lat, train_lon, train_y)
        pred = model.predict(val_lat, val_lon)
        score = balanced_accuracy_score(val_y, pred)
        if best is None or score > best[0]:
            best = (score, k, model)
    score, k, _ = best
    # Refit on train+val with the chosen k for the final model used at test time.
    full_lat = np.concatenate([train_lat, val_lat])
    full_lon = np.concatenate([train_lon, val_lon])
    full_y = np.concatenate([train_y, val_y])
    final_model = GreatCircleKNN(k=k, n_classes=n_classes).fit(full_lat, full_lon, full_y)
    return TunedResult(name="knn", hyperparam=k, model=final_model)


def tune_and_fit_kernel_smoother(train_lat, train_lon, train_y, val_lat, val_lon, val_y, n_classes: int,
                                  bandwidth_candidates=(2.0, 5.0, 10.0, 20.0, 30.0, 50.0)) -> TunedResult:
    best = None
    for bw in bandwidth_candidates:
        model = GreatCircleKernelSmoother(bandwidth_deg=bw, n_classes=n_classes).fit(train_lat, train_lon, train_y)
        pred = model.predict(val_lat, val_lon)
        score = balanced_accuracy_score(val_y, pred)
        if best is None or score > best[0]:
            best = (score, bw, model)
    score, bw, _ = best
    full_lat = np.concatenate([train_lat, val_lat])
    full_lon = np.concatenate([train_lon, val_lon])
    full_y = np.concatenate([train_y, val_y])
    final_model = GreatCircleKernelSmoother(bandwidth_deg=bw, n_classes=n_classes).fit(full_lat, full_lon, full_y)
    return TunedResult(name="kernel_smoother", hyperparam=bw, model=final_model)


def fit_random_forest(X_train: np.ndarray, y_train: np.ndarray, seed: int = 42) -> RandomForestClassifier:
    model = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1)
    model.fit(X_train, y_train)
    return model


def fit_gradient_boosting(X_train: np.ndarray, y_train: np.ndarray, seed: int = 42) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(max_iter=200, random_state=seed)
    model.fit(X_train, y_train)
    return model
