# Git Workflow Rules

## Branch Naming

- `feat/<scope>` — new functionality
- `fix/<scope>` — bug fix
- `chore/<scope>` — maintenance, CI, docs

## Commit Format

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `chore`, `test`, `refactor`, `docs`

Examples:

```
feat(coherent): add experience decay CLI
fix(validator): correct subtitle safety threshold
test(pipeline): add planner edge case coverage
chore(ci): add pytest step to workflow
```

## Pull Requests

- Title follows commit format
- Description includes: what changed, why, how to verify
- All CI checks must pass before merge
- Coverage must not drop below baseline

## What Not To Do

- Don't force-push to shared branches
- Don't skip CI (`--no-verify`)
- Don't merge with failing tests
