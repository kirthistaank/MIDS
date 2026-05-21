# Academic Projects — UC Berkeley MIDS

Welcome to the Academic Projects directory! This folder contains coursework, research projects, and academic explorations completed during the UC Berkeley Master of Information and Data Science (MIDS) program.

---

## 📚 Projects Overview

### 1. **Medical NLP: Zero-Shot vs. Fine-Tuned** ⭐ (Extended)
**Location:** `Medical_NLP_Zeroshot_vs_Finetune_Extended/`

**Course:** D266 Natural Language Processing  
**Status:** Extended & Enhanced Version

This is an **updated and extended version** of our D266 final project, revised in response to professor feedback with:
- ✅ Reproducible GPT-4 zero-shot framework with prompt engineering
- ✅ Cleaner methodology with structured comparison
- ✅ Consolidated codebase under `zeroshot/` module
- ✅ Comprehensive evaluation metrics and statistical testing

**Key Features:**
- Clinical text classification across 3 healthcare datasets
- Comparison: Zero-shot LLMs (GPT-4) vs Fine-tuned transformers (PubMedBERT, T5, Mistral-7B + LoRA)
- Medical abstracts, drug reviews, and mental health EDS classification
- Hybrid RAG retrieval pipeline
- Full reproducibility with environment configuration

**Technologies:** Python, PyTorch, Transformers, OpenAI API, PyDatalog, FAISS  
**Data:** ~30K medical texts across 3 balanced datasets

**Quick Start:**
```bash
cd Medical_NLP_Zeroshot_vs_Finetune_Extended
pip install -r requirements.txt
python -m caretrace.main  # Run zero-shot evaluation
```

---

### 2. **YogaVision — MediaPipe Pose Classification** 🧘
**Location:** `YogaVision_MediaPipe_Classification/`

**Course:** W266 Deep Learning / Computer Vision  
**Status:** Complete with Multi-Signal Analysis

Multi-class yoga pose classification using advanced computer vision and deep learning.

**Key Features:**
- MediaPipe pose detection for skeleton extraction
- Multi-feature engineering (keypoints, angles, distances)
- Logistic Regression and TensorFlow Neural Network classifiers
- Kaggle dataset integration
- Feature visualization and confidence metrics

**Technologies:** MediaPipe, TensorFlow, Keras, scikit-learn, OpenCV, NumPy  
**Dataset:** Kaggle Yoga Pose Classification (~600MB, auto-download)

**Quick Start:**
```bash
cd YogaVision_MediaPipe_Classification
pip install -r requirements.txt
python download_data.py  # Auto-download dataset
jupyter notebook yogivision.ipynb
```

---

### 3. **Child Poverty & CalFresh SNAP Benefit Modeling** 📊
**Location:** `CountyLevel_PovertyPrediction_InCalifornia/`

**Course:** W207 Applied Machine Learning  
**Status:** Complete with County-Level Predictions

Predictive modeling of childhood poverty rates and SNAP benefit eligibility across California counties.

**Key Features:**
- Random Forest, XGBoost, and ensemble methods
- Data augmentation and handling class imbalance
- County-level demographic and socioeconomic features
- Feature importance analysis
- Cross-validation and hyperparameter tuning

**Technologies:** scikit-learn, XGBoost, Pandas, Matplotlib, Seaborn

---

### 4. **Airbnb Price Prediction — DataBnB** 🏠
**Location:** `DataBnB/`

**Course:** W207 Applied Machine Learning / Statistical Analysis  
**Status:** Complete with Feature Engineering

End-to-end price prediction for Airbnb listings using statistical and ML methods.

**Key Features:**
- Exploratory data analysis (EDA) of listing features
- Feature selection and engineering
- Regression models: Linear, Ridge, Lasso
- Error minimization and model evaluation
- Price distribution analysis by neighborhood

**Technologies:** Pandas, NumPy, scikit-learn, Matplotlib, Seaborn

