# Fork Readiness

Use this gate before staging, pushing, forking, or handing the starter kit to another tester/operator.

```bash
npm run fork:readiness
```

The command writes:

```text
runs/fork_readiness/<timestamp>/summary.json
runs/fork_readiness/<timestamp>/event_flow.jsonl
runs/fork_readiness/<timestamp>/source_manifest.json
runs/fork_readiness/<timestamp>/fork_readiness.md
```

It checks that required source files exist, generated folders are excluded from the source manifest, local env files are absent, `.gitignore` contains the safety exclusions, and no source file contains a raw `tj_inv_*` invite token pattern.

This is not a deploy proof and it does not call external APIs. It does not read or print secret values.
