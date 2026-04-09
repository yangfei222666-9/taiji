# Draft Registry

## Purpose

This is the **isolated registration area** for auto-generated Skill drafts.

Drafts here are **NOT in production**. They are in observation/validation mode.

## Status Flow

```
draft → validated → (manual review) → promoted / rejected
```

### States

- **draft** - Initial state after generation
- **validated** - Passed all three validation layers (format/security/risk)
- **promoted** - Manually approved and moved to production skills directory
- **rejected** - Failed validation or manual review, kept for learning

## Structure

Each draft lives in its own subdirectory:

```
draft_registry/
├── index.json                    # Global status index
├── {skill_id}/
│   ├── SKILL.md                  # Draft skill content
│   ├── meta.json                 # Metadata (version, timestamps, source)
│   ├── validation_result.json    # Validation output
│   └── feedback.jsonl            # Shadow run feedback (optional)
```

## Rules

1. **No auto-promotion** - All drafts require manual review before production
2. **Immutable after validation** - Validated drafts cannot be modified (create new version instead)
3. **Rejection preserves history** - Rejected drafts stay in registry for learning
4. **Shadow mode only** - Drafts can run in shadow mode but never affect production chain

## Design Principle

**Observation period first, production integration later.**

This registry exists to prove value before touching the main system.
