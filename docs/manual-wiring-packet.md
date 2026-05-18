# Manual Wiring Packet

Use this packet after `preflight:live:strict` blocks on missing env or CLI setup.

```bash
npm run wiring:packet
```

The command writes:

```text
runs/manual_wiring/<timestamp>/summary.json
runs/manual_wiring/<timestamp>/event_flow.jsonl
runs/manual_wiring/<timestamp>/manual_wiring_checklist.json
runs/manual_wiring/<timestamp>/manual_wiring_packet.md
```

It reads the latest local `env_wiring`, `preflight`, and `next_actions` summaries, then renders a handoff checklist for Supabase, Vercel, GitHub Actions, Cloud Run, and the local operator machine.

## Boundary

- It does not call external APIs.
- It does not install tools.
- It does not deploy.
- It does not dispatch workflows.
- It does not invite testers.
- It does not read or print secret values.
- It does not create `.env` files.

## Supabase Guardrails

Supabase Data API access is controlled by both SQL grants and RLS; this starter keeps browser access behind Next.js API routes and grants runtime tables to `service_role` only. Supabase Storage private access is controlled through Storage RLS, and service keys bypass those controls, so service keys must stay on trusted server or agent surfaces.

Reference:

- https://supabase.com/docs/guides/api/securing-your-api
- https://supabase.com/docs/guides/storage/security/access-control

## Required Follow-up

After manually wiring env names and CLI tools outside chat, rerun:

```bash
npm run env:wiring
npm run preflight:live:strict
npm run readiness:report
npm run next:actions
```

If strict preflight remains blocked, do not deploy, dispatch workflows, or invite testers.
