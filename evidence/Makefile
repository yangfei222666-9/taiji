SHELL := /bin/bash

APP        ?= taijios
VERSION    ?= v0.1.0
ENV        ?= prod
IMAGE      ?= registry.example.com/$(APP)@sha256:abc123
SBOM_HASH  ?= demo

UTC        := $(shell date -u +"%Y%m%dT%H%M%SZ")
ISO_UTC    := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

BUILD_FILE  := build/$(APP)-$(VERSION).tar.gz
SNAPSHOT    := deploy/snapshot_$(ENV)_$(UTC).json
AUDIT_LOG   := audit/requests_$(UTC).jsonl
ATTESTATION := attest/provenance_$(APP)_$(VERSION)_$(UTC).json
MANIFEST    := release/manifest_$(VERSION).yaml

PRIVATE_KEY := keys/release_priv.pem
PUBLIC_KEY  := keys/release_pub.pem

.PHONY: all evidence verify init-keys clean

all: evidence

init-keys: $(PRIVATE_KEY) $(PUBLIC_KEY)

$(PRIVATE_KEY):
	@mkdir -p keys
	@echo "Generating local release signing private key..."
	@umask 077; openssl genrsa -out $(PRIVATE_KEY) 4096 >/dev/null 2>&1

$(PUBLIC_KEY): $(PRIVATE_KEY)
	@echo "Generating local release signing public key..."
	@openssl rsa -in $(PRIVATE_KEY) -pubout -out $(PUBLIC_KEY) >/dev/null 2>&1

evidence: init-keys
	@mkdir -p build deploy audit attest release
	@echo "Generating deploy snapshot..."
	@printf '{\n  "app": "%s",\n  "env": "%s",\n  "image": "%s",\n  "generated_at": "%s",\n  "sbom_hash": "%s"\n}\n' \
		"$(APP)" "$(ENV)" "$(IMAGE)" "$(ISO_UTC)" "$(SBOM_HASH)" > $(SNAPSHOT)
	@echo "Generating dummy audit log..."
	@printf '{"req_id":"demo-1","actor":"system","policy":"allow","ts":"%s"}\n' "$(ISO_UTC)" > $(AUDIT_LOG)
	@echo "Packing build artifact..."
	@tar czf $(BUILD_FILE) examples/ schema/
	@echo "Generating provenance attestation..."
	@printf '{\n  "app": "%s",\n  "version": "%s",\n  "env": "%s",\n  "build_file": "%s",\n  "snapshot": "%s",\n  "audit_log": "%s",\n  "generated_at": "%s"\n}\n' \
		"$(APP)" "$(VERSION)" "$(ENV)" "$(BUILD_FILE)" "$(SNAPSHOT)" "$(AUDIT_LOG)" "$(ISO_UTC)" > $(ATTESTATION)
	@echo "Generating manifest..."
	@bash scripts/gen_manifest.sh \
		$(BUILD_FILE) \
		$(SNAPSHOT) \
		$(AUDIT_LOG) \
		$(ATTESTATION) \
		> $(MANIFEST)
	@echo "Signing manifest..."
	@openssl dgst -sha256 \
		-sign $(PRIVATE_KEY) \
		-out $(MANIFEST).sig \
		$(MANIFEST)
	@echo "DONE."

verify:
	@bash scripts/verify_all.sh $(MANIFEST)

clean:
	rm -rf build deploy audit attest release
