# Thin wrapper over the real entry point, `python -m mwall <stage>` (decision D013).
# Every stage is resumable. Full-universe targets are long-running (hours).
PY ?= uv run python -W ignore -m mwall

.PHONY: fixture test data ingest parse clean qa features train score site

fixture:            ## build the committed two-trust fixture and compare with stored outputs
	$(PY) fixture

test:               ## unit, golden-file and schema tests
	uv run pytest

ingest:             ## LONG: EDGAR index -> trust discovery -> filings -> EX-102 + 10-D statements
	$(PY) index
	$(PY) discover
	$(PY) filings
	$(PY) download
	$(PY) tend

parse:
	$(PY) parse

clean:
	$(PY) clean
	$(PY) wholeloans
	$(PY) geo

qa:                 ## Gate 1 reports into docs/qa
	$(PY) census
	$(PY) qa

data: ingest parse clean qa

features train score site:
	@echo "$@: not built yet (Gate 2 onward)"; exit 1
