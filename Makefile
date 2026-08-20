.PHONY: test clean

test:
	python -m pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache

.PHONY: validate-feeds

validate-feeds:
	python scripts/validate_feeds.py


.PHONY: inspect-feeds

inspect-feeds:
	python scripts/inspect_feeds.py


.PHONY: dry-run

dry-run:
	python scripts/dry_run.py