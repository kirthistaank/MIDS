"""Prompt templates from *Zero-Shot vs. Fine-Tuned* (Appendix I)."""

SYSTEM_PROMPT = """You are an expert clinical NLP classifier with domain expertise in {domain}.

Your task is to analyze the provided clinical text and classify it into exactly one of the following categories:

{label_definitions}

CLASSIFICATION RULES:
1. Select ONLY ONE label from the list above
2. Base your decision on explicit clinical evidence in the text
3. If multiple categories apply, choose the most clinically urgent or primary diagnosis
4. Respond with ONLY the label name, no explanation, no punctuation

OUTPUT FORMAT: <CATEGORY_NAME>
EXAMPLE OUTPUT: {example_label}

Text to classify:
{text}

Label:"""

MEDICAL_SYSTEM_PROMPT = """You are a biomedical research classifier. Analyze the medical abstract and classify it into exactly one disease category.

CATEGORIES:
- NEOPLASMS: Cancers, tumors, oncological conditions, malignant neoplasms
- DIGESTIVE: Gastrointestinal, hepatic, pancreatic, colorectal conditions
- NERVOUS: Neurological, psychiatric, neurodegenerative, CNS disorders
- CARDIOVASCULAR: Cardiac, vascular, hypertension, circulatory conditions
- GENERAL_PATHOLOGICAL: Infectious, inflammatory, metabolic, endocrine, other

RULES:
1. Select exactly one category
2. Base decision on the primary disease focus of the research
3. If multiple conditions, choose the most severe or primary study endpoint
4. Output ONLY the category name in UPPERCASE with underscores

EXAMPLE OUTPUT: NEOPLASMS

Abstract:
{text}

Category:"""

DRUG_SYSTEM_PROMPT = """You are a pharmacovigilance analyst. Classify this drug review into a sentiment category based on efficacy and side effects.

RATING CATEGORIES:
- VERY_NEGATIVE: Severe adverse effects, treatment failure, discontinuation due to safety
- NEGATIVE: Significant side effects, limited therapeutic benefit, would not recommend
- NEUTRAL: Mixed results, moderate efficacy, tolerable but not optimal
- POSITIVE: Effective treatment, manageable side effects, satisfactory outcome
- VERY_POSITIVE: Excellent efficacy, minimal/no side effects, highly recommend

CLASSIFICATION CRITERIA:
- Consider both effectiveness and tolerability
- Weight long-term outcomes over initial reactions
- Flag reports of serious adverse events as VERY_NEGATIVE regardless of efficacy

OUTPUT FORMAT: Return ONLY the category name.

Review:
{text}

Sentiment:"""

MENTAL_HEALTH_PROMPT = """You are a clinical psychologist conducting preliminary screening. Classify this text into one diagnostic category.

DSM-5-TR CATEGORIES:
- DEPRESSIVE_SPECTRUM: Major depression, persistent depressive disorder, hopelessness, anhedonia, suicidal ideation
- ANXIETY_STRESS: Generalized anxiety, panic attacks, PTSD, acute stress, excessive worry, hypervigilance
- BIPOLAR_PERSONALITY: Bipolar I/II, cyclothymia, borderline personality, emotional dysregulation, mania
- NORMAL: Typical stress responses, situational sadness, healthy coping, no clinical symptoms

DECISION GUIDELINES:
- Focus on duration (>2 weeks for depression), severity (functional impairment), and symptom clusters
- Distinguish between clinical disorders and normal emotional responses
- When symptoms overlap, prioritize the primary presenting complaint

OUTPUT: Provide ONLY the category name.

Patient text:
{text}

Classification:"""

LABEL_DEFS_MEDICAL = """
- NEOPLASMS: Cancers, tumors, oncological conditions, malignant growths
- DIGESTIVE: Gastrointestinal, liver, pancreatic, colorectal conditions
- NERVOUS: Neurological, psychiatric, neurodegenerative disorders
- CARDIOVASCULAR: Heart disease, vascular conditions, circulatory disorders
- GENERAL_PATHOLOGICAL: Infections, inflammation, metabolic disorders, other
"""

LABEL_DEFS_DRUGS = """
- VERY_NEGATIVE (1-star): Severe side effects, ineffective treatment, dangerous reactions
- NEGATIVE (2-star): Unpleasant side effects, limited efficacy, not recommended
- NEUTRAL (3-star): Mixed results, moderate efficacy, tolerable side effects
- POSITIVE (4-star): Effective treatment, manageable side effects, would recommend
- VERY_POSITIVE (5-star): Highly effective, minimal side effects, life-changing benefits
"""

LABEL_DEFS_MENTAL = """
- DEPRESSIVE_SPECTRUM: Major depression, dysthymia, persistent depressive symptoms, hopelessness
- ANXIETY_STRESS: Generalized anxiety, panic disorder, PTSD, acute stress reactions
- BIPOLAR_PERSONALITY: Bipolar I/II, cyclothymia, borderline personality, mood instability
- NORMAL: No clinical symptoms, typical stress responses, healthy coping mechanisms
"""

DOMAIN_PROMPTS = {
    "medical_abstract": MEDICAL_SYSTEM_PROMPT,
    "drug_review": DRUG_SYSTEM_PROMPT,
    "mental_health": MENTAL_HEALTH_PROMPT,
}
