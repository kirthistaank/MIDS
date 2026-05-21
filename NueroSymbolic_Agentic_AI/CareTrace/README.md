# CareTrace



Neurosymbolic pediatric after-hours triage for a **scoped** bundle: febrile illness + gastrointestinal symptoms + dehydration risk, with explicit medication safety hooks and antibiotic stewardship flags.

This package wires together:

| Layer | Role |
| --- | --- |
| **Interpretation** (`caretrace/agents/interpretation.py`) | LLM or deterministic heuristics → canonical `CaseFields` |
| **KG retrieval** (`caretrace/graph/snomed_retrieval.py`) | Neo4j: Fever CPG mini-KG (`Concept.sctid` + `pt`, `IS_A`) first, then Snowstorm-loader or legacy `Concept` shapes |
| **Fever → KG terms** (`caretrace/graph/fever_cpg_mentions.py`) | Maps `CaseFields` to lookup phrases aligned with the CPG mini-KG |
| **Safety logic** (`caretrace/logic/triage_rules.py`) | PyDatalog rules + audit `rule_fired` trace |
| **Explanation** (`caretrace/agents/explanation.py`) | Template or LLM clinician-style rationale + safety netting |
| **Orchestration** (`caretrace/orchestration/graph.py`) | LangGraph: `interpret → kg → safety → explain` |

**Code structure and control flow (from `main.py`):** see [`Docs/ARCHITECTURE.md`](Docs/ARCHITECTURE.md).

## Demo

Watch the interactive CareTrace demo:

[![CareTrace Demo Video](https://img.youtube.com/vi/OlysHYbYaqU/maxresdefault.jpg)](https://youtu.be/OlysHYbYaqU)

[Link: https://youtu.be/OlysHYbYaqU](https://youtu.be/OlysHYbYaqU)

## Setup

```bash
cd FinalProject
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

## Run

Interactive CLI:

```bash
CARETRACE_MOCK_LLM=1 CARETRACE_SKIP_NEO4J=1 python -m caretrace.main
```

By default the CLI keeps asking for input until you type `quit`. To **exit automatically** once required intake is satisfied and a disposition is produced, use `CARETRACE_EXIT_ON_COMPLETE=1`.

Interactive Web UI (Streamlit):

```bash
pip install streamlit
CARETRACE_MOCK_LLM=1 CARETRACE_SKIP_NEO4J=1 streamlit run caretrace/ui_streamlit.py
```

With OpenAI + Neo4j, set environment variables in `.env` and run the same command without forcing `CARETRACE_MOCK_LLM=1` / `CARETRACE_SKIP_NEO4J=1`.

Replay scenario-style transcripts:

```bash
CARETRACE_MOCK_LLM=1 CARETRACE_SKIP_NEO4J=1 python scripts/demo_scenarios.py
```

With OpenAI + Neo4j: set variables in `.env` and unset `CARETRACE_MOCK_LLM` / `CARETRACE_SKIP_NEO4J`.

## Fever CPG (Seattle Children’s)

The bundled PDF **`Docs/CPG Fever - Safety and Wellness - Seattle Children's.pdf`** is integrated as follows:

- **Mapping table:** `Docs/CPG_Fever_Seattle_Childrens_reference.md`
- **Rules + trace IDs:** `caretrace/logic/triage_rules.py` (e.g. `R_CPG_SEIZURE`, `R_CPG_INFANT_UNDER_3MO_FEVER`, `R_URGENT_FEVER_OVER_3_DAYS`)
- **Medication language + URL citation:** `caretrace/agents/medication.py`, surfaced in `caretrace/agents/explanation.py`
- **Regenerate extracted text:** `python scripts/extract_cpg_pdf.py`

Extend `CaseFields` + rules for any CPG bullets you still need (pain focality, rash, immunocompromise, etc.).

**Neo4j:** set `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`. On Aura, the **database name** is usually `neo4j` (the default). Do **not** set `NEO4J_DATABASE` to the instance id from the hostname (e.g. `67257d23` in `neo4j+s://67257d23.databases.neo4j.io`); leave `NEO4J_DATABASE` unset unless you use a non-default DB. CareTrace ignores instance-id-shaped values so the driver uses the default database.

Retrieval prefers the mini-KG schema from `KG_implementation/Scaffold_KG_FeverCPG_Text_to_AuraDB.ipynb`; other schemas still work via fallback Cypher in `snomed_retrieval.py`.

## Baseline comparison

See `caretrace/evaluation/baseline_llm.py` for a single-LLM comparator stub for the assignment’s evaluation section.

## Automated scenario evaluation

CSV format (`caretrace/evaluation/scenarios.csv`): `id`, `description`, `expected_disposition`, `turns_json` (JSON array of user strings). Replays the full LangGraph (interpret → KG → safety → explain) with the same env flags as your demo.

```bash
CARETRACE_MOCK_LLM=1 CARETRACE_SKIP_NEO4J=1 python -m caretrace.evaluation
```

Exit code `0` when all rows match `expected_disposition`; `1` otherwise. Use a custom file: `python -m caretrace.evaluation.harness path/to/your.csv`.

**Medical disclaimer:** CareTrace is a course prototype only — not a substitute for licensed clinical decision support or medical advice.Replace dosing tables, CPG predicates, and escalation thresholds with clinician-approved sources.
**Note:** 