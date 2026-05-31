SHELL := /bin/bash

.PHONY: verify

verify:
	@python3 tools/verify_evidence_preflight.py
