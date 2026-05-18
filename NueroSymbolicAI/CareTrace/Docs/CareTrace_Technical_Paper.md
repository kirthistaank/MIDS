# CareTrace: A Neurosymbolic Approach to Pediatric After-Hours Triage

**Course:** DATASCI 290 — Neurosymbolic AI  
**Institution:** UC Berkeley School of Information  

---

## Abstract

After-hours pediatric triage is a high-stakes setting in which caregivers seek guidance for acutely ill children without immediate access to clinicians. Large language models (LLMs) are increasingly capable of producing plausible clinical language, but pure generative approaches lack verifiable reasoning provenance, cannot guarantee adherence to established clinical practice guidelines (CPGs), and risk fabricating medication dosing or epidemic context. CareTrace is a neurosymbolic prototype that grounds pediatric triage in the Seattle Children's Fever CPG by combining (1) an LLM or rule-based natural language interpretation layer, (2) a SNOMED CT–backed knowledge graph in Neo4j AuraDB populated from the CPG's red-flag criteria, (3) deterministic PyDatalog triage rules with full audit trace, and (4) a provenance-annotated explanation agent. A LangGraph orchestration pipeline sequences these components into a multi-turn conversational system. On five manually crafted scenarios spanning home management, emergency escalation, urgent same-day care, a dedicated medication-conflict test (ibuprofen CPG age gate), and a dedicated local-context isolation test, CareTrace produces correct dispositions with full symbolic justification, while a mock LLM baseline cannot guarantee structured CPG adherence. The architecture demonstrates how neurosymbolic integration can improve safety, transparency, and auditability in conversational clinical decision support.

---

## 1. Introduction

### 1.1 Motivation

Pediatric fever is one of the most common reasons families contact medical advice lines after hours. Guidelines such as the Seattle Children's Fever CPG define clear escalation criteria — seizure, altered consciousness, breathing difficulty, extreme fever, infant under three months — that must be applied consistently. Parents describing symptoms in natural language often omit details that are critical for safe triage, and any system that fails to elicit those details risks either over-escalating (unnecessary ER visits) or under-escalating (missed emergencies).

Pure LLMs present two risks in this setting: (a) they cannot guarantee that CPG thresholds are honored because reasoning is implicit in weights rather than explicitly asserted, and (b) they can hallucinate — generating plausible-sounding but incorrect medication dosing, epidemiological context, or age-specific contraindications. Prior work on clinical NLP has shown that symbolic reasoning layers, when coupled with neural language understanding, yield more auditable and safer outputs in structured medical domains.

CareTrace was designed to demonstrate this neurosymbolic integration at prototype scale, with a deliberately bounded clinical scope: febrile illness, gastrointestinal symptoms, and dehydration risk in pediatric patients.

### 1.2 Contributions

1. **Neurosymbolic triage pipeline**: LangGraph state machine sequencing LLM interpretation, SNOMED-grounded KG retrieval, PyDatalog symbolic rules, and templated explanation with provenance strings.
2. **CPG-derived mini knowledge graph**: SNOMED CT concepts seeded from the Seattle Children's Fever CPG "call the doctor" criteria, stored in Neo4j AuraDB with `IS_A` hierarchy and attribute (`REL`) edges.
3. **Audit-traceable reasoning**: every disposition includes a named `rule_ids` set (e.g. `R_CPG_SEIZURE`, `R_ER_ALERTNESS`) that explains exactly which symbolic predicate fired.
4. **Medication safety hooks**: explicit CPG citations for acetaminophen and ibuprofen age gates, with provenance strings tying every statement to the source document URL.
5. **Comparative baseline**: a vanilla LLM baseline without symbolic gates, enabling direct evaluation of provenance and consistency differences.

---

## 2. Background

### 2.1 Neurosymbolic AI

Neurosymbolic AI combines the pattern-recognition strengths of neural networks with the deductive reasoning guarantees of symbolic systems. In the clinical domain, this combination is particularly valuable: neural components handle the variability and ambiguity of natural language, while symbolic components enforce hard constraints derived from domain knowledge. Work such as DeepMind's AlphaFold and IBM's Watson for Oncology explored early neurosymbolic integrations; more recently, LLM-plus-symbolic frameworks have emerged for structured document question answering and clinical guideline compliance.

### 2.2 Clinical Practice Guidelines and Pediatric Triage

