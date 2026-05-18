# Env Wiring

Use this packet to prepare manual Vercel, GitHub Actions, Supabase, and GCP setup without exposing secret values.

```bash
npm run env:wiring
```

The command writes:

```text
runs/env_wiring/<timestamp>/summary.json
runs/env_wiring/<timestamp>/event_flow.jsonl
runs/env_wiring/<timestamp>/env_matrix.json
runs/env_wiring/<timestamp>/env_wiring.md
```

It checks env name presence and local CLI availability only. It does not call external APIs, install tools, deploy, dispatch workflows, read secret values, or print secret values.

If the verdict is:

```text
manual_env_wiring_required
```

fill the missing env names or install/provide missing CLI tools, then rerun:

```bash
npm run preflight:live:strict
npm run readiness:report
```

`GCP_CREDENTIALS` is a GitHub Actions secret gate, not a local `.env.local` requirement. `env:wiring` may report it under manual env, but it should be configured in GitHub Actions Secrets rather than pasted into repo artifacts.
