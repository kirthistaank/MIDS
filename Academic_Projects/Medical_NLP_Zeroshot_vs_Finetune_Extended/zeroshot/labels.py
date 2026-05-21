"""Label vocabularies and ground-truth mappings for each dataset."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DatasetConfig:
    key: str
    name: str
    domain: str
    zs_labels: List[str]
    example_label: str
    label_definitions: str
    ground_truth_map: Dict[str, str]
    # Colab / legacy paths (subfolder + csv name)
    subfolder: str
    val_csv: str
    test_csv: str
    # Paths relative to project root when data ships in training_data/
    bundled_val: str = ""
    bundled_test: str = ""
    text_column: str = "text"
    label_column: str = "labels"


MEDICAL_ZS_LABELS = [
    "NEOPLASMS",
    "DIGESTIVE",
    "NERVOUS",
    "CARDIOVASCULAR",
    "GENERAL_PATHOLOGICAL",
]

# Dataset uses 0–4 (or 1–5); map to paper labels
MEDICAL_GT_MAP = {
    "0": "NEOPLASMS",
    "1": "DIGESTIVE",
    "2": "NERVOUS",
    "3": "CARDIOVASCULAR",
    "4": "GENERAL_PATHOLOGICAL",
    "1.0": "NEOPLASMS",
    "2.0": "DIGESTIVE",
    "3.0": "NERVOUS",
    "4.0": "CARDIOVASCULAR",
    "5.0": "GENERAL_PATHOLOGICAL",
}

DRUG_ZS_LABELS = [
    "VERY_NEGATIVE",
    "NEGATIVE",
    "NEUTRAL",
    "POSITIVE",
    "VERY_POSITIVE",
]

DRUG_GT_MAP = {str(i): label for i, label in enumerate(DRUG_ZS_LABELS)}

MENTAL_ZS_LABELS = [
    "DEPRESSIVE_SPECTRUM",
    "ANXIETY_STRESS",
    "BIPOLAR_PERSONALITY",
    "NORMAL",
]

# Matches T5 / Mistral fine-tune label encoder order
MENTAL_GT_MAP = {
    "0": "ANXIETY_STRESS",
    "1": "BIPOLAR_PERSONALITY",
    "2": "DEPRESSIVE_SPECTRUM",
    "3": "NORMAL",
    "Anxiety/Stress": "ANXIETY_STRESS",
    "Bipolar/Personality": "BIPOLAR_PERSONALITY",
    "Depressive_Spectrum": "DEPRESSIVE_SPECTRUM",
    "Normal": "NORMAL",
    "anxiety_stress": "ANXIETY_STRESS",
    "bipolar_personality": "BIPOLAR_PERSONALITY",
    "depressive_spectrum": "DEPRESSIVE_SPECTRUM",
    "normal": "NORMAL",
}

from zeroshot.prompts import (
    LABEL_DEFS_DRUGS,
    LABEL_DEFS_MEDICAL,
    LABEL_DEFS_MENTAL,
)

_MH = "training_data/training_data"

DATASET_CONFIGS: Dict[str, DatasetConfig] = {
    "medical_abstract": DatasetConfig(
        key="medical_abstract",
        name="Medical Abstracts",
        domain="biomedical literature classification",
        zs_labels=MEDICAL_ZS_LABELS,
        example_label="NEOPLASMS",
        label_definitions=LABEL_DEFS_MEDICAL,
        ground_truth_map=MEDICAL_GT_MAP,
        subfolder="medicalabstract/",
        val_csv="val_medical_abstract.csv",
        test_csv="test_medical_abstract.csv",
        bundled_val=f"{_MH}/Medical_Abstract/train_medical_abstract (1).csv",
        bundled_test=f"{_MH}/Medical_Abstract/test_medical_abstract (1).csv",
        label_column="label",
    ),
    "drug_review": DatasetConfig(
        key="drug_review",
        name="Drug Reviews",
        domain="pharmacovigilance and patient-reported outcomes",
        zs_labels=DRUG_ZS_LABELS,
        example_label="NEUTRAL",
        label_definitions=LABEL_DEFS_DRUGS,
        ground_truth_map=DRUG_GT_MAP,
        subfolder="drugreview/",
        val_csv="drugreview_val.csv",
        test_csv="drugreview_test.csv",
        bundled_val=f"{_MH}/Drug_Review/val (2).csv",
        bundled_test=f"{_MH}/Drug_Review/train.csv",
        label_column="label",
    ),
    "mental_health": DatasetConfig(
        key="mental_health",
        name="Mental Health EDS",
        domain="mental health diagnostic screening",
        zs_labels=MENTAL_ZS_LABELS,
        example_label="NORMAL",
        label_definitions=LABEL_DEFS_MENTAL,
        ground_truth_map=MENTAL_GT_MAP,
        subfolder="mentalhealth/",
        val_csv="val.csv",
        test_csv="test.csv",
        bundled_val=f"{_MH}/Mental_Health/Train_Test_Val_data/val.csv",
        bundled_test=f"{_MH}/Mental_Health/Train_Test_Val_data/test.csv",
        text_column="statement",
        label_column="status_combined",
    ),
}


def to_zs_label(raw_label, config: DatasetConfig) -> Optional[str]:
    """Map a dataset label to the zero-shot vocabulary."""
    key = str(raw_label).strip()
    if key in config.ground_truth_map:
        return config.ground_truth_map[key]
    upper = key.upper().replace(" ", "_").replace("/", "_")
    if upper in config.zs_labels:
        return upper
    return None
