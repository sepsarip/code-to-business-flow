# Where business rules hide

Load this when tracing flows. A route-to-controller read finds the happy path; most rules live in the places below. Examples are given in several ecosystems because the skill is stack-agnostic; map each to the equivalent in the repo at hand.

## Contents

- Entry points that are not screens
- Who is allowed to do what
- State and lifecycle
- Rules that live in data definitions
- Rules that live in configuration
- Naming things in the business's words
- Secondary evidence

## Entry points that are not screens

- Scheduled tasks: Laravel `schedule`, cron files, Celery beat, Spring `@Scheduled`, GitHub Actions on a timer, `node-cron`.
- Queue consumers and event listeners: jobs, listeners, subscribers, message handlers.
- Webhooks from payment, shipping, identity or messaging providers. The payload handling is where "paid" or "delivered" is decided.
- CLI commands and seeders that run in production (imports, month-end closing).
- Admin back offices and internal tools that bypass the public UI.

Each of these is a flow with its own trigger and actor ("the system").

## Who is allowed to do what

- Policy and permission layers: Laravel Gates and Policies, Django permissions, Spring `@PreAuthorize`, CASL/Casbin rules, middleware that checks a role.
- Role definitions in seeders, enums or a roles table. The set of roles is the list of actors.
- Ownership checks (`user_id == current_user.id`), tenant scoping and "cannot act on your own record" checks.
- Client-side guards (hidden buttons, route guards). Record them, but they are not enforcement unless the server repeats them.

## State and lifecycle

- Status enums and constants, and every place that assigns to them. The set of assignments is the transition list.
- Guard conditions before an assignment (`if status == "submitted"`) define which transitions are legal.
- State machine libraries (django-fsm, Spatie model states, XState, Spring Statemachine) declare transitions explicitly; read the declaration first.
- Timestamps such as `approved_at`, `paid_at`, `cancelled_at` reveal states that have no enum value.

## Rules that live in data definitions

- Migrations and schema: `NOT NULL`, `UNIQUE`, `CHECK` constraints, default values, foreign-key `ON DELETE` behaviour.
- Model validation (`validates`, `@Valid`, serializers, Zod/Yup schemas, form requests). These are the input rules.
- Computed fields, accessors and observers/signals that fire on save.
- Pricing, tax, fee and discount tables or calculators. Quote the exact formula and its line.

## Rules that live in configuration

- Config files and environment variables that set limits, thresholds, fees, working days, retention periods. Report the key and where it is read; never report secret values.
- Feature flags. A rule behind a flag that is off is not live behaviour; say which state the repo defaults to.
- Localisation files: also the best source for business vocabulary (see next section).

## Naming things in the business's words

- Prefer UI labels, translation files, email templates, PDF/report templates and notification text over class names. They show how the business talks.
- Build a small glossary (code term → business term) while tracing and use the business term in the report.

## Secondary evidence

Use these to raise a question or support `[INFERRED]`, not to claim `[FACT]`:

- Tests and fixtures: show intended behaviour and edge cases someone cared about.
- README, ADRs, docs folders, OpenAPI specs.
- Commit messages and issue references, when history is available.
- Comments, especially `TODO`, `HACK`, `FIXME`, and comments that mention a policy or a person's decision.

When these disagree with the code, report the disagreement as an open question.
