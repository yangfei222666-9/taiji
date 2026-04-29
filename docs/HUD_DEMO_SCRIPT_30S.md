# TaijiOS HUD 30-second demo script

Purpose: one short public asset that points people to the current main repo and live HUD without expanding the TaijiOS claim.

## Boundary

TaijiOS is presented as an AI-agent reliability and learning runtime. Do not describe it as a finished AI OS, autonomous trading system, or completed self-evolution system.

## 30-second script

### 0-5s · Problem

AI agents can look successful while silently failing.

Common failure modes:

- stale artifacts
- missing event trails
- provider drift
- rollback gaps
- outputs that should stay review-only

### 5-15s · What TaijiOS shows

TaijiOS turns an agent run into an auditable evidence chain:

```text
task -> verification -> failure -> guided retry -> result -> evidence
```

The HUD is a compact view of that chain.

### 15-25s · Demo beats

Show the HUD and narrate:

1. A task enters the runtime.
2. The first attempt fails verification.
3. The runtime applies guidance and retries.
4. The final result is accepted only with evidence.
5. The run leaves a trace instead of a vague success message.

### 25-30s · CTA

If you build AI-agent workflows, start here:

- Main repo: https://github.com/yangfei222666-9/taiji
- Live HUD: https://taijios-hud.netlify.app
- Regression guard spin-off: https://github.com/yangfei222666-9/self-improving-loop

## Short post copy

TaijiOS is not a finished AI OS.

It is a reliability runtime experiment for AI agents: task verification, guided retry, rollback-aware evidence, and a HUD that makes silent failure visible.

The goal is simple: agent work should leave an auditable trail, not just a success-looking message.

Main repo: https://github.com/yangfei222666-9/taiji

Live HUD: https://taijios-hud.netlify.app
