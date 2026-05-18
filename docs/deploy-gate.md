# Deploy Gate

Use this command after local readiness reports are available and before any external deploy or workflow dispatch:

```bash
npm run deploy:gate
```

The command writes:

```text
runs/deploy_gate/<timestamp>/summary.json
runs/deploy_gate/<timestamp>/event_flow.jsonl
runs/deploy_gate/<timestamp>/deploy_gate.md
```

It does not call external APIs, read or print secret values, dispatch GitHub Actions, or deploy.

## Remote Secret Confirmation

Local scripts cannot see whether `GCP_CREDENTIALS` exists in GitHub Actions Secrets without an external API or UI check.

After a human confirms the secret exists in GitHub UI, the local gate can record that fact:

```bash
npm run deploy:gate -- --remote-secret-confirmed
```

That still does not deploy. It only creates an auditable gate artifact.

If the only manual wiring blocker is GitHub Actions `GCP_CREDENTIALS`, `--remote-secret-confirmed` may satisfy that blocker for deploy gate purposes. Other local readiness blockers remain hard blocks.

## External Action Boundary

Even if this gate reports:

```text
ready_for_explicit_external_action_approval
```

deployment still requires explicit human approval before any workflow dispatch, Vercel deploy, Cloud Run operation, or tester invite.
