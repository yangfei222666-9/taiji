# TaijiOS-Lite Migration Audit

Purpose: document what has already been carried forward from the archived
`TaijiOS-Lite` repository into this main `taiji` repository, and what should not
be copied forward.

## Current Status

`TaijiOS-Lite` is an archived historical prototype and example pack.

The current main repository already contains a `taijios-lite/` snapshot for
reference and selective reuse. This means the Lite line is not the canonical
entrypoint for new development.

New users should start from:

- `README.md`
- `examples/quickstart_minimal.py`
- `docs/HUD_DEMO_SCRIPT_30S.md`
- `taijios-lite/` only when inspecting the old lightweight example pack

## Already Represented In This Repo

The main repo contains the useful Lite-facing engineering categories that are
safe to keep as examples:

- API and bot adapters: `taijios-lite/api_server.py`, `bot_core.py`,
  `bot_feishu.py`, `bot_telegram.py`
- Runtime helpers: `taijios-lite/model_router.py`, `model_watcher.py`,
  `multi_llm.py`, `settings.py`
- Failure and output checks: `taijios-lite/aios/core/failure_rules.py`,
  `failure_samples.py`, `output_guard.py`, `validation_meta.py`
- Latency and realtime helpers: `taijios-lite/aios/core/latency_logger.py`,
  `realtime_data.py`, `system_temperature.py`
- Lite tests: `taijios-lite/tests/test_e2e_decision_loop.py`,
  `tests/test_failure_rules.py`, `test_64rounds.py`, `test_cross_validate.py`
- Failure-sample documentation:
  `taijios-lite/docs/failure_sample_library.md`

## Intentionally Not Copied Forward

Some files in the archived repository should not be promoted into the main
entrypoint without rewriting:

- `knowledge/创业笔记.txt`: contains personal and historical business notes.
- `knowledge/TaijiOS产品手册.txt`: contains older broad positioning claims.
- `ARCHITECTURE.md`: describes TaijiOS as a finished self-evolving cognitive
  strategist, which is stronger than the current public reliability-runtime
  boundary.
- `evolution/premium.py`: contains local activation-code logic and historical
  monetization assumptions.
- Live API tests such as `test_divine_live.py` and `test_v14_full.py`: useful
  as historical experiments, but they require external model credentials and
  should not be treated as the default public quickstart.
- Legacy full-stack modules under `evolution/`: useful for reference, but they
  mix cognitive-coach, premium, ecosystem, and broad self-evolution claims.

## Migration Rule

Do not bulk-copy the archived repository.

Only migrate a Lite artifact when it satisfies all of these conditions:

1. It is useful to the current reliability-runtime direction.
2. It does not require private keys, personal data, or live model access.
3. It can be tested or documented as a bounded example.
4. It does not claim completed self-evolution, autonomous trading, or finished
   AI OS capability.

## Boundary

This document is an audit and migration boundary. It does not claim that every
historical Lite feature has been productized in the main repo.

Current public boundary:

```text
TaijiOS is a reliability and learning runtime experiment for AI-agent workflows.
```

Not claimed:

```text
finished AI OS
autonomous trading
completed self-evolution system
production cognitive strategist
```
