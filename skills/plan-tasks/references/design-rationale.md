# Design Rationale (incident history)

The WHY behind the plan-tasks skill's load-bearing rules. The rules live in
`SKILL.md` where they are enforced; this file holds the incident stories and
design arguments. Nothing here is normative: if a statement here contradicts
`SKILL.md`, `SKILL.md` wins.

## Rule 2 signal widening was attempted and withdrawn (PRD 00075)

The evidence pass (`dev/local/audit-results/00075-task-mix-evidence.md` - a
gitignored local working document present only on the authoring machine, not
in the repo) proposed adding `wire`, `disable`, `permission`, `restore`,
`complete` and `pin`. Every one was withdrawn under adversarial review, and
the signal list in step 4.7's Rule 2 row is byte-identical to its pre-00075
state. The reason is structural, and it is recorded here so the next attempt
does not repeat it: **the proposed signals are generic English verbs, and the
"mechanical" quality of the tasks they were derived from lived in their SIZE,
not their verb.** Size is already gated by `files_touched ≤ 2` AND
lines-changed `≤ 50` — and every counterexample below satisfies that gate, so
the signal is what decides, and a common verb cannot carry that decision.
Concretely: `disable` matches "Disable the vulnerable legacy password-reset
endpoint that leaks account existence via timing" (1 file, ~15 lines);
`restore` matches "Restore the customer records purged by the retention-job
bug by replaying the backup snapshot" (1 file, ~40 lines); `wire`, even
restricted to whole-word matching, matches "Wire the new webhook HMAC
signature check into the payment-provider callback handler" (2 files, ~35
lines); `permission` matches "Add role-based permission checks to the billing
API" (2 files, ~45 lines). Each would route security-critical or
data-recovery work to `haiku` — which is the thinnest pipeline in `/autopilot:work`:
`haiku` skips the step-5.7 per-task code review, and Devon's adversarial
test-validation is opus-only, so such a task ships on Tess's tests alone.
`complete` and `pin` fail differently: `complete the <X>` is generic English
for "finish X", and bare `pin` collides with `mapping`/`opinion`/`spinning`.
Bindings tight enough to exclude the counterexamples matched only the
historical instances they were derived from — over-fitting, not a rule. **A
future widening must move a different axis than the verb** (edit shape or
target artifact, e.g. "adds one entry to a config file"), and must be tested
against adversarial counterexamples before shipping, not only against the
instances it was derived from.

## Rule 1 keyword triggers retired (PRD 00160)

The opus row fired on a keyword scan (`design`, `architect`, `introduce`,
`novel algorithm`, `concurrency`, `migrate`, `refactor across`) plus two size
clauses, one on `files_touched` and one on `estimated_tokens`. All of it is
gone. `classify_tier.py` decides the tier now, from the task's own file slice
and the two facts step 4.7 makes the planner assert with evidence.

Three things were wrong with it. **The scan read the whole PRD body, so one
word anywhere in a PRD promoted every task in that PRD.** **The words are
ordinary English.** "Introduce a flag", "migrate the import", `concurrency`
sitting in a quoted docstring: none of them describes work a cheaper tier
would get wrong, and a planner cannot tell the difference by matching the
string. **File count and token count measure size, not risk.** A wide, boring
rename is wide and boring; opus buys judgment about contracts, algorithms and
shared state, and neither clause asks about any of those.

The bill was real. One 12-task run classified test ports and packaging edits
as opus and paid the full pipeline on each: the opus rate, Devon's adversarial
test validation, the per-task review. None of those tasks needed any of it.

So do not put the triggers back. A keyword rule escalates on the PRD author's
vocabulary, and a size rule escalates on the diff's shape; neither asks the
one question that justifies the tier, which is what the task itself changes.
A future escalation rule has to be a per-task fact about the edit, the way
`contract_edit` and `algorithmic_risk` are, and it has to be tested against
tasks that use the word without doing the work.
