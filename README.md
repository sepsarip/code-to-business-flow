# Code to Business Flow

> An AI agent skill and toolkit to reverse-engineer source code into verifiable business flows, user journeys, status lifecycles, and business rules with diagrams.

---

## Overview

Code tells you **what** happens, but rarely **why**. This toolkit enables AI agents and developers to systematically analyze an unfamiliar or undocumented codebase and extract:

- **High-level User Journeys:** Visual end-to-end flows with swimlanes.
- **Detailed Step-by-Step Business Flows:** Traced triggers, validations, state mutations, side effects, and rejections.
- **Entity Lifecycles:** State transition diagrams mapped to actual codebase constants and database fields.
- **Evidence-Tagged Business Rules:** Every rule is validated directly against line numbers in source files.
- **Interactive HTML Reports:** Self-contained reports with tabbed navigation and interactive Mermaid diagrams.

---

## Core Concept: Evidence Tagging

To prevent hallucinations, every rule and non-obvious step in the report must be explicitly tagged:

| Tag | Meaning | Requirement |
|---|---|---|
| `[FACT]` | Verified and strictly enforced by code. | Must provide an exact `` `path:line` `` reference (e.g. `` `app.py:14-15` ``). |
| `[INFERRED]` | Strongly implied but not strictly enforced (e.g. docstrings, naming, tests). | Must state what the inference rests upon in the evidence column. |
| `[UNKNOWN]` | Essential business context that cannot be derived from code alone. | Must be phrased as a question for stakeholders / domain owners. |

---

## Repository Structure

```text
code-to-business-flow/
├── README.md                           # Documentation and usage guide
├── example-leave-app-report.html       # Sample rendered HTML business flow report
├── skills/
│   └── code-to-business-flow/
│       ├── SKILL.md                    # AI agent skill definition & instructions
│       ├── assets/
│       │   ├── report-template.md      # 3-layer Markdown report template
│       │   └── report-template.html    # Standalone HTML report template
│       ├── references/
│       │   └── discovery-signals.md    # Guide on where business rules hide
│       └── scripts/
│           ├── scan_repo.py            # Static scanner to map entry points & entities
│           ├── validate_report.py      # Validator checking structure & citations
│           └── render_report.py        # Markdown to self-contained HTML renderer
└── evals/
    └── code-to-business-flow/
        └── evals/
            ├── evals.json              # Evaluation test cases & assertions
            ├── trigger_queries.json    # Trigger phrase benchmarks
            └── files/
                ├── leave-app/          # Mock Flask/Celery application for testing
                └── leave-app.report.md # Reference English report for leave-app
```

---

## 3-Layer Report Architecture

Reports follow a strict three-layer layout (each level-2 heading becomes a tab in HTML):

1. **Summary (`## Summary`):** High-level purpose, actors, an overview journey diagram (`flowchart LR`), a summary table of all flows, and key open questions.
2. **Flows (`## Flows`):** Level-3 sections (`### <Flow Name>`) for each distinct business flow, including trigger, actor, outcome, flowchart (`flowchart TD`), lifecycle state diagram (`stateDiagram-v2`), business rules table (`BR-XX`), and failure/edge cases.
3. **Technical Detail (`## Technical detail`):** Analysis scope & coverage (files inspected vs skipped), entity definitions, integrations/background jobs, and unresolved open questions.

---

## Workflow & CLI Usage

### 1. Scan the Target Codebase
Generate a structured keyword map of entry points (routes, jobs, webhooks), status enums, auth guards, and data entities:

```bash
python3 skills/code-to-business-flow/scripts/scan_repo.py <path-to-repo> --output scan.json
```

### 2. Draft the Report
Copy `skills/code-to-business-flow/assets/report-template.md` and trace flows end-to-end using the guidance in `references/discovery-signals.md`. Tag every rule with `[FACT]`, `[INFERRED]`, or `[UNKNOWN]`.

### 3. Validate Citations and Structure
Verify that all line references exist and that report structural requirements are satisfied:

```bash
python3 skills/code-to-business-flow/scripts/validate_report.py report.md --root <path-to-repo>
```
*Exits with code `0` on success. Errors must be resolved before rendering.*

### 4. Render to Interactive HTML
Convert the validated Markdown report into a standalone, styled HTML document:

```bash
python3 skills/code-to-business-flow/scripts/render_report.py report.md --output report.html --lang en
```

---

## Quick Example

To test the full pipeline on the bundled mock application:

```bash
# 1. Scan mock application
python3 skills/code-to-business-flow/scripts/scan_repo.py evals/code-to-business-flow/evals/files/leave-app

# 2. Validate reference report
python3 skills/code-to-business-flow/scripts/validate_report.py \
  evals/code-to-business-flow/evals/files/leave-app.report.md \
  --root evals/code-to-business-flow/evals/files/leave-app

# 3. Render HTML report
python3 skills/code-to-business-flow/scripts/render_report.py \
  evals/code-to-business-flow/evals/files/leave-app.report.md \
  --output example-leave-app-report.html \
  --lang en
```

Open `example-leave-app-report.html` in any web browser to view the interactive tabs and rendered Mermaid diagrams.

---

## Requirements

- **Python 3.8+** (Python Standard Library only, zero external packages required).
- **Web Browser** with internet access (to load Mermaid.js via CDN for interactive diagram rendering in HTML).
