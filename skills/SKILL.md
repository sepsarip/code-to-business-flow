---
name: code-to-business-flow
description: Use this skill when the user wants to understand what an application or website actually does by reading its source code, then document it as business flows, user journeys, status lifecycles, actors and business rules, with diagrams. Triggers include "explain the business flow of this repo", "explain how this application works end-to-end", reverse-engineering requirements from code, onboarding onto an unfamiliar codebase from a business angle, preparing documentation for stakeholders or a business analyst, or finding out how a feature works end to end, even if the user never says "business flow". Produces a layered Markdown report (short summary first, then per-flow detail) plus a rendered HTML version. Do not use for code review, bug fixing, API reference generation, or building new features.
compatibility: Bundled scripts need Python 3.8+ (standard library only). The HTML report loads Mermaid from a CDN, so diagrams need internet when the file is opened.
metadata:
  version: "0.1"
---

# Code to business flow

Turn a codebase into a report a non-technical reader can follow and a developer can verify.

Code shows **what** happens, rarely **why**. An agent that forgets this writes fluent, confident business rules that are guesses. Every statement in the report therefore carries a tag saying how it is known (see Evidence rules). That is the core of this skill; the diagrams and layout serve it.

## Workflow

Copy this checklist and tick it off:

```
- [ ] 1. Scope
- [ ] 2. Map the repo (scripts/scan_repo.py)
- [ ] 3. Choose flows and state the plan
- [ ] 4. Trace each flow end to end
- [ ] 5. Write report.md from assets/report-template.md
- [ ] 6. Validate (scripts/validate_report.py) and fix until it exits 0
- [ ] 7. Render (scripts/render_report.py)
- [ ] 8. Hand over: paths, summary, open questions
```

### 1. Scope

Decide the root directory and whether the user wants the whole app or one feature. In a monorepo, pick the app folder, not the repo root. Write the report in the language the user wrote their request in, not the language of the code. Ask only when the target is genuinely ambiguous (which app in a monorepo, which feature); otherwise state your assumption in the report's coverage section and go on.

### 2. Map the repo

```bash
python3 scripts/scan_repo.py <root> --output /tmp/scan.json
```

The scan lists likely entry points (routes, screens, jobs, webhooks), status/state fields, role and permission checks, external integrations and data entities, plus a suggested reading order. It is a keyword map: it tells you **where to look**, never what the flow is. Expect false positives and misses. Run `python3 scripts/scan_repo.py --help` for options. Do not paste the scan into the report.

### 3. Choose flows and state the plan

Pick 3 to 7 flows. Prefer, in this order: flows that change money or a status, flows that hand work between actors, flows that touch an outside system, flows that run with no user at all (cron, queue workers, webhooks). Write the plan as a short list (flow name, actor, entry point) in the conversation before reading deeply. If the user is present and the list is contentious, wait for a reply; otherwise continue.

### 4. Trace each flow end to end

Follow one path from trigger to outcome: trigger (screen action, route, job) → input validation → who is allowed → domain logic → what is saved and which status changes → side effects (email, payment, queue, file) → what the actor sees next. Then trace the failure and rejection branches; they usually hold the real business rules.

Read `references/discovery-signals.md` before tracing. It lists where rules hide that a route-to-controller read misses (policies, enums, migrations, scheduled jobs, config, seeders, tests, UI labels).

### 5. Write the report

Start from `assets/report-template.md`. Keep its three-layer shape (headings are translated to the report language, order is fixed because the renderer builds tabs from level-2 headings):

1. **Summary** for a reader with two minutes: what the app is for, who uses it, one journey diagram, the flows in one line each.
2. **Flows**, one level-3 section per flow: steps, diagram, status lifecycle, business rules table, failure paths.
3. **Technical detail**: coverage (what you read and what you skipped), entities, integrations, evidence index, open questions.

### 6. Validate

```bash
python3 scripts/validate_report.py report.md --root <root>
```

It checks that every `path:line` reference exists, every FACT rule has one, every flow has a diagram, and diagram types are valid. It cannot check that Mermaid syntax compiles or that your reading is right. Fix errors and rerun until exit code 0. Treat warnings as things to look at, not noise.

### 7. Render

```bash
python3 scripts/render_report.py report.md --output report.html
```

Produces one self-contained HTML file (tabs per layer, tagged badges, diagrams). If the output folder is not specified by the user, put both files in `docs/business-flow/` of the analysed repo and say so.

### 8. Hand over

Reply with the two file paths, a five-line summary, and the most important `UNKNOWN` items as questions for the human who knows the business. Do not claim the flows are verified; say they are traced from code and which parts need confirmation.

## Evidence rules

Tag every business rule and every non-obvious flow step:

| Tag | Meaning | Required |
|---|---|---|
| `[FACT]` | The code enforces it. | A `` `path:line` `` reference (or `path:10-25`) to the enforcing line. |
| `[INFERRED]` | Strongly suggested but not enforced in code you read (naming, UI text, tests, comments). | Say what the inference rests on. |
| `[UNKNOWN]` | Needed to describe the flow but not answerable from code. | Phrase it as a question. |

Rules that keep the tags honest:

- A function named `approveLeave` proves a step exists, not who may approve or under what limit. Read the body, or tag it `[INFERRED]`.
- Check the server side. A rule enforced only in the browser is a UI hint, not a business rule; say so.
- Name things in the business's own vocabulary, taken from UI labels, translations and docs. Keep code identifiers in the evidence column only.
- Dead code, disabled feature flags and environment-dependent branches: report them as such, not as live behaviour.
- When tests or docs disagree with the code, the code wins for `[FACT]`; list the disagreement under open questions.
- A real analysis always leaves open questions. If you have none, you probably guessed somewhere.

## Diagram conventions

- Summary layer: one `flowchart LR` journey, at most 12 nodes, actors as subgraphs (swimlanes).
- Each flow: a `flowchart TD` with the happy path and the failure exits. Add a `sequenceDiagram` only when three or more participants or systems interact.
- Each entity with a status field: a `stateDiagram-v2` of its lifecycle, transitions labelled with the action and actor.
- Node labels: business language, five words or fewer, in double quotes when they contain parentheses, colons or slashes.
- Never use lowercase `end` as a node id or label in a flowchart; Mermaid reads it as the end of a block. Use `Done` or `"End"`.
- Split a diagram that needs more than about 15 nodes into two flows.

## Gotchas

- Status values stored in the database often differ from the labels users see. Record both once, in the lifecycle diagram's legend.
- Soft deletes, tenant or ownership scoping, and default query filters are business rules even though they look like plumbing.
- Money, rounding, tax, deadlines and time zones: when they appear, give the exact rule and its source line.
- Jobs, queue workers and webhooks have no screen. They are flows too, and the scan reports them under entry points.
- Do not describe frameworks (what a controller is). Describe the business.
- Large repos: sample deliberately and list what you did not read in the coverage section. A stated gap is fine; a silent one is not.
- Never copy secrets, credentials or personal data from config or seed files into the report.
