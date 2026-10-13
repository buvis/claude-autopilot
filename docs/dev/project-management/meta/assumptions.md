# Assumption ledger

Per-plan. Replaced at the first completed task of a full-plan pass.

Plan: PRD 00283 (loop catchup v1), batch 202610111300.

## 1: Stamp loop commits with autopilot-loop/<batch.id> committer identity

Tess (test author):

- Included the optional git-commit integration case (brief marked it "optional but valuable"); judged worth the small cost since it verifies the real mechanism the design depends on.
- Placed the new tests in a sibling file (`test_loop_committer.py`) rather than appending to `test_loop.py`, because `test_loop.py` was already at 755 lines and the global size-limit rule (800 max) would otherwise be violated — a packaging choice, not a behavior assumption.

Ivan (implementor):

- The batch id to stamp is read from `state.json`'s `batch.id` field at launch time (matches the field already used elsewhere in `loop.py`, e.g. `_append_convergence`), since no other source of "current batch id" is given in the listed files.
- `self.env["GIT_COMMITTER_NAME"]` is mutated in place on the shared env dict (rather than building a per-call copy) since `_launch` already passes `env=self.env` directly to `spawn_fn`, and the existing code mutates `self.env` the same way for `_AUTOPILOT_LOOP`.
