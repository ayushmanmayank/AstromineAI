"""
Global-mosaic dataset, Stage 5: the real test set, touched exactly once,
here and nowhere else in this experiment (Stages 2 and 4 used only
train/val -- Stage 2's own confound-screen split was a separate,
coarser pixel-level sample used purely as an internal diagnostic before
any tile/model existed, never used to tune anything evaluated below).

Evaluates, on the identical real test tiles, for: a trivial baseline
(refit here on real tile-level features -- mean FC albedo + center
lat/lon -- for a fair apples-to-apples comparison against the deep
models on the same real test tiles), the best real ResNet-50
configuration (class-weighted), the best real ViT-B configuration
(baseline), and their ensemble (averaged softmax).

**What these labels measure, stated as plainly as every other label
scheme in this project: Band I (pyroxene absorption) center-wavelength
TERTILE bins from the real VIR global mosaic raster. NOT a validated
mineral-composition classification** -- see ml/data/mosaic_labels.py.

Also runs real Grad-CAM (ResNet-50) and real attention rollout (ViT-B)
on 6 real test tiles and reports, honestly, whether the highlighted
regions look like real brightness/shadow features rather than
composition.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_dataset import MosaicTileDataset  # noqa: E402
from ml.data.mosaic_labels import CLASS_NAMES  # noqa: E402
from ml.explainability.attention_viz import vit_attention_rollout  # noqa: E402
from ml.explainability.gradcam import generate_gradcam  # noqa: E402
from ml.models import cnn_resnet, vit_model  # noqa: E402

MANIFEST_PATH = "datasets/mosaic/manifests/tile_manifest.csv"
RESNET_CKPT = "trained_models/mosaic/resnet50_classweighted.pt"
VIT_CKPT = "trained_models/mosaic/vit_b_baseline.pt"
EXPLAIN_OUT_DIR = Path("docs/handoff/artifacts/mosaic_explainability")


def expected_calibration_error(confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> float:
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(confidences)
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (confidences > lo) & (confidences <= hi)
        if not np.any(mask):
            continue
        ece += (mask.sum() / n) * abs(correct[mask].mean() - confidences[mask].mean())
    return float(ece)


def report(name: str, labels: np.ndarray, preds: np.ndarray, confidences: np.ndarray) -> dict:
    correct = (preds == labels).astype(np.float64)
    acc = float(correct.mean())
    bal_acc = float(balanced_accuracy_score(labels, preds))
    macro_f1 = float(f1_score(labels, preds, average="macro", zero_division=0))
    ece = expected_calibration_error(confidences, correct)
    cm = confusion_matrix(labels, preds, labels=list(range(len(CLASS_NAMES))))
    counts = {CLASS_NAMES[i]: int((labels == i).sum()) for i in range(len(CLASS_NAMES))}
    print(f"\n=== {name} (TEST, touched once) ===")
    print(f"  n={len(labels)} class_counts={counts}")
    print(f"  accuracy={acc:.4f} balanced_accuracy={bal_acc:.4f} macro_f1={macro_f1:.4f} ece={ece:.4f}")
    print(f"  confusion_matrix={cm.tolist()}")
    return {"name": name, "n": len(labels), "class_counts": counts, "accuracy": acc,
            "balanced_accuracy": bal_acc, "macro_f1": macro_f1, "ece": ece, "confusion_matrix": cm.tolist()}


def trivial_baseline_features(rows: list[dict]) -> np.ndarray:
    feats = []
    for row in rows:
        img = np.asarray(Image.open(row["path"]).convert("L"), dtype=np.float32)
        albedo = float(img.mean())
        lat = float(row["center_lat"])
        lon_rad = np.deg2rad(float(row["center_lon"]))
        feats.append([albedo, lat, np.sin(lon_rad), np.cos(lon_rad)])
    return np.array(feats)


def load_manifest_rows(manifest_csv: str, split: str) -> list[dict]:
    with open(manifest_csv, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if row["split"] == split]


def main() -> int:
    print("Labels measure: Band I center TERTILE bins from the real VIR global")
    print("mosaic (ml/data/mosaic_labels.py). NOT a validated mineral-composition classification.\n")

    train_rows = load_manifest_rows(MANIFEST_PATH, "train")
    test_rows = load_manifest_rows(MANIFEST_PATH, "test")
    print(f"Real train tiles: {len(train_rows)}; real TEST tiles (touched once, now): {len(test_rows)}")

    # --- Trivial baseline, refit on real tile-level features for a fair
    # apples-to-apples comparison against the deep models on the SAME test tiles.
    X_train = trivial_baseline_features(train_rows)
    y_train = np.array([int(r["label"]) for r in train_rows])
    X_test = trivial_baseline_features(test_rows)
    y_test = np.array([int(r["label"]) for r in test_rows])

    rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    trivial_probs = rf.predict_proba(X_test)
    trivial_preds = trivial_probs.argmax(axis=1)
    trivial_conf = trivial_probs.max(axis=1)
    trivial_result = report("Trivial baseline (albedo+lat+lon, random forest, refit on tiles)", y_test, trivial_preds, trivial_conf)

    # --- Deep models ---
    device = "cpu"
    test_ds = MosaicTileDataset(MANIFEST_PATH, split="test")
    test_loader = DataLoader(test_ds, batch_size=16, shuffle=False)

    resnet = cnn_resnet.build_model(num_classes=len(CLASS_NAMES), pretrained=False)
    resnet.load_state_dict(torch.load(RESNET_CKPT, map_location=device))
    resnet.eval()

    vit = vit_model.build_model(num_classes=len(CLASS_NAMES), pretrained=False)
    vit.load_state_dict(torch.load(VIT_CKPT, map_location=device))
    vit.eval()

    resnet_probs_all, vit_probs_all, labels_all = [], [], []
    with torch.no_grad():
        for images, labels, _ids in test_loader:
            images = images.float()
            resnet_probs_all.append(F.softmax(resnet(images), dim=1).numpy())
            vit_probs_all.append(F.softmax(vit(images), dim=1).numpy())
            labels_all.append(labels.numpy())
    resnet_probs = np.concatenate(resnet_probs_all)
    vit_probs = np.concatenate(vit_probs_all)
    labels_arr = np.concatenate(labels_all)

    resnet_preds = resnet_probs.argmax(axis=1)
    resnet_conf = resnet_probs.max(axis=1)
    resnet_result = report("ResNet-50 (class-weighted)", labels_arr, resnet_preds, resnet_conf)

    vit_preds = vit_probs.argmax(axis=1)
    vit_conf = vit_probs.max(axis=1)
    vit_result = report("ViT-B (baseline)", labels_arr, vit_preds, vit_conf)

    ensemble_probs = (resnet_probs + vit_probs) / 2.0
    ensemble_preds = ensemble_probs.argmax(axis=1)
    ensemble_conf = ensemble_probs.max(axis=1)
    ensemble_result = report("Ensemble (ResNet-50 + ViT-B, averaged softmax)", labels_arr, ensemble_preds, ensemble_conf)

    # --- Explainability on 6 real test tiles ---
    EXPLAIN_OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Explainability on 6 real test tiles -> {EXPLAIN_OUT_DIR} ===")
    for i in range(min(6, len(test_ds))):
        array, label, tile_id = test_ds[i]
        tensor = torch.from_numpy(array).unsqueeze(0).float()
        with torch.no_grad():
            r_pred = int(F.softmax(resnet(tensor), dim=1).argmax(dim=1).item())
            v_pred = int(F.softmax(vit(tensor), dim=1).argmax(dim=1).item())
        gradcam = generate_gradcam(resnet, resnet.layer4, tensor, target_class=r_pred)
        rollout = vit_attention_rollout(vit, tensor)

        base_img = Image.fromarray((array[0] * 255).astype(np.uint8)).convert("L")
        gradcam_img = Image.fromarray((gradcam * 255).astype(np.uint8)).resize(base_img.size, Image.BILINEAR)
        rollout_img = Image.fromarray((rollout * 255).astype(np.uint8)).resize(base_img.size, Image.NEAREST)

        combined = Image.new("L", (base_img.width * 3 + 20, base_img.height + 20), color=255)
        combined.paste(base_img, (0, 20))
        combined.paste(gradcam_img, (base_img.width + 10, 20))
        combined.paste(rollout_img, (base_img.width * 2 + 20, 20))
        combined.save(EXPLAIN_OUT_DIR / f"{tile_id}_base_gradcam_rollout.png")
        print(f"  {tile_id}: true={CLASS_NAMES[label]} resnet_pred={CLASS_NAMES[r_pred]} vit_pred={CLASS_NAMES[v_pred]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