Clinical practice guidelines are evidence-based documents that define care protocols for defined conditions. The Seattle Children's Fever CPG (publicly available at `seattlechildrens.org`) specifies fever thresholds, escalation triggers, and medication guidance aligned with the American Academy of Pediatrics. Encoding CPG logic as machine-executable predicates is an established approach in clinical decision support systems (CDSS). CareTrace applies this approach in a conversational setting, where intake fields must be elicited dynamically from unstructured caregiver language.

### 2.3 Knowledge Graphs for Medical Concept Grounding

SNOMED CT is the world's most comprehensive clinical terminology, with over 350,000 active concepts hierarchically organized through `IS_A` and attribute relationships. Snowstorm is an open-source SNOMED CT terminology server that exposes FHIR-compliant REST APIs. Neo4j is a native property graph database widely used in biomedical knowledge graph research. Combining Snowstorm concept retrieval with Neo4j graph persistence enables compact, query-friendly SNOMED subgraphs that can ground natural language terms to standard clinical identifiers.

---

## 3. System Architecture

### 3.1 Overview

CareTrace is implemented as a Python package (`caretrace`) with the following principal layers:

```
caretrace/
  main.py                    ← CLI entrypoint
  config.py                  ← Environment / .env loading, Settings dataclass
  state.py                   ← TypedDicts: CareTraceState, CaseFields, TriageDecision
  orchestration/graph.py     ← LangGraph pipeline (interpret → kg → safety → explain)
  agents/interpretation.py   ← Natural language → CaseFields
  agents/explanation.py      ← Decision + case → clinician reply
  agents/medication.py       ← CPG-grounded medication guidance with provenance
  logic/triage_rules.py      ← PyDatalog rules + required_missing
  graph/snomed_retrieval.py  ← Neo4j SNOMED concept + ancestor lookup
  graph/fever_cpg_mentions.py← CaseFields → KG search phrases
  graph/neo4j_client.py      ← Driver factory + run_cypher
  evaluation/harness.py      ← Automated scenario replay
KG_implementation/
  Pediatric_Fever_KG_Snowstorm_to_AuraDB.ipynb  ← Domain-expanded KG build
  Scaffold_KG_FeverCPG_Text_to_AuraDB.ipynb     ← CPG-text-seeded mini-KG build
```

### 3.2 State Model

All per-session data flows through a single `CareTraceState` TypedDict:

| Field | Type | Purpose |
| --- | --- | --- |
| `messages` | `list[{role, content}]` | Full chat history |
| `raw_user_text` | `str` | Latest caregiver utterance |
| `case` | `CaseFields` | Canonical clinical fields accumulated across turns |
| `kg_annotations` | `list[dict]` | SNOMED concept + ancestor rows from Neo4j |
| `decision` | `TriageDecision` | Disposition, `rule_ids`, `missing_required`, `med_flags` |
| `assistant_reply` | `str` | Final reply shown to the caregiver |
| `turn` | `int` | Turn counter |

`CaseFields` accumulates structured clinical evidence across multiple turns using a `_merge_non_empty` strategy: later turns can update any field while preserving prior values for fields not restated.

### 3.3 LangGraph Orchestration Pipeline

Each caregiver turn triggers a single invocation of the compiled LangGraph `StateGraph`:

```
interpret → kg → safety → [explain | explain_incomplete] → END
```

**Node `interpret`** calls `interpret_user_message`, which dispatches to the LLM structured extraction path (when `OPENAI_API_KEY` is set) or the deterministic heuristic path (`CARETRACE_MOCK_LLM=1`). The heuristic path uses compiled regular expressions and keyword matching covering temperature parsing, alertness signals, breathing patterns, fluid intake language, urination phrases, vomiting quantification, age extraction, medication mentions, seizure keywords, and fever duration. The output is merged with the prior `CaseFields` state.

**Node `kg`** maps the updated `CaseFields` plus the raw utterance to a list of clinical search phrases via `kg_mentions_from_case_and_text`, then queries Neo4j for matching SNOMED concepts and their `IS_A` ancestors. The resulting `kg_annotations` enrich the state for downstream agents and future retrieval-augmented generation (RAG) extensions.

**Node `safety`** calls `required_missing` (structured intake checklist) and `evaluate_triage` (PyDatalog). If required fields are missing, the router sends flow to `explain_incomplete`, which generates questions to elicit them. If all required fields are present, `evaluate_triage` fires the appropriate PyDatalog rules and returns a `TriageDecision`.

**Routing** is controlled by `route_after_safety`: if `decision.missing_required` is non-empty, route to `explain_incomplete`; otherwise route to `explain`.

