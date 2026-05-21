#!/usr/bin/env python3
"""
Automated dataset download for YogaVision project.

Downloads the Yoga Pose Classification dataset from Kaggle.
Requires Kaggle API credentials: ~/.kaggle/kaggle.json
"""

import os
import sys
import shutil
from pathlib import Path

def check_kaggle_config():
    """Check if Kaggle API is configured."""
    kaggle_config = Path.home() / '.kaggle' / 'kaggle.json'
    if not kaggle_config.exists():
        print("❌ Kaggle API not configured.")
        print("\nSetup instructions:")
        print("1. Go to https://www.kaggle.com/settings/account")
        print("2. Click 'Create New API Token' (downloads kaggle.json)")
        print("3. Move kaggle.json to ~/.kaggle/")
        print("4. Run: chmod 600 ~/.kaggle/kaggle.json")
        return False
    return True

def download_dataset():
    """Download yoga pose dataset from Kaggle."""
    try:
        import kaggle
    except ImportError:
        print("❌ Kaggle API not installed.")
        print("Install with: pip install kaggle")
        return False

    # Dataset identifier (you may need to update this based on actual Kaggle dataset)
    DATASET_NAME = "nilammedeiros/yoga5element"  # Example dataset name
    RAW_DATASET_PATH = "RAW_DATASET"

    if Path(RAW_DATASET_PATH).exists():
        print(f"✓ {RAW_DATASET_PATH}/ already exists. Skipping download.")
        return True

    print(f"📥 Downloading dataset: {DATASET_NAME}...")
    
    try:
        os.makedirs(RAW_DATASET_PATH, exist_ok=True)
        kaggle.api.dataset_download_files(
            DATASET_NAME,
            path=RAW_DATASET_PATH,
            unzip=True
        )
        print("✓ Dataset downloaded successfully!")
        print(f"✓ Extracted to: {RAW_DATASET_PATH}/")
        return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
        print("\nManual download:")
        print(f"kaggle datasets download -d {DATASET_NAME}")
        print(f"unzip <dataset-zip> -d {RAW_DATASET_PATH}/")
        return False

def verify_structure():
    """Verify downloaded data structure."""
    if not Path("RAW_DATASET").exists():
        print("⚠️  RAW_DATASET/ not found. Dataset may not have downloaded.")
        return False

    files = list(Path("RAW_DATASET").rglob("*"))
    num_images = len([f for f in files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']])
    
    print(f"\n✓ Dataset structure verified")
    print(f"  - Images found: {num_images}")
    print(f"  - Total files: {len(files)}")
    return True

def main():
    """Main setup flow."""
    print("=" * 60)
    print("YogaVision Dataset Download Setup")
    print("=" * 60)

    if not check_kaggle_config():
        sys.exit(1)

    print("✓ Kaggle API configured")

    if not download_dataset():
        sys.exit(1)

    if not verify_structure():
        print("\n⚠️  Please verify the dataset was extracted correctly.")
        print("Expected structure:")
        print("  RAW_DATASET/")
        print("  ├── class_1/")
        print("  ├── class_2/")
        print("  └── ...")

    print("\n" + "=" * 60)
    print("✓ Setup complete! Ready to run yogivision.ipynb")
    print("=" * 60)

if __name__ == "__main__":
    main()
