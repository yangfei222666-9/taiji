# Skill Auto-Creation System

**Status:** Design & Observation Phase  
**Version:** MVP v1.1  
**Mode:** Isolated / No Production Chain Changes

---

## Purpose

Automatically discover, generate, validate, and test Skill drafts from repeated patterns in AIOS operations.

**This is NOT production code.** This is an isolated workspace for:
- Proving the concept
- Testing the full lifecycle
- Gathering feedback before any main chain integration

---

## Design Principles

1. **Observation period first** - No production integration until proven
2. **Shadow mode only** - Drafts run in parallel, never affect main chain
3. **Manual promotion gate** - All drafts require human review before production
4. **Reality Ledger** - Every step is logged for learning and rollback
5. **Fail-safe by default** - Validation failures block progression, not bypass

---

## Directory Structure

```
skill_auto_creation/
├── candidates/              # Detected patterns (detector output)
├── draft_registry/          # Validated drafts (isolated from production)
│   ├── index.json          # Global status index
│   └── README.md           # Registry rules
├── templates/               # Generation templates
│   ├── SKILL_TEMPLATE.md
│   └── VALIDATION_RULES.json
├── stubs/                   # Module interface stubs (no business logic yet)
├── tests/
│   ├── fixtures/           # Test data (heartbeat_alert_deduper samples)
│   └── skeleton/           # Test skeletons (no implementation yet)
├── logs/                    # Local test & shadow run logs
└── README.md               # This file
```

---

## Lifecycle

```
1. Detect     → skill_candidate_detector  → candidates.jsonl
2. Draft      → skill_drafter             → draft_registry/{id}/SKILL.md
3. Validate   → skill_validator           → validation_result.json
4. Register   → skill_draft_registry      → index.json (status: validated)
5. Shadow Run → (manual trigger)          → feedback.jsonl
6. Review     → (human decision)          → promoted / rejected
```

---

## Current Status

### ✅ Completed
- Task cards for 5 modules
- Test fixtures for `heartbeat_alert_deduper` (5 cases)
- Isolated directory structure
- Templates (SKILL.md, VALIDATION_RULES.json)
- Draft registry with status flow

### 🚧 In Progress
- Module interface stubs (next step)
- Test skeletons

### ⏸️ Not Started
- Business logic implementation
- Shadow mode runner
- Production chain integration

---

## First Target

**Skill:** `heartbeat_alert_deduper`  
**Pattern:** Repeated alert deduplication judgment  
**Source:** Heartbeat logs with old skill alerts  
**Risk Level:** Low (read-only, no file modification)

---

## Constraints

### What This System WILL Do
- Detect repeated patterns from logs
- Generate draft SKILL.md files
- Validate format, security, and risk
- Run drafts in shadow mode (parallel, no side effects)
- Record feedback for improvement

### What This System WILL NOT Do
- Modify production skill directory
- Auto-promote drafts without review
- Execute high-risk operations
- Bypass validation failures
- Touch main heartbeat chain

---

## Next Steps

1. Write interface stubs for 5 modules
2. Write test skeletons
3. Implement detector (read-only, pattern matching)
4. Implement drafter (template filling)
5. Implement validator (rule checking)
6. Run first end-to-end test with `heartbeat_alert_deduper`

---

## References

- Design Doc: `docs/SKILL_AUTO_CREATION_MVP_v1.1_SPEC.md`
- Task Cards: See commit message or `memory/2026-03-09.md`
- Test Fixtures: `tests/fixtures/heartbeat_alert_deduper/`
- hermes-agent Research: `memory/2026-03-09-hermes-skill-research.md`

---

**Last Updated:** 2026-03-09  
**Maintainer:** 小九 + 珊瑚海