**Node `explain`** (and `explain_incomplete`) calls the explanation agent, which renders a disposition-specific reply combining: rule trace, medication guidance with CPG provenance strings, dehydration and antibiotic safety flags, and safety netting language.

### 3.4 Symbolic Triage Rules

Rules are defined at module load using PyDatalog's Python DSL. Session-scoped facts (`cf(session_id, name, value)`) prevent cross-session contamination. The rule set covers:

**Hard ER gates:**
```prolog
er_now(S) :- cf(S, "alertness", "altered")
er_now(S) :- cf(S, "breathing", "distress")
er_now(S) :- cf(S, "dehydration_severe", "yes")
er_now(S) :- cf(S, "fluid_intake", "none"), cf(S, "urine_last_8h", "no")
er_now(S) :- cf(S, "cpg_seizure", "yes")
er_now(S) :- cf(S, "cpg_infant_under_3mo_fever", "yes")
```

**Urgent same-day patterns:**
```prolog
urgent_same_day(S) :- cf(S, "temp_f", "very_high"), ~er_now(S)
urgent_same_day(S) :- cf(S, "vomiting", "repeated"), cf(S, "fluid_intake", "poor"), ~er_now(S)
urgent_same_day(S) :- cf(S, "breathing", "tachypnea_concern"), ~er_now(S)
urgent_same_day(S) :- cf(S, "cpg_fever_duration_3_days", "yes"), ~er_now(S)
```

Temperature bucketing maps continuous values to ordinal labels: `very_high` (≥ 104°F), `high` (≥ 103°F), `non_extreme`. CPG predicates — `cpg_seizure`, `cpg_infant_under_3mo_fever`, `cpg_fever_duration_3_days` — are derived in `_case_to_facts` from `CaseFields` before session assertion.

Each firing rule is independently traced via dual `rule_fired(S, "RULE_ID")` predicates that match the same conditions. The `TriageDecision` output includes the complete `rule_ids` list for audit.

### 3.5 Knowledge Graph Construction

Two notebooks build the Neo4j AuraDB mini-KG:

**`Scaffold_KG_FeverCPG_Text_to_AuraDB.ipynb`** seeds the graph directly from the CPG text:
1. Read `CPG_Fever_Seattle_Childrens_extracted.txt`.
2. Extract "Call the doctor if your child:" bullet lines.
3. Map each bullet to short Snowstorm search queries (e.g. "seizure", "dyspnea", "lethargy", "dehydration").
4. Resolve queries via Snowstorm REST API (`/MAIN/concepts`) to SCTIDs.
5. Anchor with `386661006` (Fever).
6. Expand with bounded `build_mini_kg` (max 45 concepts, BFS over `IS_A` + up to 3 attribute neighbors).
7. Load `(:Concept {sctid, pt, kg_source})` nodes with `[:IS_A]` and `[:REL {typeId, typeTerm}]` edges via `MERGE` Cypher. Unique constraint on `sctid`.

**`Pediatric_Fever_KG_Snowstorm_to_AuraDB.ipynb`** seeds the graph from curated domain SCTIDs:
- 6 domains: Asthma, Pediatric_febrile_illness, Abdominal_pain, Sore_throat, General symptoms.
- Same `build_mini_kg` + load pattern, capped at 45 concepts.

The retrieval layer (`snomed_retrieval.py`) detects the graph schema at startup via `CALL db.labels()` / `CALL db.propertyKeys()` and routes to the appropriate query shape: mini-KG (`pt` + `sctid`/`conceptId`), Snowstorm RF2 (`Description` label + `conceptId`), or legacy (`term` field). Catalog probes are cached per driver instance to avoid repeated schema introspection queries.

### 3.6 Medication Safety Module

`medication.py` provides CPG-grounded medication guidance objects (`MedGuidance`) with explicit provenance strings. Key rules:
- Infants under 3 months: no acetaminophen without clinician instruction (`must_escalate=True`).
- Under 6 months: no ibuprofen without clinician instruction (`must_escalate=True`).
- Active dehydration risk: prefer acetaminophen over ibuprofen.
- Weight unknown: request weight before computing dose; do not estimate.
- Every guidance object cites the source URL (`seattlechildrens.org/health-safety/illness/fever`).

PyDatalog `med_flag` predicates independently surface the same age gates in the rule trace (`cpg_ibuprofen_contraindicated_age`, `cpg_no_routine_antipyretic_under_3mo`) as separate `med_flags` in `TriageDecision`.