---

### 5. **Global & U.S. Disaster Trends Analysis** 🌍
**Location:** `Global_US_DisasterTrendsAnalysis/`

**Course:** W209 Data Visualization / W200 Fundamentals  
**Status:** Complete with Geospatial Analysis

Comprehensive analysis of natural disaster trends globally and within the United States.

**Key Features:**
- Time series analysis of disaster frequency and impact
- Geospatial visualization and mapping
- Disaster type classification and clustering
- Historical trend analysis (20+ years)
- Interactive visualizations

**Technologies:** Pandas, Matplotlib, Folium, GeoPandas, Plotly

---

### 6. **Original Medical NLP Course Project** 📋
**Location:** `Medical_NLP_Zeroshot_vs_Finetune/`

**Course:** D266 Natural Language Processing  
**Status:** Original submission (see Extended version for updates)

Original course submission with T5 and Mixtral zero-shot experiments.

**Note:** The `Medical_NLP_Zeroshot_vs_Finetune_Extended/` folder contains the enhanced version with professor feedback incorporated. Start with the Extended version for latest improvements.

---

### 7. **Zero-Shot Learning Research** 🔬
**Location:** `ZeroShot/`

**Course:** W266 Deep Learning / Research  
**Status:** In Progress / Research Exploration

Experimental exploration of zero-shot learning paradigms and prompt engineering techniques.

---

## 📊 Course Breakdown

| Course | Projects | Topics |
|--------|----------|--------|
| **D266 NLP** | Medical NLP (Extended) | LLMs, Fine-tuning, Prompt Engineering, RAG |
| **W266 Deep Learning** | YogaVision, Zero-Shot | Computer Vision, Neural Networks, Transfer Learning |
| **W207 ML** | Poverty Prediction, DataBnB | Supervised Learning, Feature Engineering, Evaluation |
| **W209 Visualization** | Disaster Analysis | Data Visualization, Geospatial Analysis |
| **W200 Fundamentals** | Disaster Analysis | EDA, Data Cleaning, Basic Statistics |

---

## 🚀 Getting Started

### General Setup
```bash
# Clone the repository
git clone https://github.com/kirthistaank/MIDS.git
cd MIDS/Academic_Projects

# Choose a project
cd <project-name>

# Install dependencies (if available)
pip install -r requirements.txt

# Follow project-specific SETUP.md or README.md
```

### Project-Specific Setup
Each project may have:
- `README.md` — Project overview and description
- `SETUP.md` — Detailed setup and data download instructions
- `requirements.txt` — Python dependencies
- `*.ipynb` — Jupyter notebooks with full analysis
- `*.py` — Standalone scripts and modules

---

## 📝 Notes

- **Group Collaborations:** Most academic projects were group collaborations
- **Data:** Large datasets are excluded from git and downloaded on-demand (see individual project SETUP.md)
- **Code Quality:** Projects emphasize reproducibility and best practices
- **Documentation:** Each project includes comprehensive notebooks and reports

---

## 🔗 Links

- **Main Portfolio:** https://github.com/kirthistaank/MIDS
- **Extended Medical NLP (Latest):** `Medical_NLP_Zeroshot_vs_Finetune_Extended/`
- **YogaVision Setup:** See `YogaVision_MediaPipe_Classification/SETUP.md`

---

## 📚 Course References

All projects are from the UC Berkeley **Master of Information and Data Science (MIDS)** program:
- School: UC Berkeley School of Information
- Program: https://datascience.berkeley.edu/
- Graduating: May 2026

---

## 💡 Key Takeaways

These projects demonstrate:
- ✅ End-to-end ML/NLP pipelines
- ✅ Statistical rigor and evaluation
- ✅ Production-ready code practices
- ✅ Research-grade documentation
- ✅ Real-world problem solving
- ✅ Collaboration and teamwork

---

**Last Updated:** May 2026  
**Maintained By:** Kirthi Shanbhag
