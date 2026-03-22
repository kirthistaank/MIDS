---

# **README**

## **1. Introduction**

This repository contains the code, experiments, and analysis for our study on **single-label medical text classification** using a combination of **zero-shot large language models (LLMs)** and **fine-tuned transformer architectures**. The project evaluates multiple modeling strategies across three healthcare-related datasets, with the aim of providing empirical guidance on model selection under limited-resource conditions.

Our investigation is grounded in recent literature that documents a trade-off between zero-shot LLM generalization and the superior accuracy and stability of fine-tuned encoder models when modest amounts of labeled data are available. By examining models such as PubMedBERT,  T5 and Mixtral, we assess how these paradigms perform on varied medical text domains.

---

## **2. Project Motivation**

Healthcare text is inherently complex, diverse, and unstructured. While zero-shot LLMs provide an attractive solution in low-resource settings, empirical findings suggest that well-tuned transformer encoders often outperform them, particularly on multi-class or domain-specific classification tasks.

This project extends these insights by conducting a systematic comparison of:

* **Supervised fine-tuning** (BERT, T5)
* **Zero-shot inference paradigms** (Mixtral)

across **Medical Abstracts**, **Drug Reviews**, and **Mental Health EDS** datasets.
Our goal is to highlight practical pathways for obtaining strong performance in real-world health-text classification scenarios.

---

## **3. Repository Structure**

```
├── README.md
|
├── PubMedBERT.ipynb
│
├── T5_medicalAbstract_finetune.ipynb
├── T5_MedicalAbstract_Inference.ipynb
├── T5_zeroshot_MedicalAbstract_prompt_tests.ipynb
│
├── T5_drugreview_finetune.ipynb
├── T5_drugreview_inference.ipynb
├── T5_zeroshot_Drugreview_prompt_tests.ipynb
│
├── T5_MentalHealth_finetune&Inference.ipynb
├── T5_zeroshot_MentalHealth_prompt_tests.ipynb
│
├── Results/*.png 
│
│
├── archieve/
│   ├── *.ipynb[not important]
│
├── Data/<TBD>[Large files, skipping it]
│
├── docs/
│   ├── D266_FinalProject_Report.pdf
│
├── MM_Mental_Health_data/
│   ├── train_balanced.csv
│   ├── val.csv
│   ├── test.csv
│   └── MM_Mental_Health_EDA.ipynb
│
└── tmp/*

```

---

## **4. Datasets**

### **4.1 Medical Abstracts**

Used to evaluate encoder-based fine-tuning and zero-shot inference. Preprocessing includes text normalization, label mapping, and handling class imbalance.

### **4.2 Drug Reviews**

Includes patient reviews used for sentiment and condition classification. This dataset is used heavily for comparing T5 fine-tuning, GPT-4 zero-shot performance, and baseline models.

### **4.3 Mental Health EDS Dataset**

Contains text from mental health–related posts. Used to evaluate Mixtral and study model behavior on sensitive, domain-specific language.

---

## **5. Models and Experimental Setup**

### **Baseline Models**

* TF–IDF + Logistic Regression
* Linear classifiers for initial benchmarks

### **Fine-Tuned Models**

* **BERT / PubMedBERT**
* **T5** (encoder-decoder model, fine-tuned for classification)
* **Mixtral** (transformer model evaluated for zero shot experiement esp. for longer mental-health narratives)

### **Zero-Shot Models**

* **Mixtral** (transformer model evaluated for zero shot experiement esp. for longer mental-health narratives)

---

## **6. Key Experiments**

1. **Zero-Shot Evaluation**
   Prompt-based classification using Mixtral and T5[Did not end up using for our report] and comparison against supervised methods.

2. **Fine-Tuned Evaluations**
   Training PubMedBERT, T5 on respective datasets; measuring accuracy, F1, class-wise behavior, and overall generalization.

3. **Model Comparison Across Paradigms**
   We compare the effects of:

   * Model architecture
   * Dataset characteristics
   * Resource availability
   

4. **Error and Confusion Matrix Analysis**
   Includes qualitative and quantitative assessments to understand failure modes across classes.

---

## **7. Results Summary**

Our findings align with current literature:

* Fine-tuned encoder models (e.g., BERT) consistently outperform zero-shot LLMs for structured medical text classification.
* Zero-shot LLMs perform strongly on general sentiment tasks but degrade on multi-class or domain-specific settings.
* T5 demonstrates competitive performance in decoder-based fine-tuning with modest resource requirements.
* Mixtral shows strong results on the Mental Health dataset, particularly for longer context spans.
* Overall, **task-aware model selection is critical**, and fine-tuned models remain highly effective under limited data.

---

## **8. Reproducibility**

### **8.1 Install Dependencies**

```bash
pip install -r requirements.txt <TBD> 
```

### **8.2 Preprocess the Data**

```
<TBD>
```

### **8.3 Fine-Tune Models**

```bash
Run the indvidual notebooks on co-lab or Kaggle or anywhere you think is approriate
```

### **8.4 Zero-Shot Evaluation**

```bash
Run the indvidual notebooks on co-lab or Kaggle or anywhere you think is approriate
```

Evaluation outputs are stored in `results/`.

---

## **9. Team Contributions**

* **Helen Lu**
  Conducted EDA for Medical Abstracts, text cleaning, baseline modeling, BERT fine-tuning, zero-shot tests, and composed major portions of the final report and slides.

* **Kirthi Shanbhag**
  Sourced datasets, performed EDA for Drug Reviews, implemented baseline and zero-shot experiments, fine-tuned T5, validated results using ClinicalBERT and decoder models, and prepared the T5 abstract and report section.

* **Monica Martin**
  Processed and cleaned the Mental Health dataset, conducted Mixtral fine-tuning experiments, generated results, and contributed slides for model comparisons.

---

## **10. Citation**

If you use this work, please cite the following papers referenced in the project:

* Zhang et al. (2025). *Advancing Single and Multi-task Text Classification through LLM Fine-Tuning*.
* Bucher et al. (2024). *Encoder Model Stability and Efficiency in Low-Resource Supervision*.
* Vajjala et al. (2025). *Text Classification in the LLM Era – Where Do We Stand?*

---


