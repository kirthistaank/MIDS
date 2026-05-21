"""Evaluation pipeline: metrics, confusion matrices, optional McNemar test."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
    precision_score,
    recall_score,
)

from zeroshot.classifier import ZeroShotClassifier
from zeroshot.labels import DATASET_CONFIGS, DatasetConfig, to_zs_label
from zeroshot.parsing import coerce_text


def _package_project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def canonical_project_root(start: Optional[str] = None) -> str:
    """Resolve to the repo root containing `zeroshot/__init__.py`.

    Works even if `start` points at `training_data/` or another subfolder under the repo.
    """
    pkg_root = _package_project_root()
    if not start:
        return pkg_root.rstrip(os.sep) + os.sep
    probe = os.path.normpath(os.path.expandvars(os.path.expanduser(start.strip().rstrip(os.sep))))
    for _ in range(12):
        if os.path.isfile(os.path.join(probe, "zeroshot", "__init__.py")):
            return probe.rstrip(os.sep) + os.sep
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return pkg_root.rstrip(os.sep) + os.sep


def resolve_base_dir() -> str:
    """Project root containing `zeroshot/` (and bundled CSVs under `training_data/...`)."""
    if os.getenv("COLAB_RELEASE_TAG"):
        raw = os.getenv(
            "ZEROSHOT_BASE_DIR",
            "/content/gdrive/MyDrive/Colab Notebooks/d266/FinalProject/",
        ).strip()
        return canonical_project_root(raw)

    raw = os.getenv("ZEROSHOT_BASE_DIR")
    if raw and raw.strip():
        return canonical_project_root(raw.strip())

    return canonical_project_root(None)


def load_split_df(config: DatasetConfig, split: str, base_dir: str) -> pd.DataFrame:
    base_dir = canonical_project_root(base_dir)
    bundled = config.bundled_val if split == "validation" else config.bundled_test

    candidates = [
        os.path.join(base_dir, bundled) if bundled else "",
        os.path.join(base_dir, config.subfolder, config.val_csv if split == "validation" else config.test_csv),
        os.path.join(base_dir, config.val_csv if split == "validation" else config.test_csv),
    ]
    path = next((p for p in candidates if p and os.path.isfile(p)), None)
    if path is None:
        raise FileNotFoundError(
            f"No {split} CSV found for {config.key}. Tried: " + ", ".join(c for c in candidates if c)
        )
    df = pd.read_csv(path)
    if config.text_column not in df.columns:
        for alt in ("text", "statement", "medical_abstract", "review"):
            if alt in df.columns:
                df = df.rename(columns={alt: config.text_column})
                break
    if config.label_column not in df.columns:
        for alt in ("label", "labels", "status_combined", "condition_label", "rating"):
            if alt in df.columns:
                df = df.rename(columns={alt: config.label_column})
                break

    if config.text_column in df.columns:
        df[config.text_column] = df[config.text_column].map(lambda x: coerce_text(x, max_len=None))
        df = df[df[config.text_column].str.len() > 0].reset_index(drop=True)
    return df


def evaluate_zero_shot(
    df: pd.DataFrame,
    config_key: str,
    classifier: ZeroShotClassifier,
    dataset_name: str = "validation",
    batch_size: int = 1,
    max_samples: Optional[int] = None,
    results_dir: str = "Results",
) -> Dict:
    """Run zero-shot evaluation and save metrics / artifacts."""
    config = DATASET_CONFIGS[config_key]
    df = df.copy()
    if max_samples:
        df = df.head(max_samples)

    texts = df[config.text_column].tolist()
    raw_labels = df[config.label_column].tolist()
    true_zs = [to_zs_label(l, config) for l in raw_labels]

    results = classifier.classify_batch(texts, config, show_progress=True)
    preds = [r["prediction"] for r in results]
    raw_outputs = [r["raw"] for r in results]

    valid_idx = [
        i
        for i, (t, p) in enumerate(zip(true_zs, preds))
        if t is not None and p != "INVALID"
    ]
    if not valid_idx:
        raise ValueError("No valid label pairs; check ground_truth_map and API responses.")

    y_true = [true_zs[i] for i in valid_idx]
    y_pred = [preds[i] for i in valid_idx]
    labels_ordered = config.zs_labels

    accuracy = accuracy_score(y_true, y_pred)
    f1_macro = f1_score(y_true, y_pred, labels=labels_ordered, average="macro", zero_division=0)
    f1_weighted = f1_score(
        y_true, y_pred, labels=labels_ordered, average="weighted", zero_division=0
    )
    precision = precision_score(
        y_true, y_pred, labels=labels_ordered, average="macro", zero_division=0
    )
    recall = recall_score(y_true, y_pred, labels=labels_ordered, average="macro", zero_division=0)

    print("\n" + "=" * 70)
    print(f"ZERO-SHOT EVALUATION — {config.name.upper()} ({dataset_name})")
    print(f"Model: {classifier.model} | Backend: {classifier.backend}")
    print("=" * 70)
    print(f"Valid pairs: {len(valid_idx)}/{len(df)}")
    print(f"Accuracy:     {accuracy:.4f}")
    print(f"F1 (macro):   {f1_macro:.4f}")
    print(f"F1 (weighted): {f1_weighted:.4f}")
    print(f"Precision:    {precision:.4f}")
    print(f"Recall:       {recall:.4f}")
    print("\nClassification report:")
    print(classification_report(y_true, y_pred, labels=labels_ordered, zero_division=0))

    os.makedirs(results_dir, exist_ok=True)
    prefix = f"{config_key}_{dataset_name}_{classifier.backend}"

    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required to save confusion matrix plots. "
            "Install with: pip install matplotlib"
        ) from exc

    cm = confusion_matrix(y_true, y_pred, labels=labels_ordered)
    fig, ax = plt.subplots(figsize=(8, 6))
    ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels_ordered).plot(
        ax=ax, xticks_rotation=45, cmap="Blues"
    )
    ax.set_title(f"Zero-shot — {config.name} ({dataset_name})")
    fig.tight_layout()
    cm_path = os.path.join(results_dir, f"zeroshot_confusion_matrix_{prefix}.png")
    fig.savefig(cm_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    out_df = pd.DataFrame(
        {
            "text": [coerce_text(texts[i], max_len=200) for i in valid_idx],
            "true_label": y_true,
            "predicted_label": y_pred,
            "raw_output": [raw_outputs[i] for i in valid_idx],
            "correct": [t == p for t, p in zip(y_true, y_pred)],
        }
    )
    csv_path = os.path.join(results_dir, f"zeroshot_predictions_{prefix}.csv")
    out_df.to_csv(csv_path, index=False)

    print(f"\nSaved confusion matrix: {cm_path}")
    print(f"Saved predictions: {csv_path}")

    return {
        "accuracy": accuracy,
        "f1_macro": f1_macro,
        "f1_weighted": f1_weighted,
        "precision": precision,
        "recall": recall,
        "y_true": y_true,
        "y_pred": y_pred,
        "confusion_matrix_path": cm_path,
        "predictions_path": csv_path,
    }


def mcnemar_test(y_true: List[str], pred_a: List[str], pred_b: List[str]) -> Tuple[float, float]:
    """Paired McNemar test comparing two classifiers on the same examples."""
    import numpy as np
    from statsmodels.stats.contingency_tables import mcnemar

    a_correct = np.array([p == t for p, t in zip(pred_a, y_true)])
    b_correct = np.array([p == t for p, t in zip(pred_b, y_true)])
    table = np.zeros((2, 2), dtype=int)
    table[0, 0] = np.sum(a_correct & b_correct)
    table[0, 1] = np.sum(a_correct & ~b_correct)
    table[1, 0] = np.sum(~a_correct & b_correct)
    table[1, 1] = np.sum(~a_correct & ~b_correct)
    result = mcnemar(table, exact=False, correction=True)
    return float(result.statistic), float(result.pvalue)