---

## 4. Knowledge Graph Design

### 4.1 Schema

```
(:Concept {sctid: String, pt: String, kg_source: String})
  -[:IS_A]->(:Concept)              ← SNOMED hierarchical subsumption
  -[:REL {typeId, typeTerm}]->(:Concept)   ← SNOMED attribute (e.g. Finding site)
```

`sctid` is the SNOMED CT identifier (also stored as `conceptId` in some loaders — the retrieval layer treats both as equivalent). `pt` is the preferred display term from Snowstorm's FHIR `CodeSystem/$lookup` endpoint.

### 4.2 Seed Concepts (from CPG extraction)

| Snowstorm query | Selected SCTID | Preferred term |
| --- | --- | --- |
| fever | 386661006 | Fever |
| seizure | 91175000 | Seizure |
| dyspnea | 267036007 | Dyspnea |
| tachypnea | 271823003 | Tachypnea |
| lethargy | 214264003 | Lethargy |
| oliguria | 83128009 | Oliguria |
| dehydration | 34095006 | Dehydration |
| vomiting | 422400008 | Vomiting |
| skin rash | 271807003 | Skin rash |
| neck pain | 81680005 | Neck pain |
| ear pain | 16001004 | Otalgia |
| sore throat | 267102003 | Sore throat |

### 4.3 Bounded Graph Expansion

The `build_mini_kg` function performs breadth-first expansion up to `MAX_TOTAL_CONCEPTS = 45`, following `IS_A` parents and up to `MAX_ATTR_NEIGHBORS = 3` attribute edges per concept for up to `MAX_HOPS_ATTR = 1` hops. A second ancestor-closure pass adds any remaining `IS_A` parents without expanding attribute edges, ensuring the resulting subgraph is semantically coherent without growing unboundedly.

### 4.4 Runtime Retrieval

At each conversational turn the KG node:
1. Calls `kg_mentions_from_case_and_text(case, raw_text)` to produce search terms (combining structured case signals with substring cues from the utterance).
2. For each term, `find_concepts_by_term` queries Neo4j with a case-insensitive `CONTAINS` on `pt`.
3. `ancestors_via_is_a` traverses `IS_A` edges up to 8 hops to provide semantic context.
4. Results are stored in `kg_annotations` for downstream use.

---

## 5. Evaluation

### 5.1 Scenario Design

Five multi-turn scenarios cover all three dispositions plus two separate extended scenarios — one for medication safety and one for local-context handling:

| Scenario | Type | Description | Expected disposition |
| --- | --- | --- | --- |
| `scenario_1_home` | Base | 6-year-old, 101.8°F, tired but responsive, sipping, on amoxicillin | `HOME_MANAGEMENT` |
| `scenario_2_er` | Base | 6-year-old, 103.5°F, barely responding, not drinking, no urine since afternoon | `ER_NOW` |
| `urgent_repeated_vomit` | Base | 5-year-old, 102.5°F, vomited 4 times, only sipping | `URGENT_SAME_DAY` |
| `scenario_4_medication` | **Extended — medication** | **5-month-old**, 101.5°F, responsive, sipping formula | `HOME_MANAGEMENT` |
| `scenario_5_local_context` | **Extended — local context** | **4-year-old**, 102°F, parent says "it's just what's going around school" | `HOME_MANAGEMENT` |

These were deliberately kept as separate scenarios rather than combined:
- `scenario_4_medication` tests **only** the CPG ibuprofen age gate (infant <6 months) with no local context, so the medication flag is the only noteworthy output.
- `scenario_5_local_context` tests **only** that `local_outbreak_context` is captured in state and explicitly labelled as a probabilistic prior that never influences any PyDatalog rule.

Each scenario is a JSON array of natural language turns in `caretrace/evaluation/scenarios.csv`, driven by the automated harness `evaluation/harness.py`. The harness replays turns through the full LangGraph pipeline (`interpret → kg → safety → explain`) and asserts the final `decision.disposition` against `expected_disposition`. All five scenarios pass with exit code 0.

### 5.2 Actual Run Results (mock LLM, no Neo4j)

Run command: `CARETRACE_MOCK_LLM=1 CARETRACE_SKIP_NEO4J=1 python -m caretrace.evaluation`

