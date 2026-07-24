#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

VERSION="${1:-}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Bruk: $0 <versjon, f.eks. 0.2.0>" >&2
    exit 1
fi
TAG="v$VERSION"

if ! gh auth status >/dev/null 2>&1; then
    echo "Feil: ikke logget inn med gh. Kjør 'gh auth login' først." >&2
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "Feil: arbeidstreet er ikke rent. Committ eller stash endringer først." >&2
    exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
    echo "Feil: må stå på main (er på $BRANCH)." >&2
    exit 1
fi

echo "Henter siste main fra origin..."
git fetch origin main --quiet
LOCAL="$(git rev-parse main)"
REMOTE="$(git rev-parse origin/main)"
if [ "$LOCAL" != "$REMOTE" ]; then
    echo "Feil: main er ikke oppdatert med origin/main." >&2
    exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Feil: taggen $TAG finnes allerede." >&2
    exit 1
fi

NOTES_FILE="$(mktemp)"
trap 'rm -f "$NOTES_FILE"' EXIT

python3 - "$VERSION" "$NOTES_FILE" <<'PYEOF'
import re
import sys
from datetime import date

version, notes_path = sys.argv[1], sys.argv[2]

changelog_path = "CHANGELOG.md"
with open(changelog_path) as f:
    content = f.read()

unreleased_heading = "## [Unreleased]"
start = content.find(unreleased_heading)
if start == -1:
    sys.exit("Feil: fant ikke '## [Unreleased]' i CHANGELOG.md")

body_start = start + len(unreleased_heading)
next_heading = content.find("\n## [", body_start)
body = content[body_start:next_heading if next_heading != -1 else len(content)]
body = body.strip("\n")

if not body.strip():
    sys.exit("Feil: '## [Unreleased]' i CHANGELOG.md er tom. Legg til endringer før release.")

today = date.today().isoformat()
new_section = f"{unreleased_heading}\n\n## [{version}] - {today}\n\n{body}\n"

rest = content[next_heading:] if next_heading != -1 else ""
new_content = content[:start] + new_section + ("\n" if rest else "") + rest.lstrip("\n")

with open(changelog_path, "w") as f:
    f.write(new_content)

with open(notes_path, "w") as f:
    f.write(f"## [{version}] - {today}\n\n{body}\n")

init_path = "claude_usage/__init__.py"
with open(init_path) as f:
    init_content = f.read()

new_init_content = re.sub(
    r'^__version__ = ".*"$',
    f'__version__ = "{version}"',
    init_content,
    flags=re.MULTILINE,
)
if new_init_content == init_content:
    sys.exit(f"Feil: fant ikke __version__-linje i {init_path}")

with open(init_path, "w") as f:
    f.write(new_init_content)
PYEOF

git add CHANGELOG.md claude_usage/__init__.py
git commit -m "Release $TAG"
git tag "$TAG"
git push origin main
git push origin "$TAG"
gh release create "$TAG" --title "$TAG" --notes-file "$NOTES_FILE"

echo "Ferdig: $TAG er tagget, pushet og publisert som GitHub Release."
