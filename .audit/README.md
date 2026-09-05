# Material-change audit

The scheduled detector reads successful runs from `release.yml` and downloads
only unexpired `taiji-evidence-*` artifacts, matching the producer in
[`release.yml`](../.github/workflows/release.yml). It excludes its own workflow
and `taijios-audit-pulse-*` output. Coverage reports are not build evidence.

`AUDIT_SOURCE_WORKFLOW` accepts a workflow filename or numeric workflow ID;
`AUDIT_SOURCE_ARTIFACT_PREFIX` selects that producer's artifact names. The
scheduled workflow sets both explicitly. Selection examines the latest 20
successful producer runs and up to 100 artifacts per run.

- No eligible artifacts: `PENDING`, exit 0, no pulse or state update.
- Run/artifact lookup failure: `BLOCKED`, exit 2; it is not reported as no change.
- Eligible artifacts: the existing normalized-content and Rekor comparison
  determines whether to emit. Identical content does not emit another pulse.
  The existing 72-hour source-age limit still applies.

Having no successful release is a valid waiting state. Do not trigger a release
merely to make this monitor produce a report. A pulse is a change notification,
not proof of provenance, reproducibility or production readiness.

Run the offline checks from the repository root (Python, pytest, Bash, jq and
unzip are required). HTTP responses in the Python tests are local fixtures:

```bash
python3 -m pytest tests/test_audit_source_selection.py -q
bash .audit/test_material_detector.sh
```