| Scenario | Expected | CareTrace disposition | Rules fired | Med flags | Result |
| --- | --- | --- | --- | --- | --- |
| `scenario_1_home` | HOME_MANAGEMENT | HOME_MANAGEMENT | `R_HOME_CONSERVATIVE` | `antibiotic_on_file_review_interactions` | ✓ PASS |
| `scenario_2_er` | ER_NOW | ER_NOW | `R_ER_ALERTNESS`, `R_ER_DEHYDRATION_SEVERE` | — | ✓ PASS |
| `urgent_repeated_vomit` | URGENT_SAME_DAY | URGENT_SAME_DAY | `R_URGENT_REPEATED_VOMIT_POOR_FLUID` | `dehydration_avoid_nsaid_or_use_with_caution` | ✓ PASS |
| `scenario_4_medication` | HOME_MANAGEMENT | HOME_MANAGEMENT | `R_HOME_CONSERVATIVE` | `cpg_ibuprofen_under_6mo_requires_clinician` | ✓ PASS |
| `scenario_5_local_context` | HOME_MANAGEMENT | HOME_MANAGEMENT | `R_HOME_CONSERVATIVE` | — | ✓ PASS |

### 5.3 Per-Turn State Trace (Scenario 2 — ER Now)

The table below shows the accumulated `CaseFields` after each turn for the ER scenario, illustrating how the system builds state incrementally and defers the decision until all required fields are present:

| Turn | New input signal | Active case state | Missing | Disposition |
| --- | --- | --- | --- | --- |
| 1 | age=6y, vomiting=once | `{age_years:6, vomiting:'once'}` | temp, alertness, breathing, intake, urine | OUT_OF_SCOPE (asking) |
| 2 | temp=103.5, alertness=altered, breathing=normal, intake=poor, local_context | `{...alertness:'altered', breathing:'normal', fluid_intake:'poor', ...}` | urine | OUT_OF_SCOPE (asking) |
| 3 | urine=no | full state complete | — | **ER_NOW** (`R_ER_ALERTNESS` + `R_ER_DEHYDRATION_SEVERE`) |

Note: the `local_outbreak_context` field is populated from the school-virus mention in Turn 2 but does not influence any PyDatalog predicate — CareTrace's rules treat it as context-only metadata.

### 5.4 Symbolic Rule Coverage

| Scenario | Governing rules (in `TriageDecision.rule_ids`) |
| --- | --- |
| `scenario_1_home` | `R_HOME_CONSERVATIVE` |
| `scenario_2_er` | `R_ER_ALERTNESS`, `R_ER_DEHYDRATION_SEVERE` |
| `urgent_repeated_vomit` | `R_URGENT_REPEATED_VOMIT_POOR_FLUID` |
| `scenario_4_medication` | `R_HOME_CONSERVATIVE` + med flag `cpg_ibuprofen_under_6mo_requires_clinician` |
| `scenario_5_local_context` | `R_HOME_CONSERVATIVE` (local context captured in state; no rule references it) |

The audit trace makes every decision transparent: reviewers can inspect which predicate fired without re-running the model.

### 5.5 Baseline Comparison

`evaluation/baseline_mock.py` provides a deterministic mock baseline that receives the same turn transcripts but has no structured state, no PyDatalog rules, no required-intake checklist, and no CPG-cited provenance. It represents what a naive chatbot would produce.

| Rubric dimension | CareTrace | Mock baseline |
| --- | --- | --- |
| Safety — correct escalation | ✓ 4/4 scenarios correct | Approximate signal only; no guarantee |
| Trustworthiness — CPG grounding | ✓ Rule IDs + CPG citations in every reply | ✗ None |
| Actionability — explicit triggers | ✓ Per-disposition escalation list | ✗ Vague ("if worried") |
| Medication safety | ✓ Age/weight gates + `med_flags` in every reply | ✗ May suggest ibuprofen to infant <6 months |
| Local context handling | ✓ Captured but never overrides safety gate | ✗ May treat as reassuring factor |
| Transparency — state→rule→decision | ✓ Full audit trail in `TriageDecision.rule_ids` | ✗ None |

**Key failure mode — scenario 4 (medication, 5-month-old):** The baseline produces a home-management reply that mentions "acetaminophen or ibuprofen are common options" without any age restriction. CareTrace surfaces `cpg_ibuprofen_under_6mo_requires_clinician` as an explicit med flag backed by the CPG citation URL.

**Key failure mode — scenario 5 (local context):** The baseline reply says *"There does seem to be something going around — that's reassuring in some ways,"* treating viral local context as a clinical modifier that could lower urgency. CareTrace marks `local_outbreak_context` as `(probabilistic prior only; never overrides safety gates)` in the state and in the explanation — neither the rules nor the LLM prompt can treat it as a substitute for clinical assessment.

