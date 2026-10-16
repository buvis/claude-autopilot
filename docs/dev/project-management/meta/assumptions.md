## 1: Write fail-first tests for verify --log refusal

- For test #16 (`test_nested_repo_store_is_refused`), used `docs/dev/tmp/other/` as the nested repo's root and committed `docs/dev/project-management/autopilot/nested-marker.txt` inside it, then called `--log docs/dev/tmp/other/docs/dev/project-management/autopilot/nested-marker.txt` — matches the task note's example path shape exactly.
- For test #15 (`test_parent_dir_symlink_swap_is_refused`), since `cli.log_sink_refusal` doesn't exist yet, wrapped the import in try/except and call `pytest.fail` with a descriptive message if `log_sink_refusal` is `None`, rather than letting the test error with a raw `ImportError`/`AttributeError`.
- Extended the shared fixture (beyond the carried-over branch's fixture) to also commit a `docs/dev/project-management/autopilot/marker.txt` file at setup, since several new tests need a pre-existing tracked store file to hardlink against or probe.
- Added `skills/run-autopilot/cli/test_verify_log_refusal.py` to release-checks' "review verbs" block (not a new `[checks]` section) since it tests the same `verify --log` surface as the other files already grouped there.
- Did not read or modify `__main__.py`'s actual implementation (out of scope — Task 2's job); grounded only in its name usage via the design doc and the carried-over fixture.
- (Retry fix, review MEDIUM findings) "narrow to the expected failure mode" for the parent-dir symlink swap test means `OSError`, as the review explicitly named it.
