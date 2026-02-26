# Changelog

## v1.0.0 — Final (2026-02-26)

Summary

- Initial stable release: consolidates repository layout, restores CI/tests and documents the stable behavior.

Added

- Consolidated code under the `infra_monitoring` package.
- Basic Prometheus exporter and minimal application metrics (load, cpu temp, network throughput).

Changed

- Restored `conftest.py` and set `PYTHONPATH=src` to make tests importable.
- Hardened CI workflows: added `workflow_dispatch`, moved secret checks to runtime, and improved lint/test steps.
- Docker: use non-root user in `Dockerfile` and load `.env` in `docker-compose`.

Fixed

- Ensure `.cache` uses repository root for post-treatment history.
- Remove duplicate placeholder `infrastructure` package.

Removed / Cleanup

- Deleted legacy packages and placeholder files after consolidation.

Documentation

- Updated technical README and moved PT-BR technical README under `docs/`.

Notes

- This release contains no breaking API changes; major refactors will target `2.0.0`.
- Full commit history documents the detailed changes and PRs included in this release.

For maintainers: commit message: `chore(release): add CHANGELOG for v1.0.0 final`