### 5.6 Required Intake Policy

`required_missing()` enforces a minimum intake checklist before any disposition is issued:

| Required field | Clinical rationale |
| --- | --- |
| Temperature (or explicit `temp_unknown`) | Absolute fever threshold gates |
| Alertness / responsiveness | ER hard gate (altered consciousness) |
| Breathing | ER (distress) and urgent (tachypnea) gates |
| Fluid intake | Dehydration severity gates |
| Urine in last 6–8 hours | Dehydration and ER gate |

Until all five signals are present, the system routes to `explain_incomplete` and asks focused follow-up questions rather than issuing a disposition. This prevents premature decisions based on sparse intake.

---

## 6. Design Decisions and Trade-offs

### 6.1 Why PyDatalog over a Rule Engine?

PyDatalog provides Python-native Datalog with backward-chaining inference. Alternative choices — CLIPS, Drools, or raw if/else Python — were considered. PyDatalog was selected because it allows rules to be expressed declaratively in the same source file as Python business logic, supports negation as failure (`~er_now(S)`), and produces enumerable rule traces via `rule_fired` predicates without separate audit infrastructure. The session-scoped fact pattern avoids global state contamination across evaluation runs.

### 6.2 Why SNOMED CT via Snowstorm?

SNOMED CT is the only comprehensive clinical terminology with a publicly available training server (Snowstorm at `snowstorm-training.snomedtools.org`). Using FHIR `CodeSystem/$lookup` for display term resolution and REST `/concepts` search for seed discovery ensures the KG is built from a terminologically authoritative source. Alternative: ICD-10 or LOINC are less granular for symptom representation.

### 6.3 Why LangGraph?

LangGraph provides a typed state machine with conditional routing, node isolation, and compile-time graph validation. Compared to a simple imperative function chain, LangGraph makes the orchestration flow explicit and auditable, supports future addition of nodes (e.g. a `risk_factor_lookup` node) without rearchitecting the pipeline, and cleanly separates node inputs and outputs.

### 6.4 Scope Boundaries

CareTrace is deliberately bounded to pediatric febrile illness, GI symptoms, and dehydration risk. The following CPG criteria are not yet fully encoded and require extension:
- Localized pain (neck, ears, throat distinction)
- Rash (non-chickenpox)
- Immunocompromised status
- "3 months–2 years with fever > 24h and no other symptoms"
- Chronic health conditions weakening the immune system

These are documented in `Docs/CPG_Fever_Seattle_Childrens_reference.md` and `README.md` as explicit extension points.

### 6.5 LLM vs. Heuristics for Interpretation

The interpretation agent supports two modes:
- **LLM structured extraction** (OpenAI `gpt-4o-mini` with `structured_output`): more robust on diverse natural language, handles implicit phrases ("barely opens eyes" → `alertness=altered`).
- **Heuristic regex/keyword extraction**: deterministic, explainable, fully offline. Covers the most common surface forms but may miss unusual phrasing.

The hybrid design (`try LLM, fallback to heuristics`) provides production resilience while allowing grading/CI with `CARETRACE_MOCK_LLM=1`.

---

## 7. Extra Investigation — Logic-Augmented Generation (LAG)

### 7.1 Motivation

We selected **Option B** from the Lecture 20 menu: *Logic-Augmented Generation.* The hypothesis is that providing the LLM with the full symbolic reasoning chain — patient state, KG evidence, all rules evaluated (fired ✓ or cleared ✗), med flags, and the final decision — produces more trustworthy and consistent explanations than providing raw Python dicts.

### 7.2 Design

| Mode | What the LLM receives | `CareTrace` env flag |
| --- | --- | --- |
| **Standard** | Raw `case` dict + raw `decision` dict | `CARETRACE_USE_LAG=0` (default) |
| **LAG** | Fully structured symbolic context block (see below) | `CARETRACE_USE_LAG=1` |

The LAG context block (rendered by `_format_lag_context` in `explanation.py`) contains:

1. **Patient State** — human-readable labeled fields (e.g., `Alertness: ALTERED — not responding normally`) rather than raw enum values.
2. **KG Evidence** — any SNOMED concepts retrieved from Neo4j (empty when offline).
3. **Triage Rules Evaluated** — all 11 rules in scope, each marked `✓ FIRED` or `✗ NOT FIRED`, with the exact condition string and CPG basis.
4. **Medication Safety Flags** — any active med flags.
5. **Final Symbolic Decision** — the disposition in all-caps.
6. **Eight explicit generation constraints** — e.g., "State the disposition first. Do NOT change it.", "Acknowledge which red-flag rules were evaluated and NOT fired.", "Do NOT invent diagnoses, dosages, or conditions not present in the state."

