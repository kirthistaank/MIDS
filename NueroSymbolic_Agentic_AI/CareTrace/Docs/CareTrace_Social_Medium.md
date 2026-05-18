# CareTrace — Medium article (draft)

*Paste into Medium’s editor. Replace `[Illustration: …]` blocks with your own figures (architecture PNG, flowchart, screenshot). Use Medium’s “code block” for snippets if preferred.*

**Subtitle suggestion:** Grounding after-hours pediatric guidance with structured state, logic, and a little knowledge graph—without letting the LLM improvise the verdict.

---

## The gray zone after bedtime

After-hours pediatric illness is a stressful gray zone. Parents are often forced to make decisions **alone**, without clear, trustworthy guidance. The same situation tends to produce two harmful extremes: **unnecessary emergency visits** or **dangerous delays**—especially when offices are closed.

Today’s partial fixes don’t fit the problem. **Symptom checkers** are rigid and one-directional: they rarely hold a real conversation or integrate new details coherently. **General-purpose AI assistants** can sound empathetic and fluent, but they can also **change their implicit reasoning** as the chat continues. For triage-style decisions, that inconsistency isn’t a minor annoyance—it’s a **safety** concern.

This article introduces **CareTrace**, a **neurosymbolic** research prototype: natural language on the outside, **explicit structure and rules** on the inside, with **stable escalation thresholds** and a **traceable** notion of *why* the system recommended a given path.

**Important:** CareTrace is **not** a diagnostic tool and **not** a replacement for a clinician. It is scoped, educational software meant to explore **trustworthy** architectures—not to give medical advice in production.

---

## Objective: more than conversation

Our goal is to build an agent that goes **beyond** answering questions in isolation. CareTrace aims to produce a **clear, actionable triage plan** tied to three outcomes:

1. **ER now**  
2. **See a clinician today** (urgent / same-day care)  
3. **Home management** with explicit safety netting  

The central design bet is **separation of concerns**:

- A **language layer** interprets caregiver messages and explains results in calm, caregiver-appropriate language (templates and/or an LLM, depending on configuration).  
- A **symbolic layer** holds the **canonical case** and runs **deterministic rules** so that, given the same structured facts, the **disposition stays consistent** across turns.

That split is what we mean by **neurosymbolic** here: neural or heuristic **interpretation** + **symbolic** triage and audit hooks.

---

## Scope (what we deliberately include—and exclude)

We focus on **pediatric fever** with **gastrointestinal symptoms** and **dehydration risk**, for children **under 12**, framed as **after-hours caregiver guidance**. The system also exposes an **out-of-scope** path when the situation doesn’t fit that bundle.

We align parts of the logic and educational text with a **fever-focused CPG** (e.g. Seattle Children’s fever safety material) for **grounding and teaching**, while keeping the implementation a **small, inspectable** ruleset—not a full clinical pathway engine.

Again: **not** a product, **not** a substitute for professional care.

---

## Architecture at a glance

**[Illustration: End-to-end diagram — caregiver message → interpretation → CaseFields → optional Neo4j annotations → PyDatalog rules → TriageDecision → explanation → reply]**

At a high level, each **turn** follows:

1. **Interpretation** — Update a typed, minimal **`CaseFields`** structure from the latest user message (and conversation context).  
2. **Knowledge graph (optional)** — Map mentions to a **small** Neo4j graph (SNOMED-style concept IDs, curated edges). This **augments** context; it does not silently override hard safety gates.  
3. **Safety / triage logic** — Evaluate **PyDatalog** rules and produce a **`TriageDecision`**: disposition, **`rule_ids`**, missing required fields, medication flags.  
4. **Explanation** — Generate the user-facing message, including rule trace language, CPG highlights where configured, and red-flag netting.

Orchestration is implemented with **LangGraph** so the flow is explicit in code: interpret → KG → safety → explain, with routing when **required fields** are still missing.

---

## Code walkthrough: why “structure” matters

### 1. Minimal, typed case state

Instead of letting the model “remember” everything in free text, CareTrace keeps a **shared** structured object that rules can consume. Fields include temperature, alertness, breathing, fluids, urine, vomiting, seizure, fever duration, medications, and similar—only what the triage bundle needs.

```python
# caretrace/state.py (excerpt)
class CaseFields(TypedDict, total=False):
    age_years: float | None
    age_months: float | None
    temp_f: float | None
    vomiting: Literal["none", "once", "repeated", "unknown"]
    alertness: Literal["normal", "sleepy_ok", "altered", "unknown"]
    breathing: Literal["normal", "tachypnea_concern", "distress", "unknown"]
    fluid_intake: Literal["good", "some", "poor", "none", "unknown"]
    urine_last_8h: Literal["yes", "no", "unknown"]
    current_meds: list[str]
    # ... additional fields for CPG-linked gates, etc.
```

The **`TriageDecision`** carries what presenters and logs care about: disposition, which rules fired, what is still missing, and optional med flags.

```python
class TriageDecision(TypedDict, total=False):
    disposition: Disposition
    rule_ids: list[str]
    missing_required: list[str]
    med_flags: list[str]
    out_of_scope_reason: str | None
```

