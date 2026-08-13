#!/usr/bin/env bash
# Install the local pre-commit hook that runs scripts/check_pii.sh.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
hook="$repo_root/.git/hooks/pre-commit"

cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Installed by scripts/install_hooks.sh
repo_root="$(git rev-parse --show-toplevel)"
exec "$repo_root/scripts/check_pii.sh"
HOOK

chmod +x "$hook"
echo "Installed pre-commit hook: $hook"
