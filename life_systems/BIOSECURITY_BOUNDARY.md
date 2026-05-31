# Life Systems Biosecurity Boundary

## Verdict

```text
verdict=life_systems_biosecurity_boundary_draft
scope=life_systems_research_boundary
mode=learning_only_observe_only_evidence_audit
wet_lab=false
pathogen_work=false
gene_editing=false
medical_advice=false
runtime_changed=false
code_changed=false
secret_read=false
stage_commit_push=false
repo_pass_claimed=false
t7_imported=false
```

## Purpose

The life systems research lane maps biological concepts into TaijiOS reliability, safety, and agent-defense language.

Research mode:

```text
learning_only + observe_only + evidence_audit
```

This lane can study high-level ideas such as evolution, immune systems, nervous systems, ecology, AI biology, astrobiology, and biosecurity governance as systems metaphors and safety models.

It must not provide operational biological instructions or high-impact biomedical guidance.

## Allowed Mapping

| Life system concept | TaijiOS mapping | Boundary |
| --- | --- | --- |
| Immune system | agent threat defense, quarantine, anomaly response | conceptual only |
| Nervous system | EventFlow, signal routing, feedback loops | conceptual only |
| Cells | worker agents, local state, bounded functions | conceptual only |
| Genes | source blueprint, configuration, inheritance metaphor | no gene editing instructions |
| Evolution | iteration, selection pressure, rollback, adaptation | no biological optimization guidance for harm |
| Homeostasis | system health, budgets, stability, recovery | no medical diagnosis |
| Infection | malicious input, prompt injection, compromised dependency | cybersecurity metaphor only |
| Isolation | `BLOCKED`, quarantine, sandbox, containment | no wet-lab protocol |

## Hard Blocks

The life systems lane must not provide:

```text
wet-lab protocols
pathogen handling guidance
pathogen design guidance
pathogen synthesis guidance
gene editing operational instructions
medical diagnosis
medical treatment plans
dosage or medication instructions
biological optimization for harm
evasion of biosafety controls
instructions to acquire restricted biological materials
```

## AI Biology Boundary

AI biology and biosecurity may be discussed only as high-level systems mapping, governance, risk modeling, or defensive safety thinking.

Model output is not biological truth. Any factual scientific claim needs source review, and any safety-relevant claim must remain conservative.

## Evidence Requirements

Every life systems note should preserve:

```text
topic
source type
learning objective
system mapping
allowed authority=observe_only
forbidden authority
what cannot be claimed
next safe action
```

## Forbidden Promotions

Do not promote life systems notes into:

```text
medical advice
lab instructions
bioengineering instructions
clinical claims
health optimization claims
public safety claims
SpaceX readiness claims
runtime authority
```

## Non-Claims

This boundary does not claim:

```text
biology expertise
medical authority
wet-lab readiness
biosecurity certification
AI biology implementation readiness
production safety validation
```

## Acceptance Criteria

A life systems artifact is acceptable only if:

```text
learning_only=true
observe_only=true
evidence_audit=true
wet_lab=false
pathogen_work=false
gene_editing=false
medical_advice=false
harmful_biological_optimization=false
```