**[Illustration: Small table screenshot — example CaseFields after 2–3 turns of dialogue]**

---

### 2. Deterministic rules + audit trace (PyDatalog)

Rules are written as **logic over facts**, not as prompts. That makes behavior **testable** and **repeatable**. Hard **ER** gates are expressed explicitly; **urgent** and **home** patterns sit in layers below, with negation as appropriate so ER always wins when triggered.

```python
# caretrace/logic/triage_rules.py (excerpt)
pyDatalog.create_terms(
    "cf, S, er_now, urgent_same_day, home_candidate, "
    "rule_fired, med_flag"
)

er_now(S) <= cf(S, "alertness", "altered")
er_now(S) <= cf(S, "breathing", "distress")
er_now(S) <= cf(S, "fluid_intake", "none") & cf(S, "urine_last_8h", "no")

urgent_same_day(S) <= cf(S, "temp_f", "very_high") & ~er_now(S)
urgent_same_day(S) <= (
    cf(S, "vomiting", "repeated")
    & cf(S, "fluid_intake", "poor")
    & ~er_now(S)
)

rule_fired(S, "R_ER_ALERTNESS") <= cf(S, "alertness", "altered")
rule_fired(S, "R_HOME_CONSERVATIVE") <= home_candidate(S)
```

**[Illustration: Simplified ladder graphic — ER band → Urgent band → Home band, with 2–3 example triggers each]**

This is the piece that addresses the LinkedIn critique of “helpful but inconsistent” chat: the **verdict** is not whatever the LLM feels like saying this turn—it is **anchored** to facts and rules, and the UI can show **`rule_ids`** for transparency.

---

### 3. LangGraph orchestration

The graph keeps the pipeline **modular** and easy to explain on a slide or in a code review.

```python
# caretrace/orchestration/graph.py (excerpt)
def node_interpret(state: CareTraceState) -> CareTraceState:
    settings = Settings.from_env()
    prior = state.get("case") or default_case()
    text = state.get("raw_user_text") or ""
    case = interpret_user_message(settings, prior, text)
    return {"case": case, "turn": int(state.get("turn") or 0) + 1}

def node_safety(state: CareTraceState) -> CareTraceState:
    case = state.get("case") or default_case()
    miss = required_missing(case)
    decision = evaluate_triage(case, miss)
    return {"decision": decision}
```

Routing after safety checks whether **required** information is still missing; if so, the system can **ask bounded follow-ups** instead of pretending the plan is complete.

**[Illustration: Flowchart — interpret → kg → safety → branch on missing_required → explain vs explain_incomplete]**

---

## Knowledge graph: small, on purpose

We use **SNOMED-style concept IDs** as stable keys for a **deliberately small** graph: enough to demonstrate **retrieval + reasoning integration**, not to import the entire ontology. Relationships can be **curated** for the teaching demo rather than inherited wholesale from a massive release.

**[Illustration: Neo4j-style subgraph — a few fever-related nodes and one or two relationship types]**

When Neo4j is unavailable (CI, local demo), the stack can run with **`CARETRACE_SKIP_NEO4J=1`** so rules and explanations still execute—another nod to **robust integration** over demo-only wiring.

---

## Evaluation and honest failure modes

A serious project should show **failure**, not only hero cases. CareTrace includes **scenario replay** (CSV harness) and notebook-style **baseline** comparisons (e.g. a single LLM on the same transcript). A good demo contrasts:

- **Baseline:** fluent text, but **no stable symbolic disposition** or rule trace.  
- **CareTrace:** same transcript drives **`CaseFields`** → **`rule_ids`** → disposition, with **gating** when critical fields are unknown.

**[Illustration: Side-by-side screenshot — baseline output vs CareTrace `decision` + sectioned explanation]**

---

## Limitations and next steps

- **Narrow scope** by design; many real presentations are out of scope or need clinician-defined rules.  
- **Interpretation** can still err; rules only see the **structured** case. Mitigations include must-ask gating and conservative defaults—not perfection.  
- **CPG and thresholds** in a course repo are **placeholders** for pedagogy until reviewed by qualified clinicians.

Next steps might include richer CPG coverage, stronger evaluation sets, and formal human-factors review—**after** treating safety and scope with appropriate rigor.

---

## Closing

After-hours pediatric illness will stay emotionally and cognitively hard for families. Tools that only **sound** smart—but **drift**—are a poor fit for triage-style guidance. **CareTrace** experiments with a different contract: **consistent symbolic outcomes**, **traceable rules**, and **natural language** where it helps most—interpretation and explanation—while staying humble about **scope** and **non-diagnostic** use.

If you’re building in this space, the question worth asking is not only “can the model chat?” but **“what structure makes the behavior accountable?”** Neurosymbolic design is one answer worth testing.

---

### Optional footer for Medium

**Repository / context:** Course project — CareTrace (Python, LangGraph, PyDatalog, optional Neo4j).  
**Disclaimer:** Educational prototype only; not medical advice.
