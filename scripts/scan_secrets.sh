#!/usr/bin/env bash
set -Eeuo pipefail
# Détection basique de secrets ; .env et secrets.env doivent être ignorés.
if git ls-files 2>/dev/null | grep -qE '(^|/)(\.env|secrets\.env)$'; then
  echo "::error::un fichier de secrets est suivi par git"; exit 1
fi
PATTERN='(AKIA|scw-[a-f0-9-]{36}|sk-ant-|ghp_|SG\.[A-Za-z0-9_-]{16,})'
if git grep -nIE "$PATTERN" -- . ':!*.example' ':!scripts/scan_secrets.sh' 2>/dev/null; then
  echo "::error::secret potentiel détecté dans le code"; exit 1
fi
echo "scan-secrets ok"
