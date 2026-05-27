# Frontend Design Protocol

## Purpose

Separate visual direction, human taste approval, frontend code validation, and production readiness.

## Authority States

| Item | Default state | Upgrade condition |
| --- | --- | --- |
| `visual_direction` | `DEFAULT_ACCEPT` only after human approval | Human owner explicitly accepts the taste direction |
| `frontend_code` | `VERIFY_REQUIRED` | Build, lint, responsive review, accessibility smoke check, and manual UI review pass |
| `production_readiness` | `PENDING` | Separate runtime, deployment, auth, data, monitoring, rollback, and owner approval gates pass |

## Required Checks

1. Build check.
2. Lint check.
3. Responsive review across expected desktop and mobile widths.
4. Accessibility smoke check for keyboard reachability, labels, contrast, focus, and reduced-motion concerns where relevant.
5. Manual UI review by the human owner or delegated reviewer.

## Gemini Boundary

- Gemini may provide aesthetics, visual direction, layout options, and UI exploration.
- Gemini visual direction can be accepted by taste after human approval.
- Gemini frontend code is a candidate and remains `VERIFY_REQUIRED`.
- Gemini output cannot bypass build, lint, responsive review, accessibility smoke check, or manual UI review.

## Non-Claims

- A nice screenshot is not production readiness.
- Human taste approval is not build validation.
- Build success is not product judgment.
- Frontend visual approval does not validate backend, auth, data, provider access, deployment, monitoring, rollback, or revenue readiness.
