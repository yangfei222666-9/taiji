# Agent Reliability Proof

## Ten-second read

I build evidence gates for AI agent workflows. The goal is to prevent false-pass behavior: an agent says a task is done, but the evidence does not support that claim.

This page links the current public proof to merged GitHub PRs, local validation commands, and explicit `cannot_claim` boundaries.

Current public proof also includes Codex Reliability Gap Map #01, a scoped public-report review that maps coding-agent failure reports to evidence-gate design patterns without treating reports as confirmed defects.

## What problem this targets

AI agents often close tasks with unsupported success language. Common failure modes:

- A local check passes, but remote CI has not run.
- A self-test reports pass with zero cases.
- A provider or model output is treated as truth instead of candidate evidence.
- A tool claims readiness without showing evidence gates, unsafe-write boundaries, or closeout proof.

The reliability target here is narrow: make the evidence visible enough that a reviewer can inspect what was built and what is still not proven.

## What is implemented

### 1. False-Pass Gate

The false-pass gate is a local schema-level check for agent success claims. It blocks success language when required passing evidence pointers or explicit `cannot_claim` boundaries are missing.

Run:

```bash
python scripts/check_false_pass_gate.py --self-test examples/false_pass_gate/fixtures
python -m pytest tests/test_false_pass_gate.py -q
```

### 2. Zero-fixture false-pass fix

The gate was hardened so an empty or missing fixture directory cannot produce a fake pass such as `self_test=PASS cases=0`.

Evidence:

- PR #38: [Fix zero-fixture false-pass gate](https://github.com/yangfei222666-9/taiji/pull/38)
- Merge commit: [`de1907fb`](https://github.com/yangfei222666-9/taiji/commit/de1907fb17ce5492895595767c3484a2e719a7e0)

### 3. GLM-5.2 candidate review bridge

The bridge creates a local candidate-review envelope from sanitized stdin. It does not read repository files, does not write files, does not read API keys, and does not call a provider in dry-run mode.

Run:

```bash
printf 'sanitized summary only; no secrets.\n' \
  | python tools/glm52_candidate_review.py --task local_review \
  | python -m json.tool
```

Evidence:

- PR #39: [Add GLM candidate review bridge](https://github.com/yangfei222666-9/taiji/pull/39)
- Merge commit: [`342cc55d`](https://github.com/yangfei222666-9/taiji/commit/342cc55d6e14b09667783372b2c85ec5b1cfc068)

### 4. GLM-5.2 provider lock

The local bridge scripts are locked to Zhipu GLM-5.2 only. Dynamic model selection, dynamic endpoint selection, and non-Zhipu API-key environment fallbacks were removed.

Dry-run validation:

```bash
env -u ZHIPUAI_API_KEY -u GLM_API_KEY -u BIGMODEL_API_KEY -u ZAI_API_KEY \
  python tools/glm52_smoke.py
```

Expected dry-run properties:

```text
provider_called=false
api_key_read=false
locked_provider=zhipuai
locked_sdk=zhipuai.ZhipuAI
locked_model=glm-5.2
api_key_env=ZHIPUAI_API_KEY
dynamic_model_allowed=false
dynamic_endpoint_allowed=false
fallback_provider_allowed=false
```

Evidence:

- PR #40: [Lock GLM bridge to Zhipu GLM-5.2](https://github.com/yangfei222666-9/taiji/pull/40)
- Merge commit: [`54c2b636`](https://github.com/yangfei222666-9/taiji/commit/54c2b6366e8417b5807bd13338e362aced896969)
- Main CI run: [28108395046](https://github.com/yangfei222666-9/taiji/actions/runs/28108395046)

### 5. Codex Reliability Gap Map #01

The Gap Map reviews a deterministic 30-issue public `openai/codex` snapshot and maps reported symptoms to evidence-gate patterns. It is a research proof for failure-mode taxonomy, not a product-quality verdict.

Run:

```bash
python3 scripts/check_codex_gap_map.py
```

Evidence:

- PR #43: [Add Codex Reliability Gap Map #01](https://github.com/yangfei222666-9/taiji/pull/43)
- Merge commit: [`44dee657`](https://github.com/yangfei222666-9/taiji/commit/44dee657fb112f8ea3bfa207c104684079bd94de)
- Main CI run: [28116696880](https://github.com/yangfei222666-9/taiji/actions/runs/28116696880)

## Evidence map

| Evidence | Status | What it supports | What it does not prove |
| --- | --- | --- | --- |
| PR #38 merged | Remote main evidence | Empty or missing fixture directories are rejected instead of passing with zero cases | Production readiness |
| PR #39 merged | Remote main evidence | Candidate review envelope exists and is local-only by default | Provider readiness |
| PR #40 merged | Remote main evidence | GLM bridge scripts are locked to `glm-5.2` and `ZHIPUAI_API_KEY` | Long-task readiness |
| PR #43 merged | Remote main evidence | Gap Map #01 is published with a deterministic public-report sample, validator, and tests | Codex product-quality assessment |
| Main CI at `54c2b636` | Remote CI evidence | CI passed after PR #40 merged | Runtime deployment readiness |
| Main CI at `44dee657` | Remote CI evidence | CI passed after PR #43 merged | Prevalence or confirmed-defect claims |
| Local dry-run commands | Local validation evidence | No provider call or key read in dry-run mode | API execution correctness |

## Recruiter-readable summary

- Built a false-pass gate that rejects unsupported AI-agent success claims when evidence pointers or `cannot_claim` boundaries are missing.
- Fixed a real false-pass bug where missing or empty fixtures could have allowed a zero-case self-test to appear successful.
- Added a candidate-review bridge that prepares sanitized review envelopes while preserving local-only and candidate-only boundaries.
- Locked the GLM bridge to Zhipu GLM-5.2 only, removing dynamic model, endpoint, and fallback-provider paths.
- Published Codex Reliability Gap Map #01 as a scoped research proof that maps public coding-agent failure reports to evidence-gate patterns.
- Kept provider output separate from canonical truth: GLM output can assist planning and review, but local verification, GitHub CI, and human approval remain separate gates.

## `cannot_claim`

This proof does not claim:

- production readiness
- provider readiness
- runtime readiness
- long-task readiness
- autonomous self-improvement
- hiring validation
- customer validation
- Zhipu endorsement
- that provider output is canonical truth
- prevalence across Codex users
- current Codex product quality
- maintainer-confirmed defects or root causes

## Next evidence gate

The next useful gate is to keep README and recruiter-facing materials aligned with the merged implementation proof and research proof. Do not add another architecture layer before the public proof path is easy to inspect.
