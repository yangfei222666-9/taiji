# Real Timeline

## Verdict

| Gate | Verdict |
| --- | --- |
| Timeline archive | PENDING_SETUP |
| Evidence layer | MUST_BE_REAL |
| Mythic layer | SYMBOLIC / allowed |
| Cinematic layer | DRAMATIZED / must be labeled |
| Private data exposure | BLOCKED |
| Fabricated achievement | BLOCKED |

This file is the real-event timeline template. It must preserve the difference
between what happened, what it means symbolically, and what may later be
dramatized.

## Entry Template

```text
Date:
Event:
Evidence source:
Evidence path:
Reality layer:
Symbolic layer:
Cinematic layer:
Verdict: PASS / PARTIAL / PENDING / BLOCKED
What cannot be claimed:
Privacy / sanitization notes:
Next review date:
```

## JSONL Template

```json
{
  "date": "YYYY-MM-DD",
  "event": "short factual event",
  "evidence_source": "chat | git | closeout | image | runbook | other",
  "evidence_path": "relative path or external reference placeholder",
  "reality_layer": "what actually happened",
  "symbolic_layer": "optional mythic mapping",
  "cinematic_layer": "optional dramatized treatment, clearly labeled",
  "verdict": "PASS | PARTIAL | PENDING | BLOCKED",
  "what_cannot_be_claimed": [
    "claims that are not supported by evidence"
  ],
  "privacy_sanitization_notes": "redaction or consent status",
  "next_review_date": "YYYY-MM-DD"
}
```

## Required Fields

Every timeline entry must include:

- Date.
- Event.
- Evidence source.
- Reality layer.
- Verdict.
- What cannot be claimed.
- Privacy / sanitization notes.

If any required field is missing, the entry remains `PENDING`.

## Evidence Rules

- A chat excerpt is source material, not final proof by itself.
- A screenshot is context until source files or live state are checked.
- A local file is not canonical truth until git gates complete.
- A PR is not merge.
- A merged PR is not release.
- A plan is not execution.
- AI-generated imagery is not documentary truth.

## Starter Backlog

Potential future entries:

- Hidden systems childhood interest.
- SpaceX mission lock-in.
- Journey to the West mapping.
- TaijiOS evidence-first doctrine.
- New computer / Fangcunshan workstation setup.
- Git Five Elements Mountain blockers.
- AI tool routing formula.
- Four-book system.
- Life systems closure.
- Xiaojiu Tongtianlu canon creation.

All starter backlog items are `PENDING` until source material is indexed.
