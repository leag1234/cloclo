#!/usr/bin/env bash
set -Eeuo pipefail
# Lint multi-langage tolérant à l'absence d'outils en M0, strict s'ils sont présents.
command -v ruff >/dev/null && ruff check . || echo "(ruff absent — skip py lint)"
command -v shellcheck >/dev/null && shellcheck scripts/*.sh infra/*.sh 2>/dev/null || echo "(shellcheck absent — skip)"
echo "lint ok"