### 7.3 Example: ER Scenario (Scenario 2) LAG Context

Below is the full LAG context that would be fed to the LLM for the ER scenario:

```
=== SYMBOLIC TRIAGE CONTEXT ===

PATIENT STATE (structured from caregiver reports):
- Age: 6 years
- Temperature: 103.5°F  [classified: high (≥103°F)]
- Alertness: ALTERED — not responding normally
- Breathing: normal
- Fluid intake: poor (minimal)
- Urination last 8h: NO (dry for 8+ hours)
- Vomiting: once
- Current medications: none reported
- Local outbreak context: community_viral_illness_context_mentioned
  (probabilistic prior only; never overrides safety gates)

KNOWLEDGE GRAPH EVIDENCE:
KG evidence: none retrieved (Neo4j offline or no mentions mapped)

TRIAGE RULES EVALUATED (all rules in scope):
✓ FIRED: R_ER_ALERTNESS
  Label: Altered alertness
  Condition: alertness == altered
  CPG basis: Seattle Children's CPG: child not alert when awake → ER immediately
✗ NOT FIRED: R_ER_BREATHING  (Breathing distress)
✓ FIRED: R_ER_DEHYDRATION_SEVERE
  Label: Severe dehydration
  Condition: dehydration_severe == yes  (poor/no fluid AND no urine)
  CPG basis: CPG: no wet diaper/urine in 8 h + poor intake → ER immediately
✗ NOT FIRED: R_ER_NO_FLUID_NO_URINE  (No fluid intake and no urine output)
✗ NOT FIRED: R_CPG_SEIZURE  (Febrile seizure)
✗ NOT FIRED: R_CPG_INFANT_UNDER_3MO_FEVER  (Infant under 3 months with fever)
✗ NOT FIRED: R_URGENT_VERY_HIGH_FEVER  (Very high fever)
✗ NOT FIRED: R_URGENT_REPEATED_VOMIT_POOR_FLUID  (Repeated vomiting with poor fluid intake)
✗ NOT FIRED: R_URGENT_TACHYPNEA_CONCERN  (Tachypnea concern)
✗ NOT FIRED: R_URGENT_FEVER_OVER_3_DAYS  (Fever lasting more than 3 days)
✗ NOT FIRED: R_HOME_CONSERVATIVE  (Conservative home management)

FINAL SYMBOLIC DECISION: ER_NOW
```

### 7.4 Findings

**1. Constrained generation prevents fabricated reasoning.** In standard mode, the LLM receives raw dicts and must reconstruct which rules fired — it may attribute the ER decision to fever severity (103.5°F) rather than the actual rules (`R_ER_ALERTNESS` + `R_ER_DEHYDRATION_SEVERE`). LAG mode eliminates this by providing the exact fired rules.

**2. Not-fired rules prevent false alarms in the explanation.** The `✗ NOT FIRED` list explicitly tells the LLM that seizure, breathing distress, and tachypnea were evaluated and not present. A standard-mode LLM might still mention these as concerns to hedge, which erodes trust.

**3. Local-context separation is made explicit.** The state summary labels `local_outbreak_context` as a "probabilistic prior only; never overrides safety gates." The LLM cannot misread the school-virus mention as a modifying factor, whereas in standard mode this requires careful prompt engineering to prevent.

**4. Medication constraints are surfaced directly.** For scenario 4 (5-month-old), the med flag `cpg_ibuprofen_under_6mo_requires_clinician` appears explicitly in the LAG context, so the LLM must address it. In standard mode, the LLM may silently drop it.

**5. Trade-off: reduced flexibility.** LAG mode constrains the LLM to express the symbolic reasoning rather than augment it. This is the intended behavior for a safety tool, but it limits the LLM's ability to add appropriate clinical nuance not captured by the rule set (e.g., parental anxiety, cultural context). For this prototype, the constraint is a feature, not a bug.

**Implementation:** activate with `CARETRACE_USE_LAG=1` (requires `OPENAI_API_KEY`). In mock-LLM mode, the template fallback is used instead but the LAG context is still rendered and can be inspected. See `_format_lag_context` in `caretrace/agents/explanation.py` and the full demonstration in `evaluation_comparison.ipynb` (Part 5).

