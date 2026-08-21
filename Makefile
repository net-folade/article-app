# Use dev unless ENV is set, for example: `make deploy ENV=prod`.
ENV ?= dev
TF_DIR := infra/terraform/envs/$(ENV)
TF := terraform -chdir=$(TF_DIR)

# Use the project virtual environment when available.
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: test clean

test:
	$(PY) -m pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache

.PHONY: validate-feeds

validate-feeds:
	$(PY) scripts/validate_feeds.py


.PHONY: inspect-feeds

inspect-feeds:
	$(PY) scripts/inspect_feeds.py


.PHONY: dry-run

dry-run:
	$(PY) scripts/dry_run.py


# AWS

.PHONY: package init fmt validate plan deploy invoke logs stats destroy outputs

package:
	./scripts/package_lambda.sh

# Run after backend or module changes.
init:
	$(TF) init -input=false

fmt:
	terraform -chdir=infra/terraform fmt -recursive

validate:
	$(TF) validate

# Build the zip before planning.
plan: package
	$(TF) plan

# Keep Terraform's confirmation prompt.
deploy: package
	$(TF) apply

outputs:
	$(TF) output

invoke:
	aws lambda invoke \
	  --function-name $$($(TF) output -raw function_name) \
	  --cli-binary-format raw-in-base64-out \
	  --payload '{}' \
	  /dev/stdout

logs:
	aws logs tail $$($(TF) output -raw log_group_name) --follow

stats:
	$(PY) scripts/stats.py --bucket $$($(TF) output -raw bucket_name)

# Destroying prod also deletes its send history.
destroy:
	$(TF) destroy
