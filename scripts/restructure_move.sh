#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Infra Monitoring System - Restructure Move Script (git mv)
#
# Purpose:
#   Move legacy modules under src/ into the target namespace package:
#     src/infra_monitoring/{core,services,infra,api}/...
#
# Design:
#   - Uses `git mv` to preserve history.
#   - DRY_RUN=1 by default (prints commands only).
#   - Does NOT rewrite imports. After moving, imports WILL break until you
#     complete the follow-up "import update" step (planned separately).
#
# Usage (Git Bash / WSL):
#   DRY_RUN=1  ./scripts/restructure_move.sh   # preview
#   DRY_RUN=0  ./scripts/restructure_move.sh   # execute
#
# Preconditions:
#   - run from repo root
#   - clean working tree
# -----------------------------------------------------------------------------

DRY_RUN="${DRY_RUN:-1}"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "+ $*"
  else
    eval "$@"
  fi
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_clean_tree() {
  if [[ -n "$(git status --porcelain)" ]]; then
    git status --porcelain
    die "working tree not clean; commit/stash first"
  fi
}

require_paths_tracked() {
  local missing=0
  for p in "$@"; do
    if ! git ls-files --error-unmatch "$p" >/dev/null 2>&1; then
      echo "missing tracked path: $p" >&2
      missing=1
    fi
  done
  [[ "$missing" -eq 0 ]] || die "one or more expected paths are not tracked"
}

main() {
  require_clean_tree

  # 1) Ensure destination directories exist
  run "mkdir -p src/infra_monitoring/infra/config"
  run "mkdir -p src/infra_monitoring/infra/system"
  run "mkdir -p src/infra_monitoring/services/monitoring"
  run "mkdir -p src/infra_monitoring/api/exporter"

  # 2) Replace scaffold core/__init__.py with the legacy one (preserves re-exports)
  #    NOTE: this removes the placeholder created earlier.
  require_paths_tracked "src/infra_monitoring/core/__init__.py" "src/core/__init__.py"
  run "git rm -f src/infra_monitoring/core/__init__.py"

  # 3) Move core modules
  require_paths_tracked \
    "src/core/__init__.py" \
    "src/core/args.py" \
    "src/core/core.py" \
    "src/core/emitter.py"

  run "git mv src/core/__init__.py src/infra_monitoring/core/__init__.py"
  run "git mv src/core/args.py src/infra_monitoring/core/args.py"
  run "git mv src/core/core.py src/infra_monitoring/core/core.py"
  run "git mv src/core/emitter.py src/infra_monitoring/core/emitter.py"

  # 4) Move config into infra
  require_paths_tracked "src/config/__init__.py" "src/config/settings.py"
  run "git mv src/config/__init__.py src/infra_monitoring/infra/config/__init__.py"
  run "git mv src/config/settings.py src/infra_monitoring/infra/config/settings.py"

  # 5) Move system into infra
  require_paths_tracked \
    "src/system/__init__.py" \
    "src/system/helpers.py" \
    "src/system/ingest.py" \
    "src/system/log_helpers.py" \
    "src/system/logs.py" \
    "src/system/maintenance.py" \
    "src/system/network_learning.py" \
    "src/system/time_helpers.py" \
    "src/system/treatments.py"

  run "git mv src/system/__init__.py src/infra_monitoring/infra/system/__init__.py"
  run "git mv src/system/helpers.py src/infra_monitoring/infra/system/helpers.py"
  run "git mv src/system/ingest.py src/infra_monitoring/infra/system/ingest.py"
  run "git mv src/system/log_helpers.py src/infra_monitoring/infra/system/log_helpers.py"
  run "git mv src/system/logs.py src/infra_monitoring/infra/system/logs.py"
  run "git mv src/system/maintenance.py src/infra_monitoring/infra/system/maintenance.py"
  run "git mv src/system/network_learning.py src/infra_monitoring/infra/system/network_learning.py"
  run "git mv src/system/time_helpers.py src/infra_monitoring/infra/system/time_helpers.py"
  run "git mv src/system/treatments.py src/infra_monitoring/infra/system/treatments.py"

  # 6) Move monitoring into services
  require_paths_tracked \
    "src/monitoring/__init__.py" \
    "src/monitoring/averages.py" \
    "src/monitoring/formatters.py" \
    "src/monitoring/handlers.py" \
    "src/monitoring/metrics.py" \
    "src/monitoring/state.py"

  run "git mv src/monitoring/__init__.py src/infra_monitoring/services/monitoring/__init__.py"
  run "git mv src/monitoring/averages.py src/infra_monitoring/services/monitoring/averages.py"
  run "git mv src/monitoring/formatters.py src/infra_monitoring/services/monitoring/formatters.py"
  run "git mv src/monitoring/handlers.py src/infra_monitoring/services/monitoring/handlers.py"
  run "git mv src/monitoring/metrics.py src/infra_monitoring/services/monitoring/metrics.py"
  run "git mv src/monitoring/state.py src/infra_monitoring/services/monitoring/state.py"

  # 7) Move exporter into api
  require_paths_tracked \
    "src/exporter/__init__.py" \
    "src/exporter/main_http.py" \
    "src/exporter/prometheus.py" \
    "src/exporter/promtail.py"

  run "git mv src/exporter/__init__.py src/infra_monitoring/api/exporter/__init__.py"
  run "git mv src/exporter/main_http.py src/infra_monitoring/api/exporter/main_http.py"
  run "git mv src/exporter/prometheus.py src/infra_monitoring/api/exporter/prometheus.py"
  run "git mv src/exporter/promtail.py src/infra_monitoring/api/exporter/promtail.py"

  # 8) Optional cleanup (leave legacy empty dirs for now; git won't track empties)
  echo
  echo "Next steps after move (NOT done by this script):"
  echo "  - Update imports from src.* / relative imports to infra_monitoring.*"
  echo "  - Decide whether src/main.py stays as legacy entrypoint or becomes a thin shim"
  echo "  - Run: pytest -q"
  echo
  echo "Done. (DRY_RUN=$DRY_RUN)"
}

main "$@"