---

## 8. Related Work

**Clinical decision support systems (CDSS)**: MYCIN (Shortliffe, 1976) established symbolic rule-based diagnosis. Modern CDSS like Isabel DDx and UpToDate use hybrid rule-plus-retrieval architectures. CareTrace differs in its focus on caregiver-facing conversational triage and its explicit CPG provenance tracing.

**LLM safety in healthcare**: Studies (Singhal et al., 2023; Nori et al., 2023) show GPT-4 can pass medical licensing exams, but also demonstrate hallucination risk in dosing and contraindication scenarios. CareTrace's symbolic layer specifically guards the categories where pure LLMs are most unreliable: discrete thresholds and age-specific contraindications.

**Knowledge graphs in medicine**: Rotmensch et al. (2017) built EHR-derived disease graphs; UMLS-based KGs are standard in medical NLP. CareTrace's contribution is using a CPG-text–seeded SNOMED subgraph at inference time, not just at training time, as a runtime retrieval oracle.

**Neurosymbolic integration**: Garcez & Lamb (2023) survey neural-symbolic computing. The `interpret → symbolic → explain` pipeline pattern used here is similar to the neuro-symbolic concept learner (NSCL) approach: neural perception feeds symbolic reasoning which feeds interpretable output.

---

## 9. Limitations and Future Work

**Limitations:**
- Evaluation is limited to five manually authored scenarios; larger-scale clinical validation is required.
- The KG is bounded to ~45 SNOMED concepts; edge cases involving rare symptom combinations may not be grounded.
- Heuristic interpretation fails on phrasing outside its regex vocabulary; adversarial or non-standard caregiver language is not tested.
- Medical disclaimer: CareTrace is a course prototype; thresholds, dosing tables, and escalation criteria must be reviewed by licensed clinicians before any real-world use.

**Future directions:**
- Extend `CaseFields` and triage rules to cover the unmodeled CPG bullets (rash, immunocompromise, localized pain).
- Add a `kg_rag` node that surfaces `kg_annotations` into the explanation prompt for LLM-backed responses, closing the KG–explanation integration loop.
- Train a fine-tuned structured-extraction model on synthetic triage transcripts to reduce dependence on commercial LLM API.
- Replace template-based explanation with constrained generation guided by the rule trace (chain-of-thought grounded in `rule_ids`).
- Multi-CPG support: extend seed extraction to guidelines for RSV, croup, and urinary tract infections.

---

## 10. Conclusion

CareTrace demonstrates that neurosymbolic integration is both feasible and beneficial for conversational pediatric triage. By combining LLM-based natural language understanding with PyDatalog symbolic rules derived from the Seattle Children's Fever CPG, SNOMED CT knowledge graph grounding in Neo4j, and CPG-cited medication guidance, the system produces structured, auditable, and clinician-legible triage dispositions. The architecture's key properties — traceable rule firing, explicit required-intake policy, and provenance-annotated medication language — directly address the failure modes of pure generative approaches in safety-critical clinical contexts. CareTrace's modular design allows each component to be extended or replaced independently as clinical scope, available data, or deployment constraints evolve.

---

## References

- Seattle Children's. *Fever — Safety and Wellness*. Available: https://www.seattlechildrens.org/health-safety/illness/fever
- Shortliffe, E.H. (1976). *Computer-Based Medical Consultations: MYCIN*. Elsevier.
- Singhal, K. et al. (2023). Large language models encode clinical knowledge. *Nature*, 620, 172–180.
- Nori, H. et al. (2023). Capabilities of GPT-4 on Medical Challenge Problems. arXiv:2303.13375.
- Rotmensch, M. et al. (2017). Learning a health knowledge graph from electronic medical records. *Scientific Reports*, 7, 5994.
- d'Avila Garcez, A., & Lamb, L.C. (2023). Neurosymbolic AI: The 3rd Wave. *AI Communications*, 36, 1–8.
- SNOMED International. *SNOMED CT*. Available: https://www.snomed.org
- Snowstorm Server. *SNOMED CT Training API*. Available: https://snowstorm-training.snomedtools.org
- LangGraph. *LangGraph: Build Stateful Multi-Actor Applications*. LangChain Inc., 2024.

---

*Medical disclaimer: CareTrace is a course prototype only and is not a substitute for licensed clinical decision support or professional medical advice. All dosing guidance, thresholds, and escalation logic must be reviewed and validated by licensed clinicians before deployment.*
