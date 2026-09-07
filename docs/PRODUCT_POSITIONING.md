# CAN Research — product positioning

CAN Research is an **AI-assisted CAN engineering research platform** — for understanding,
documenting, reverse-engineering, diagnosing, and developing real CAN systems — while
**reusing what is already known** and **preserving what is confirmed** for the next session.

It is a **general CAN research platform** with particularly strong support for J1939,
ISOBUS, agricultural machinery, implements, and mixed standard/proprietary networks.
Agriculture is the first deeply developed specialization and a strong niche, not an
architectural ceiling. Industrial, construction, marine, mining, generic 11-bit CAN, and
other segments fit the same evidence-driven model where reference material and DBCs exist.

This document explains where CAN Research is intentionally different from conventional CAN
analysis tools, **why** those differences exist, and what practical value they provide.

**Related docs:** [README.md](../README.md) · [USER_ONBOARDING.md](USER_ONBOARDING.md) ·
[REFERENCE_DATA.md](REFERENCE_DATA.md) · [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) ·
[ARCHITECTURE.md](ARCHITECTURE.md)

---

## Platform architecture

```text
physical system
  → CAN interface (CANsub.2 today)
  → deterministic CAN Research core
  → reference / DBC / historical knowledge
  → bounded MCP evidence
  → AI-guided reasoning (Skills / MCP clients)
  → human engineering judgement
```

| Layer | Role | Status |
|-------|------|--------|
| **Physical + CAN interface** | Real bus traffic via CANsub.2 | **Implemented today** |
| **Deterministic core** | Capture, parse, classify, decode, coverage, candidates, DBC previews | **Implemented today** |
| **Reference knowledge** | J1939/ISOBUS catalogue, bundle import, DBC library, confirmed research | **Implemented today** |
| **MCP** | Bounded, passive tool surface for AI clients | **Implemented today** |
| **Generative AI + Skills** | Workflow orchestration, hypothesis, experiment design, interpretation | **Implemented today** (Skills primarily tested with ChatGPT) |
| **Human CLI** | Confirmation, research DBC writes, configuration | **Implemented today** |

The main differentiator is not one isolated algorithm. It is the full **research loop**:

```text
observe
  → establish known baseline
  → isolate unknown behaviour
  → form hypothesis
  → run bounded experiment
  → compare evidence
  → refine understanding
  → preserve knowledge
  → produce reusable engineering artefacts
```

---

## Engineering culture

CAN Research is an **engineering tool**, not a packet viewer or AI demo. It embraces
reverse engineering, diagnostics, experimentation, control-system understanding, tool-face
design, and development of real engineering solutions on real equipment.

Practical engineering is **iterative**. Unexpected behaviour and failed experiments happen.
The objective is not to normalize careless damage, but to work **deliberately**: preserve
evidence, understand failures, recover where possible, and use what was learned to improve
the next design.

| Distinction | Meaning |
|-------------|---------|
| **Observation** | What was measured on the bus or in a session |
| **Reference-backed knowledge** | Documented PGN/SPN, bundle import, registered DBC |
| **Hypothesis** | AI or operator inference — not yet confirmed |
| **Confirmed finding** | Human-accepted via CLI; eligible for research DBC |

Encourage baselines, controlled changes, reproducible experiments, and recovery planning
alongside discovery.

> Observe carefully. Experiment deliberately. Preserve evidence. Learn from failure. Build better systems.

