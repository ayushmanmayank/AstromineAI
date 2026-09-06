"""
Classical ML baseline (Month 1 proposal's 3-way comparison, arm 1 of 3):
logistic regression / random forest over simple flattened pixel features.

Real, runnable scikit-learn code — not a stub — but it has never been run
against real labeled data, because there is none yet (Month 1 slice 3:
0 surviving image-spectrum pairs). `train_baseline()` raises clearly
rather than silently "succeeding" on an empty dataset.
"""

from __future__ import annotations

import logging

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

from ml.data.dataset import VestaDataset

logger = logging.getLogger("baseline")


def _flatten_dataset(dataset: VestaDataset) -> tuple[np.ndarray, np.ndarray]:
    if len(dataset) == 0:
        raise ValueError(
            f"VestaDataset(split={dataset.split!r}) has 0 samples — cannot train or "
            f"evaluate a baseline on it. See docs/month1_log.md for why."
        )
    X, y = [], []
    for i in range(len(dataset)):
        image, label_idx, _region_id = dataset[i]
        X.append(np.asarray(image).reshape(-1))
        y.append(label_idx)
    return np.stack(X), np.array(y)


def train_baseline(
    train_dataset: VestaDataset,
    model_type: str = "logreg",
    random_state: int = 42,
):
    """Train a scikit-learn baseline. model_type: 'logreg' or 'random_forest'."""
    X_train, y_train = _flatten_dataset(train_dataset)

    if model_type == "logreg":
        model = LogisticRegression(max_iter=1000, random_state=random_state)
    elif model_type == "random_forest":
        model = RandomForestClassifier(n_estimators=200, random_state=random_state)
    else:
        raise ValueError(f"Unknown model_type: {model_type!r}")

    model.fit(X_train, y_train)
    logger.info("Trained %s baseline on %d samples", model_type, len(y_train))
    return model


def evaluate_baseline(model, eval_dataset: VestaDataset) -> dict:
    X, y_true = _flatten_dataset(eval_dataset)
    y_pred = model.predict(X)
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "n_samples": len(y_true),
        "classification_report": report,
    }
