# Release Readiness

Use this report to aggregate local fork readiness, deploy plan readiness, tester packet readiness, and live preflight status.

```bash
npm run readiness:report
```

The command writes:

```text
runs/readiness/<timestamp>/summary.json
runs/readiness/<timestamp>/event_flow.jsonl
runs/readiness/<timestamp>/release_readiness.md
```

It does not call external APIs, dispatch workflows, deploy, read secret values, or issue invite tokens.

After this report is ready, run the deploy gate before any external action:

```bash
npm run deploy:gate
```

`deploy:gate` records whether local readiness is clear and whether a human has confirmed the GitHub Actions secret gate. It still does not deploy.

Important boundary:

```text
local_release_packet_ready_cloud_runtime_blocked
```

means the local packet is reviewable, but Cloud Run / Supabase / GitHub / Vercel live readiness is still blocked. Do not invite testers or deploy from that state.
