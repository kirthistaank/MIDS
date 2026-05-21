# YogaVision Setup Guide

This guide explains how to set up the YogaVision project and download the required datasets.

## Project Overview

**YogaVision** — Multi-class yoga pose classification using MediaPipe pose detection and deep learning models (Logistic Regression, Neural Networks).

## Why Data Isn't in Git

The dataset folders are **excluded from git** because they're too large (~2.75GB):
- `RAW_DATASET/` — 603MB (raw images from Kaggle)
- `DATASET/` — 644MB (processed dataset)
- `FEATURES/` — 1.5GB (extracted pose features)

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/kirthistaank/MIDS.git
cd MIDS/Academic_Projects/YogaVision_MediaPipe_Classification
```

### 2. Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Download the Dataset

#### Option A: Automated Download (Recommended)
```bash
python download_data.py
```

This script will:
- Check for Kaggle API credentials
- Download the yoga pose dataset
- Extract and organize files into `RAW_DATASET/`

#### Option B: Manual Download

1. **Set up Kaggle API:**
   - Go to https://www.kaggle.com/settings/account
   - Click "Create New API Token" (downloads `kaggle.json`)
   - Place it in `~/.kaggle/kaggle.json`
   - Run: `chmod 600 ~/.kaggle/kaggle.json`

2. **Download from Kaggle:**
   ```bash
   kaggle datasets download -d <dataset-name>
   unzip <dataset-zip> -d RAW_DATASET/
   ```

3. **Find the Dataset:**
   - Search for "Yoga Pose Classification" on Kaggle
   - Or use: `kaggle datasets list -s yoga`

### 5. Generate Features (Optional)
If you want to regenerate processed features:
```bash
python extract_features.py
```

This will populate:
- `FEATURES/` — Extracted MediaPipe pose landmarks
- `DATASET/` — Cleaned, split train/val/test data

## Project Structure

```
YogaVision_MediaPipe_Classification/
├── yogivision.ipynb                # Main notebook with full pipeline
├── yogivision_final_report.pdf     # Detailed project report
├── yogivision_code.pdf              # Code documentation
├── requirements.txt                 # Python dependencies
├── SETUP.md                         # This file
├── README.md                        # Project overview
├── download_data.py                 # Automated dataset download
├── extract_features.py              # Feature extraction script
│
├── RAW_DATASET/                     # Raw images (not in git - download)
│   └── [yoga pose images by class]/
│
├── DATASET/                         # Processed splits (not in git)
│   ├── train/
│   ├── val/
│   └── test/
│
└── FEATURES/                        # Extracted features (not in git)
    ├── train_features.npy
    ├── val_features.npy
    └── test_features.npy
```

## Running the Analysis

### Using Jupyter Notebook
```bash
jupyter notebook yogivision.ipynb
```

### From Python Script
```python
from yogivision import YogaPoseClassifier

classifier = YogaPoseClassifier(model='neural_network')
classifier.train(data_path='DATASET/train/')
results = classifier.evaluate(data_path='DATASET/test/')
print(results)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Kaggle API error | Verify credentials at `~/.kaggle/kaggle.json` |
| Missing `RAW_DATASET/` folder | Run `python download_data.py` |
| Out of memory during training | Reduce batch size in notebook or script |
| MediaPipe errors | Run `pip install --upgrade mediapipe` |

## Dataset Information

- **Source:** Kaggle Yoga Pose Classification Dataset
- **Classes:** Multiple yoga poses (e.g., Tree, Mountain, Warrior)
- **Format:** Images (JPG/PNG) with pose labels
- **Total Size:** ~603MB (raw), ~2.75GB (with features)

## Citation

If you use this project, cite the original Kaggle dataset and MediaPipe:

```bibtex
@misc{yogavision2024,
  title={YogaVision: Multi-Class Yoga Pose Classification},
  author={Shanbhag, Kirthi},
  year={2024},
  url={https://github.com/kirthistaank/MIDS}
}
```

## Requirements

- Python 3.8+
- TensorFlow 2.0+
- MediaPipe
- scikit-learn
- NumPy, Pandas, Matplotlib

See `requirements.txt` for exact versions.
