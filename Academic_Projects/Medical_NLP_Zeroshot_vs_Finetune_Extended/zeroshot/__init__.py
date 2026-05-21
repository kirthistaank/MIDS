"""Zero-shot clinical text classification (GPT-4 / Mistral-7B-Instruct)."""

from zeroshot.classifier import ZeroShotClassifier
from zeroshot.labels import DATASET_CONFIGS
from zeroshot.parsing import validate_prediction

__all__ = [
    "ZeroShotClassifier",
    "evaluate_zero_shot",
    "DATASET_CONFIGS",
    "validate_prediction",
]


def __getattr__(name):
    if name == "evaluate_zero_shot":
        from zeroshot.evaluate import evaluate_zero_shot

        return evaluate_zero_shot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