Concise version in [README.md](../README.md#engineering-philosophy).

---

## General CAN platform, agricultural specialization

| Area | Today | Notes |
|------|-------|-------|
| J1939 / ISOBUS | **Strong** — catalogue import, classify/decode, bundle knowledge, agricultural workflows | First specialization |
| Generic 11-bit / proprietary CAN | **Supported** — capture, sessions, signal research, DBC library | Same evidence loop; less built-in catalogue |
| UDS / ISO-TP / OBD | **Not implemented** | Different tool category; future or external reference |
| CAN FD / LIN / other physical layers | **Not implemented** | Would need adapter + reference extensions |

Do not claim automotive diagnostic workstation capabilities that are not implemented. State
honestly where protocol-specific reference material or future extensions are required.

---

## What CAN Research is — and is not

CAN Research is **not** primarily:

- a CAN GUI
- a packet viewer
- a diagnostics workstation
- a fuzzing tool
- a replacement for SavvyCAN or similar viewers

It **complements** tools like SavvyCAN. Use a viewer for live inspection and graphs; use
CAN Research for structured research, knowledge reuse, deterministic evidence, asset-scoped
DBC refinement, and long-term retention.

```text
SavvyCAN (and similar)          CAN Research
────────────────────────        ────────────────────────────
live viewing                    structured reverse engineering
graphing                        existing-knowledge reuse
manual inspection               deterministic evidence
frame manipulation              AI-guided research workflow
                                asset-specific knowledge
                                DBC creation / refinement
                                provenance and audit trail
                                long-term knowledge retention
```

---

## Status legend

Throughout this document:

| Label | Meaning |
|-------|---------|
| **Implemented today** | Available in the current codebase (CLI and/or MCP) |
| **Direction** | Architectural intent actively shaping design; partial implementation |
| **Planned** | Documented target; not yet built |

See [V1_SCOPE.md](V1_SCOPE.md) for milestone completion detail.

---

## Differentiators and user value

### 1. Known-first research

**Problem:** Starting every capture as “all unknown” repeats work — rediscovering J1939
traffic, re-reading the same DBC, and re-explaining standard PGNs to an AI assistant.

**CAN Research approach:** Begin with what is already known, then isolate the remainder.

| Knowledge source | Status |
|------------------|--------|
| J1939 / ISOBUS reference catalogue | **Implemented today** — PDF import, `lookup_pgn` / `lookup_spn`, session classify/decode |
| Registered DBC library + session coverage | **Implemented today** — `reference dbc register`, `analyze_dbc_coverage` |
| Confirmed research signals / `<asset>_research.dbc` | **Implemented today** — CLI confirm workflow |
| OEM/vendor manuals and spreadsheets | **Implemented today** — source registry + **can-reference-builder** → Reference Bundle V1 import |
| Asset/session history | **Implemented today** — SQLite sessions, assets, candidates |

```text
existing knowledge  →  known baseline  →  unknown remainder  →  research effort
```

**User value:**

- Less rediscovery of standard and previously confirmed traffic
- Smaller proprietary search space
- Faster reverse engineering on repeat visits
- Lower AI context cost — the Skill and MCP can skip already-explained IDs

---

### 2. Asset-centric knowledge

**Problem:** Capture-centric workflows lose context when the session file is archived.
Knowledge about *this tractor* or *this implement* scatters across folders and memory.

**CAN Research approach:** Organize knowledge around an **asset** (machine, implement,
controller) rather than a single log file.

```text
asset
  ├── identity / context
  ├── applicable references
  ├── DBCs (<asset>_standard.dbc, <asset>_research.dbc)
  ├── registered library DBCs (optional asset association)
  ├── sessions (linked captures)
  ├── confirmed proprietary signals
  └── unresolved traffic (coverage output)
```

| Capability | Status |
|------------|--------|
| Asset registry, session linking | **Implemented today** |
| Asset-scoped candidates and research DBC | **Implemented today** |
| Unified asset “knowledge dashboard” | **Planned** |
| Automatic cross-session diff (“what changed since last visit”) | **Planned** |

**User value:**

- Knowledge persists across sessions and revisits
- Tractor / implement / controller knowledge stays separated
- Previous discoveries are reused instead of re-inferred
- Mature assets need investigation only for new or changed traffic

---

### 3. AI as research orchestrator

**Problem:** Asking an AI to “write a Python script to analyse this CAN log” on every
session produces repeated throwaway code, inconsistent methods, and large token use.

**CAN Research approach:** Split roles clearly.

```text
Generative AI (Skill / ChatGPT)
    decides what evidence is needed
    interprets bounded results
    proposes next step (passive inference or experiment)
        ↓
Deterministic core + MCP (41 tools baseline)
    measures facts from stored/live traffic
    returns reproducible, bounded payloads
        ↓
Human operator (CLI)
    confirms or rejects research candidates
    writes confirmed research DBC
```

| Capability | Status |
|------------|--------|
| MCP tool substrate (read-only analysis, passive live, signal research) | **Implemented today** |
| CAN Signal Research Skill workflow | **Implemented today** |
| MCP candidate confirmation | **Not implemented** — intentional; CLI-only human boundary |

**User value:**

- Less repeated generated analysis code
- More consistent research workflow across machines and operators
- Easier validation — same tool, same session, same result
- Better economics on long-running research (bounded MCP calls vs full log re-analysis)

Avoid unsupported cost claims: savings depend on workflow, bus complexity, and how much
knowledge is already on file.

---

### 4. DBC as reusable knowledge

**Problem:** DBC files are often treated as final viewer exports — not as living input to
the next research cycle.

**CAN Research approach:** Existing tuned DBCs are **first-class knowledge sources**.

```text
base / tuned DBC knowledge
        +
observed asset addressing (live/stored traffic)
        +
confirmed local variation (CLI-confirmed research)
        ↓
asset-specific DBC pair:
  <asset>_standard.dbc   — reference-backed / standard
  <asset>_research.dbc — confirmed proprietary only
```

| Capability | Status |
|------------|--------|
| Register, inspect, lookup registered DBCs | **Implemented today** |
| Session coverage vs registered DBCs | **Implemented today** |
| Generate `<asset>_standard.dbc` from session + catalogue | **Implemented today** |
| Generate `<asset>_research.dbc` from confirmed candidates | **Implemented today** |
| Automatic address adaptation / mask-aware DBC rewrite | **Not implemented** |
| J1939 PGN-level address-variant hint in coverage | **Implemented today** (partial — flags likely same PGN, different SA) |

**Why this matters:** On real machinery, source addresses, destination addresses, ECU
instances, and module assignments often vary between otherwise similar machines. CAN
Research does **not** silently rewrite CAN IDs. Coverage can report a **partial** PGN
family match so the engineer knows reuse is plausible but exact mapping is unresolved.

**User value:**

- Supplier/OEM DBCs accelerate research instead of sitting unused
- Clear separation between reusable knowledge and asset-specific confirmation
- Honest reporting when addressing differs from the tuned DBC

---

### 5. Reference + document fusion

**Problem:** No single source explains everything. PGN tables lack semantics; DBCs lack
context; manuals lack observed behaviour.

**CAN Research approach:** Combine evidence types with explicit provenance.

| Source | Typical contribution | Status |
|--------|---------------------|--------|
| Structured reference catalogue | PGN/SPN/DDI definitions, classify/decode | **Implemented today** |
| DBC definitions | Bit layout, scaling, message names | **Implemented today** (library + generated previews) |
| Supporting documents (PDF, CSV, manuals) | Semantics, limits, OEM naming | **Implemented today** — source registry + bundle import; generative conversion via **can-reference-builder** |
| Live / stored CAN traffic | What actually appears on this bus | **Implemented today** |

Example fusion:

```text
DBC          → encoding (start bit, factor, unit)
manual       → semantics (“hydraulic relief pressure”)
live traffic → observed values and change patterns
reference    → standards-backed baseline
```

Together they produce stronger, reviewable evidence than any single source alone.

**User value:**

- Less guessing when a DBC bit layout matches but meaning is unclear
- Standards traffic excluded before proprietary bit-hunting
- Supporting docs remain in the loop without pretending they are already parsed

---

### 6. Deterministic evidence + generative reasoning

**Problem:** If the AI is also the parser, database, and calculator, results are hard to
reproduce and hard to audit.

**CAN Research approach:**

| Layer | Role |
|-------|------|
| **Deterministic core** | Parse frames, classify J1939, decode known SPNs, rank candidates, detect counters/checksums, build DBC previews, compute coverage |
| **Generative AI** | Interpret evidence, prioritize unknowns, suggest experiments, draft reports — label inferences as hypotheses |
| **Human CLI** | Confirm/reject candidates; only confirmed signals enter research DBC |

**User value:**

- Reproducibility — rerun the same MCP tool on the same session
- Evidence traceability — candidate records link to session and metrics
- Lower hallucination risk for bit positions and frame counts
- Generative flexibility without making the model the system of record

---

### 7. Provenance

**Problem:** Mixed knowledge sources get flattened into one DBC or one chat transcript;
later reviewers cannot tell what was measured vs inferred vs imported.

**CAN Research separates:**

| Class | Trust level | How it enters the system |
|-------|-------------|--------------------------|
| Reference-backed | High for documented PGN/SPN | Licensed PDF import → catalogue |
| User-supplied / OEM DBC | As-is from supplier; verify on bus | `reference dbc register` |
| Standard asset DBC | Reference-backed from sessions | `session dbc` / preview |
| Confirmed research | Human accepted | CLI `research candidate confirm` |
| Generative hypothesis | Not confirmed | Skill output, MCP previews only |

**User value:**

- Engineers know **why** a signal is trusted
- Inferred knowledge is not silently promoted to confirmed DBC
- Easier review and audit months later

---

### 8. Complementary tooling (SavvyCAN and others)

CAN Research is **intended to complement** SavvyCAN, CANalyzer, and similar CAN viewers —
not replace them.

Conventional viewers are often **stronger** at:

- Live frame tables and filtering
- Signal graphing and plotting
- Interactive frame send and manipulation
- Ad-hoc bus exploration in a GUI

CAN Research deliberately **does not rebuild** those capabilities in V1. That focus allows
effort on:

- Research workflow and known-first filtering
- Knowledge persistence and asset scope
- DBC refinement and coverage analysis
- AI-guided inference with deterministic backing

**Practical workflow:** Capture or observe in CAN Research (CANsub.2) or import context
from a viewer export where applicable → analyse and retain knowledge in CAN Research →
load resulting DBCs back into SavvyCAN for visual validation and graphing.

---

### 9. Passive-first research

**Problem:** Active bus probing and fuzzing increase risk on production machinery and are
often unnecessary for sensor/state discovery.

**CAN Research approach (current):**

```text
passive observation
    → operator-controlled physical experiment (if needed)
    → deterministic analysis
    → CLI confirmation
```

| Capability | Status |
|------------|--------|
| Passive live capture and observation (MCP + CANsub.2) | **Implemented today** |
| Experiment event markers and window comparison | **Implemented today** |
| CAN TX / injection / fuzzing | **Not implemented** — no MCP TX tools registered |

**User value:**

- Lower safety risk on connected machinery via passive MCP defaults
- Appropriate default for agricultural and industrial equipment
- Physical experiments remain deliberate and human-initiated

**Residual risk:** Passive MCP does not make reverse engineering risk-free. Firmware,
PLC, configuration, wiring, external CAN tools, and manual experiments can still cause
malfunction or damage. Operators remain responsible for equipment and consequences.

**Direction:** Future active probing, if added, would likely be a **separate capability or
Skill** — not an expansion of the core into a monolithic bus workstation.

---

### 10. Initial setup vs normal use

**Problem:** AI-agent integration (MCP clients, ChatGPT connectors/tunnels, Claude desktop
MCP) involves one-time steps that cannot always be frictionless across every host.

**CAN Research approach:** Accept technical initial setup; optimize **repeatable daily use**.

| Phase | Operator experience | Detail |
|-------|---------------------|--------|
| **First install** | Technical — `setup.cmd`, CANsub, MCP/tunnel, connector, Skills | [INSTALLATION.md](INSTALLATION.md) · [MCP_SETUP.md](MCP_SETUP.md) |
| **Normal use** | Simple — `start-can-research.cmd`, `status.cmd`, connect AI | [MCP_SETUP.md — normal startup](MCP_SETUP.md#normal-startup-after-reboot) |

```text
start-can-research.cmd  →  verify CANsub / local MCP / tunnel  →  connect AI  →  READY FOR RESEARCH
```

**User value:** After onboarding, research sessions start quickly without re-creating
connectors, tunnels, or Skills on every boot.

---

### 11. Long-term value curve

CAN Research should become **more useful as you build knowledge**.

| Stage | Typical state | Research effort |
|-------|---------------|-----------------|
| First session on new asset | Mostly unknown; reference may explain much J1939 | High — inventory + prioritize |
| After DBC register + reference import | Coverage shows known vs partial vs unknown | Medium — focus on remainder |
| Mature asset | Standard + research DBCs, confirmed candidates, session history | Low — only new/changed IDs |

Accumulated knowledge is **part of the product value**, not a side effect of one capture.

---

## Comparison matrix

Honest comparison — conventional CAN viewers/workstations vs CAN Research.

| Capability / approach | Conventional CAN viewer / workstation | CAN Research | User value |
|----------------------|----------------------------------------|--------------|------------|
| Live viewing | **Strong** — primary purpose | Passive via CANsub.2 + MCP; no GUI | Viewer wins for ad-hoc live tables; CAN Research for retained sessions |
| Graphing | **Strong** | Not provided | Export DBC to viewer for plots |
| Existing DBC reuse | Manual load/compare | **Register, inspect, coverage, lookup** | Quantified known vs unknown; less manual diff |
| Asset knowledge | Usually manual/project-specific | **Registry, scoped DBCs, candidates** | Knowledge survives across sessions |
| Reference documents | External to tool | Source registry + bundle import/search (**implemented**); vector search **planned** | Standards-backed baseline in one place |
| Known-first filtering | Operator discipline | **Built into workflow + MCP** | Smaller proprietary search space |
| AI role | External scripts / chat | **Orchestrator over MCP substrate** | Consistent evidence gathering |
| Deterministic evidence | Depends on scripts | **Core + MCP** | Reproducible metrics and decode |
| Provenance | Often implicit | **Explicit classes + CLI confirm gate** | Trust and audit |
| DBC generation / refinement | Export from viewer | **Standard + research DBC paths** | Asset-scoped, confirmed proprietary separation |
| Address variation | Filters/masks in viewer | **PGN partial match in coverage**; full adaptation **planned** | Honest reuse without silent ID rewrite |
| TX / fuzzing | Often supported | **Not offered** | Safety and scope focus |
| Persistent knowledge | Project/files ad hoc | **SQLite + JSONL + DBC library + assets** | Compound value over time |

---

## What CAN Research is not (intentional boundaries)

CAN Research is **not currently trying to be:**

| Boundary | Rationale |
|----------|-----------|
| Replacement for SavvyCAN | Viewers excel at live GUI workflows; CAN Research focuses on research retention |
| Full UDS / diagnostic workstation | Out of scope for V1; different tool category |
| ECU flashing platform | Safety and liability boundaries |
| General-purpose CAN fuzzing suite | Passive-first; TX not implemented |
| Generic CAN GUI | CLI-first; no graphing or frame tables in-product |
| Distributor of licensed SAE / ISO / OEM content | Users import material they are authorised to use |

These boundaries keep the project focused on **guided reverse engineering**, **knowledge
reuse**, and **asset-specific DBC refinement**.

---

## Value test (design rule for future work)

A difference should remain **only if it provides practical value**.

Before adding complexity, ask:

- Does it reduce operator effort?
- Does it avoid rediscovery?
- Does it improve confidence?
- Does it preserve reusable knowledge?
- Does it reduce model / token overhead in the research loop?
- Does it make asset-specific DBC creation easier?
- Does it improve repeatability?

If not, prefer simplicity over novelty.

---

## Implemented today (summary)

- CLI-first capture, sessions (SQLite + JSONL), J1939/ISOBUS reference catalogue
- Asset registry, session linking, node / NAME mapping
- Standard DBC from sessions; research DBC from **CLI-confirmed** candidates
- Reference source registry: register originals (public/private/licensed metadata)
- Normalized bundle validate/import/search; MCP reference knowledge tools
- DBC library: register, list, inspect, lookup, session coverage analysis
- MCP: 41 tools — offline analysis, reference bundles, DBC library, passive live CANsub
- CAN Signal Research Skill — known-first workflow orchestration
- Passive-only — no CAN TX tools

## Direction and planned (summary)

- Richer asset knowledge dashboard and cross-session change detection
- **can-reference-builder** Skill — **implemented** (generative conversion → Reference Bundle V1)
- Vector/semantic search over retained reference documents
- Catalogue-level `reference import-dbc` (distinct from library register)
- Mask / filter-aware address-family DBC adaptation
- Optional future active probing as separate capability — not core monolith

Details: [REFERENCE_DATA.md](REFERENCE_DATA.md) · [V1_SCOPE.md](V1_SCOPE.md)

---

## See also

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Concise product definition, engineering philosophy, documentation map |
| [USER_ONBOARDING.md](USER_ONBOARDING.md) | Install, add knowledge, run known-first research |
| [REFERENCE_DATA.md](REFERENCE_DATA.md) | Catalogue, DBC library, documents, provenance |
| [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) | AI + MCP + Skill design contract |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Module boundaries and data flows |
| [../skills/can-signal-research/SKILL.md](../skills/can-signal-research/SKILL.md) | Skill workflow source |
