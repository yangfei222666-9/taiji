# Privacy And Dramatization Rules

## Verdict

| Gate | Verdict |
| --- | --- |
| Privacy boundary | PASS |
| Dramatization boundary | PASS |
| Secret exposure | BLOCKED |
| Private third-party exposure | BLOCKED unless consented and necessary |
| Fabricated achievement | BLOCKED |
| SpaceX employment claim | BLOCKED unless evidence-backed |
| AI-generated scene as documentary truth | BLOCKED |

This document is the release boundary for Xiaojiu Tongtianlu. It protects the
evidence layer from being polluted by dramatization and protects private data
from being exposed.

## Three-Layer Rule

| Layer | Allowed | Required label |
| --- | --- | --- |
| Real evidence | Real events, artifacts, closeouts, git states | evidence |
| Symbolic mapping | Journey, Yijing, Shanhai, Yongle, life systems imagery | symbolic |
| Cinematic dramatization | Compressed scenes, invented visuals, staged narration | dramatized |

Dramatization must never overwrite the evidence layer.

## Blocked Content

Never include:

- API keys, tokens, passwords, private keys, credentials, recovery codes.
- Emails, phone numbers, addresses, private account names, private screenshots.
- Private third-party identities without consent.
- Private conversations without review and sanitization.
- Medical, legal, trading, or biological execution advice.
- Fabricated achievements.
- Claims of SpaceX readiness, employment, interview, endorsement, or access that
  are not backed by evidence.
- AI-generated scenes presented as real footage.
- Symbolic interpretations presented as scientific facts.

## Sanitization Checklist

Before any excerpt, image, or scene is used:

- Remove secret values.
- Remove contact details.
- Remove private identifiers.
- Replace private people with roles or composites.
- Mark evidence, symbolic, or dramatized layer.
- State what cannot be claimed.
- Preserve blockers and failures.
- Preserve PENDING, PARTIAL, and BLOCKED states.

## Release Gate

No public release until:

- Source material is indexed.
- Privacy review is complete.
- Claims are mapped to evidence.
- Dramatized scenes are labeled.
- Third-party exposure is removed or consented.
- No secret appears.
- No unsupported SpaceX claim appears.
- No medical, trading, legal, or biological execution claim appears.

## Rule Of Truth

```text
The archive earns trust by preserving limits.
```

If a scene is beautiful but false, it must be labeled dramatized or removed.
