# Next Actions

Use this packet after `env:wiring`, `preflight:live`, and `readiness:report` to summarize the current operator state.

```bash
npm run next:actions
npm run deploy:gate
```

The command writes:

```text
runs/next_actions/<timestamp>/summary.json
runs/next_actions/<timestamp>/event_flow.jsonl
runs/next_actions/<timestamp>/next_actions.md
```

It does not call external APIs, read secret values, print secret values, install tools, deploy, dispatch workflows, or invite testers.

Manual gate env such as `GCP_CREDENTIALS` should be configured in GitHub Actions Secrets. It is intentionally not required in `.env.local` for local preflight.

When the verdict is:

```text
blocked_next_actions_available
```

only the listed local/manual repair actions are allowed. Deploy, workflow dispatch, and tester invites remain forbidden until live preflight, release readiness, deploy gate, and explicit human approval all pass.
