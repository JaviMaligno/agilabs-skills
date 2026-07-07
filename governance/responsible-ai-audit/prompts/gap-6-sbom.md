# Gap 6 — SBOM + licence allowlist

[Preamble must be prepended at invocation.]

## Objective

Generate an SBOM and enforce a production-dependency licence allowlist. The licence check is the **gate**; the SBOM is the artifact.

## "Done" criteria (stack-agnostic)

- A repo-root file `licenses-allowlist.json` declares an SPDX allowlist (MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Unlicense, CC0-1.0, MPL-2.0) plus an `exceptions` map keyed by SPDX id with per-package justifications.
- A script `scripts/check-licenses.<ext>` exits 0 when every production dependency uses an allowed licence (or is in `exceptions`), and exits 1 otherwise, printing the offenders.
- A run target (`npm run check-licenses`, `composer run check-licenses`, `make check-licenses`, etc.) invokes the script.
- An SBOM run target (`npm run sbom`, `make sbom`, etc.) produces a CycloneDX JSON file at repo root.
- The SBOM output file is gitignored. The allowlist JSON is **not** gitignored.
- Operator workflow (run before tagging a release) documented in `CLAUDE.md` / `README.md` deployment section.
- Compliance tracker (`docs/RESPONSIBLE_AI_COMPLIANCE.md` item 6 OSS sub-control) updated.

## Stack hints

### node

Devdeps: `@cyclonedx/cyclonedx-npm`, `license-checker-rseidelsohn`.

```json
"scripts": {
  "sbom": "cyclonedx-npm --output-format JSON --output-file sbom.cdx.json --omit dev",
  "check-licenses": "node scripts/check-licenses.js"
}
```

`scripts/check-licenses.js` uses `license-checker-rseidelsohn` with `{ production: true, excludePrivatePackages: true }`. Normalise SPDX `OR` / `AND`. Honor `exceptions[<spdx>]` substring match against `<pkg>@<version>`.

### laravel / php

Devdeps: `cyclonedx/cyclonedx-php-composer`. For licence checking, use `composer licenses --no-dev --format=json` and parse it in `scripts/check-licenses.php`.

```json
"scripts": {
  "sbom": "vendor/bin/cyclonedx-php-composer --output-format=json --output-file=sbom.cdx.json",
  "check-licenses": "php scripts/check-licenses.php"
}
```

`scripts/check-licenses.php` reads `licenses-allowlist.json`, executes `composer licenses --no-dev --format=json`, decodes, walks each package, returns exit 0/1.

### python

Devdeps (add to `[project.optional-dependencies].dev` in `pyproject.toml` or to `requirements-dev.txt`): `pip-licenses>=4`, `cyclonedx-bom>=4` (provides `cyclonedx-py`).

Run targets — add to a `Makefile` (preferred for Python projects) or to `[project.scripts]` if the project ships entry points:

```makefile
.PHONY: sbom check-licenses
sbom:
	cyclonedx-py environment -o sbom.cdx.json --schema-version 1.6
check-licenses:
	python scripts/check_licenses.py
```

`scripts/check_licenses.py` (≈ 80 lines): import `pip_licenses` API or shell out to `pip-licenses --format=json --with-system`; parse the JSON; honour `licenses-allowlist.json` (allowed list + exceptions per package name@version). Exit 1 on violation, 0 otherwise. Normalise SPDX `OR`/`AND` the same way the Node version does.

For monorepos with multiple `pyproject.toml`s, run the scan once per project and aggregate.

### go

Use `go-licenses` (`go install github.com/google/go-licenses@latest`). SBOM via `syft` (binary).

```makefile
sbom:
	syft scan dir:. -o cyclonedx-json=sbom.cdx.json
check-licenses:
	go-licenses check ./... --allowed_licenses=$(shell jq -r '.allowed | join(",")' licenses-allowlist.json)
```

## CI integration

**Do NOT** mix custom steps with imported pipeline templates if the repo uses one (`bitbucket-pipelines.yml` with `import:` syntax cannot be combined with sibling steps — it produces `duration: 0` failures). Document the manual operator gate instead and list the CI-integration follow-up in the tracker.

## Out of scope

- Auto-uploading SBOM to an artifact repository.
- Backup procedure (separate sub-item).
- Forcing the CI gate when the repo uses a shared pipeline template.
